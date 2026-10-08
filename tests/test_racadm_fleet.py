import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import racadm_fleet as tool


class FleetTests(unittest.TestCase):
    def test_host_validation_blocks_options_and_shell_text(self):
        for value in ['-oProxyCommand=evil', 'host; reboot', 'host\nname', '', 'a..b']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                tool.valid_host(value)
        for value in ['192.0.2.10', 'idrac.example.test', '2001:db8::10']:
            self.assertEqual(tool.valid_host(value), value)

    @patch('racadm_fleet.subprocess.run')
    def test_racadm_error_with_zero_exit_is_failure(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, 'ERROR: Invalid subcommand', '')
        self.assertFalse(tool.run_command('192.0.2.10', 'root', tool.COMMANDS['nic'], 5)['ok'])
        argv = run.call_args.args[0]
        self.assertIn('StrictHostKeyChecking=yes', argv)
        self.assertEqual(argv[-1], 'racadm hwinventory NIC')

    @patch('racadm_fleet.subprocess.run', side_effect=subprocess.TimeoutExpired('ssh', 5))
    def test_timeout_is_structured_failure(self, run):
        result = tool.run_command('192.0.2.10', 'root', tool.COMMANDS['system'], 5)
        self.assertTrue(result['timed_out'])
        self.assertFalse(result['ok'])

    @patch('racadm_fleet.subprocess.run')
    def test_demo_never_connects(self, run):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'report.json'
            self.assertEqual(tool.main(['--demo', '--output', str(output)]), 0)
            report = json.loads(output.read_text())
            self.assertTrue(report['demo'])
            self.assertEqual(len(report['servers'][0]['checks']), 4)
        run.assert_not_called()

    @patch('racadm_fleet.run_command')
    def test_failed_command_does_not_stop_fleet(self, run):
        run.side_effect = [
            {'ok': False, 'returncode': 255, 'stdout': '', 'stderr': 'connection failed', 'timed_out': False},
            {'ok': True, 'returncode': 0, 'stdout': 'Bios Version = example', 'stderr': '', 'timed_out': False},
        ]
        with tempfile.TemporaryDirectory() as directory:
            inventory = Path(directory) / 'inventory.csv'
            inventory.write_text('name,host\na,192.0.2.10\nb,192.0.2.11\n')
            output = Path(directory) / 'report.json'
            self.assertEqual(tool.main(['--inventory', str(inventory), '--checks', 'firmware', '--workers', '1', '--output', str(output)]), 1)
            report = json.loads(output.read_text())
            self.assertEqual([s['collection_ok'] for s in report['servers']], [False, True])


if __name__ == '__main__':
    unittest.main()
