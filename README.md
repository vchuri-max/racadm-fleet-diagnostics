# RACADM Fleet Diagnostics

A Python CLI for collecting Dell PowerEdge diagnostics across multiple iDRACs. Built around data center operations workflows: checking BIOS/iDRAC versions, collecting sensor readings, and investigating NIC inventory before maintenance.

## Features

- Four read-only RACADM checks, executed over OpenSSH.
- Concurrent server collection with bounded workers and per-command timeouts.
- JSON reports retaining raw output for troubleshooting and audit review.
- Individual failures remain in the report; failed collections return a nonzero exit code.
- SSH key authentication, strict host verification, and no passwords in source or command arguments.
- Hardware-free demo, unit tests, and GitHub Actions workflow.
- Python standard library only; no pip dependencies.

## Quick start

Requires Python 3.10+ and OpenSSH on macOS or Linux. For real use, enable SSH on iDRAC and configure supported public-key authentication with a suitably permissioned account. Confirm the device host-key fingerprint through a trusted channel and add the verified host key to your SSH known_hosts before running. The tool does not enroll or bypass host keys.

```bash
python3 racadm_fleet.py --demo
python3 racadm_fleet.py --inventory inventory.example.csv --user monitoring --identity ~/.ssh/idrac_key
python3 racadm_fleet.py --inventory inventory.example.csv --checks firmware nic --workers 4 --timeout 45
python3 -m unittest discover -s tests -v
```

Replace example IP addresses with your lab iDRAC addresses. CSV format:

```csv
name,host
lab-r630-01,192.0.2.10
lab-r630-02,192.0.2.11
```

## RACADM commands

| Check | Command | Purpose |
| --- | --- | --- |
| system | `racadm getsysinfo` | System information and service tag |
| firmware | `racadm getversion` | Installed component firmware versions |
| sensors | `racadm getsensorinfo` | Sensor information reported by iDRAC |
| nic | `racadm hwinventory NIC` | Network adapter hardware inventory |

Dell references: [iDRAC9 SSH RACADM](https://www.dell.com/support/manuals/en-us/oth-r640/idrac9_7.xx_racadm_pub/ssh-or-remote-racadm?guid=guid-d55fa376-512b-4e2a-9465-bea099eaee49&lang=en-us) and [iDRAC7/8 RACADM guide](https://dl.dell.com/topicspdf/idrac8-lifecycle-controller-v2818181_cli-guide_en-us.pdf).

## Understanding the report

`collection_ok` means every requested command completed successfully; it does **not** mean the hardware is healthy. Review sensor output and logs using your operational runbook. Raw output varies by iDRAC generation, permissions, and firmware; unsupported commands appear as failures rather than aborting other servers. Firmware collection lists installed versions; it does not determine whether they are latest.

Exit codes: `0` complete collection, `1` at least one command failed, `2` invalid input or report/inventory I/O failure. Timeout applies per command, not to the entire fleet run. This first version preserves output rather than claiming a universal parser for all iDRAC generations.

Demo values are fictional illustrations, not hardware validation. Tests mock SSH responses; live iDRAC validation is still required. No reset, power control, configuration, or firmware-update operations are included.

## Publishing on GitHub

Create a repository named `racadm-fleet-diagnostics` and upload this folder's contents. Suggested description: **Python CLI for Dell iDRAC fleet diagnostics using RACADM over SSH, with concurrent collection, JSON reports, and automated tests.**

The example inventory contains only documentation IPs. Keep real inventories, generated reports, credentials, and keys private. The included `.gitignore` excludes default reports and local inventory files; check staged files before publishing. No license is imposed; add your chosen license before inviting reuse.

## Possible next steps

- Validate against your lab's iDRAC7/8/9 firmware combinations.
- Add tested sensor parsing using anonymized fixtures.
- Compare installed firmware against an explicitly maintained baseline.
- Add approved maintenance operations as a separate, reviewed workflow.
