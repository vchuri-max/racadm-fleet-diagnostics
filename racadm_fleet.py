#!/usr/bin/env python3
"""Collect read-only RACADM diagnostics over key-authenticated OpenSSH."""
import argparse
import csv
import ipaddress
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

COMMANDS = {
    'system': 'racadm getsysinfo',
    'firmware': 'racadm getversion',
    'sensors': 'racadm getsensorinfo',
    'nic': 'racadm hwinventory NIC',
}
DEMO = {
    'system': 'System Model = PowerEdge R630\nService Tag = DEMO001\n',
    'firmware': 'Bios Version = 2.19.0\niDRAC Version = 2.86.86.86\n',
    'sensors': 'Demo sensor output: fan and power supply readings would appear here.\n',
    'nic': 'NIC.Integrated.1-1-1:Intel(R) 2P X520/2P I350 rNDC\n',
}


def valid_host(value):
    """Accept IP literals or ordinary DNS names, never SSH option strings."""
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        labels = value.rstrip('.').split('.')
        if len(value) <= 253 and all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label) for label in labels):
            return value
    raise ValueError('host must be an IP address or DNS name')


def load_hosts(path):
    with path.open(newline='', encoding='utf-8') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {'name', 'host'} <= set(reader.fieldnames):
            raise ValueError('inventory requires name,host columns')
        hosts = []
        for row in reader:
            name = (row.get('name') or '').strip()
            if not name or len(name) > 128 or any(ord(c) < 32 for c in name):
                raise ValueError('each server needs a name without control characters')
            hosts.append({'name': name, 'host': valid_host((row.get('host') or '').strip())})
        if not hosts:
            raise ValueError('inventory is empty')
        return hosts


def run_command(host, user, command, timeout, identity=None):
    argv = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'ConnectTimeout=10', '-o', 'ConnectionAttempts=1',
            '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=2']
    if identity:
        argv += ['-i', str(identity), '-o', 'IdentitiesOnly=yes']
    argv += ['-l', user, host, command]
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
        # Some iDRAC versions return exit code zero for RACADM application errors.
        app_error = bool(re.search(r'^\s*ERROR\b', result.stdout + '\n' + result.stderr, re.MULTILINE | re.IGNORECASE))
        return {'ok': result.returncode == 0 and not app_error,
                'returncode': result.returncode, 'stdout': result.stdout,
                'stderr': result.stderr, 'timed_out': False}
    except subprocess.TimeoutExpired:
        return {'ok': False, 'returncode': None, 'stdout': '',
                'stderr': 'Command exceeded timeout.', 'timed_out': True}
    except OSError as exc:
        return {'ok': False, 'returncode': None, 'stdout': '',
                'stderr': str(exc), 'timed_out': False}


def collect(server, args):
    results = {}
    for check in args.checks:
        command = COMMANDS[check]
        if args.demo:
            result = {'ok': True, 'returncode': 0, 'stdout': DEMO[check],
                      'stderr': '', 'timed_out': False}
        else:
            result = run_command(server['host'], args.user, command, args.timeout, args.identity)
        results[check] = {'command': command, **result}
    return {**server, 'collection_ok': all(r['ok'] for r in results.values()), 'checks': results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path)
    parser.add_argument('--user', default='root')
    parser.add_argument('--identity', type=Path, help='SSH private key path; otherwise use SSH agent/config')
    parser.add_argument('--checks', nargs='+', choices=COMMANDS, default=list(COMMANDS))
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--timeout', type=int, default=30, help='seconds per command')
    parser.add_argument('--output', type=Path, default=Path('reports/report.json'))
    parser.add_argument('--demo', action='store_true', help='use fictional data; no SSH connections')
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 32 or not 1 <= args.timeout <= 600:
        parser.error('workers must be 1–32; timeout must be 1–600')
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]*', args.user):
        parser.error('invalid SSH username')
    if not args.demo and not args.inventory:
        parser.error('--inventory is required unless --demo is selected')
    try:
        hosts = load_hosts(args.inventory) if args.inventory else [{'name': 'demo-server', 'host': '192.0.2.10'}]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            servers = list(pool.map(lambda server: collect(server, args), hosts))
        report = {'generated_at': datetime.now(timezone.utc).isoformat(),
                  'demo': args.demo, 'servers': servers}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        for server in servers:
            status = 'COLLECTED' if server['collection_ok'] else 'INCOMPLETE'
            print(f"{server['name']}: {status}")
        print(f'Report: {args.output}')
        return 0 if all(s['collection_ok'] for s in servers) else 1
    except (ValueError, OSError, csv.Error) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
