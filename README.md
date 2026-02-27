# it-snapshot

![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-0078D6?logo=windows&logoColor=white)
![Version](https://img.shields.io/badge/version-2.0.0-brightgreen)
![psutil](https://img.shields.io/badge/dependency-psutil-green)
![GitHub repo](https://img.shields.io/badge/GitHub-websanal%2Fit--snapshot-181717?logo=github&logoColor=white)

A cross-platform endpoint inventory agent that collects a comprehensive point-in-time snapshot of a machine and outputs a structured `report.json` and a self-contained `report.html`.

---

## What it collects

| Category | Details |
|---|---|
| **Device Identity** | Hostname, FQDN, domain/workgroup, Machine GUID (Windows) / Platform UUID (macOS), MAC addresses, Azure AD device ID |
| **Hardware** | CPU (model, cores, threads, max clock, manufacturer), RAM total + per-DIMM slot (capacity, speed, manufacturer, part number), GPU (name, driver, VRAM), BIOS, motherboard, TPM (present/version), Secure Boot, monitors, printers |
| **Physical Disks** | Model, serial number, media type (SSD/HDD), interface (NVMe/SATA/USB), size |
| **Storage** | All partitions — drive letter, filesystem, total / used / free / %, BitLocker status |
| **OS Detail** | Edition, version, build number, install date, last boot, hotfix KB list + last installed date, local Administrators group members |
| **Network** | Per-adapter detail: MAC, driver version, link speed, IP / IPv6 addresses, DHCP, DNS servers, default gateway; active Wi-Fi SSID |
| **Software** | Full installed software list (name, version, publisher, install date) + startup entries (registry Run keys & startup folders) |
| **Security** | Antivirus, firewall profiles, UAC, BitLocker / FileVault, Windows Defender, Secure Boot, Gatekeeper (macOS), SIP (macOS) |
| **Logs** | 7-day event log summary (Critical / Error / Warning counts, top 10 error sources, 20 most recent critical/error events) for System & Application logs; failed login attempts |
| **Findings** | Automated risk findings with severity ratings |
| **Risk Score** | Weighted score (0–100) with level: low / medium / high / critical |

---

## Requirements

- Python 3.10 or newer
- Windows 10/11 or macOS (Windows Server supported)

---

## Installation

```cmd
# 1. Clone / copy this project
cd it-snapshot

# 2. Create a virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Usage

```cmd
# Basic run — writes report.json + report.html in the current directory
python main.py

# JSON only
python main.py --format json

# HTML only
python main.py --format html

# Custom base output path
python main.py --output C:\reports\snapshot

# Compact (minified) JSON
python main.py --no-pretty

# POST JSON to a remote endpoint
python main.py --mode post --post-url https://server/api/snapshots --api-key TOKEN

# Copy JSON to a network share
python main.py --mode share --share-path \\server\reports

# Show version
python main.py --version

# Help
python main.py --help
```

### Options

| Flag | Default | Description |
|---|---|---|
| `--output`, `-o` | `report` | Base path for output files (`report` → `report.json` + `report.html`) |
| `--format` | `both` | Output format: `json`, `html`, or `both` |
| `--mode` | `local` | Delivery mode: `local`, `post`, or `share` |
| `--post-url` | — | URL to POST the JSON report to (required with `--mode=post`) |
| `--api-key` | — | Bearer token for the Authorization header when posting |
| `--share-path` | — | UNC or local path to copy the JSON to (required with `--mode=share`) |
| `--dry-run` | false | Skip privileged / external commands; return empty stubs (useful for testing) |
| `--no-pretty` | false | Write compact JSON without indentation |
| `--version`, `-v` | — | Show version and exit |

---

## Findings & Risk Scoring

The agent automatically evaluates the collected data against a set of rules and produces a risk score.

| ID | Severity | Rule |
|---|---|---|
| `SEC-001` | High | No active antivirus detected |
| `SEC-002` | High | UAC disabled |
| `SEC-003` | High | Public firewall profile disabled |
| `SEC-004` | Medium | BitLocker not active on all volumes |
| `SEC-005` | Medium / High | 5+ / 10+ failed login attempts |
| `SYS-001` | Medium / High | System uptime > 30 / > 60 days |
| `SYS-002` | Medium / High | Disk > 90% / > 95% full |

**Risk score** = sum of finding weights (low=5, medium=15, high=30, critical=50), capped at 100.
**Levels**: 0–10 = low · 11–30 = medium · 31–60 = high · 61+ = critical

---

## Sample output (`report.json`)

```json
{
  "schema_version": "2.0",
  "agent_version": "2.0.0",
  "run_id": "e3b0c442-98fc-1c14-9afb-5e3e3b6e4f2a",
  "collected_at": "2026-02-26T10:30:00+00:00",
  "device_identity": {
    "hostname": "DESKTOP-ABC123",
    "fqdn": "DESKTOP-ABC123.corp.example.com",
    "domain": "corp.example.com",
    "os_machine_id": "a1b2c3d4-...",
    "primary_macs": ["aa:bb:cc:dd:ee:ff"]
  },
  "hardware": {
    "cpu": { "brand": "Intel Core i7-1185G7", "physical_cores": 4, "logical_cores": 8, "max_frequency_mhz": 3000.0 },
    "ram": {
      "total_gb": 32.0, "available_gb": 18.4, "used_gb": 13.6, "percent_used": 42.5,
      "modules": [
        { "slot": "ChannelA-DIMM0", "capacity_gb": 16.0, "speed_mhz": 3200, "manufacturer": "Micron", "part_number": "MT53E1G32D4NQ-046" }
      ]
    },
    "gpu": [{ "name": "NVIDIA RTX 4060", "driver_version": "31.0.15.3179", "vram_mb": 8192 }],
    "bios": { "manufacturer": "Dell Inc.", "version": "1.15.0", "release_date": "20250101000000.000000+000" },
    "motherboard": { "manufacturer": "Dell Inc.", "product": "0ABC12", "serial": "XYZ789" },
    "tpm": { "present": true, "version": "2.0" },
    "secure_boot_enabled": true
  },
  "physical_disks": [
    { "model": "Samsung MZVL21T0HCLR", "serial": "S64ENX0T123456", "media_type": "SSD", "interface": "NVMe", "size_gb": 953.86 }
  ],
  "storage": [
    {
      "drive_letter": "C:\\", "fstype": "NTFS",
      "total_gb": 476.84, "used_gb": 210.5, "free_gb": 266.34, "percent_used": 44.1,
      "status": "ok", "bitlocker_status": "FullyEncrypted", "bitlocker_protection": "On"
    }
  ],
  "os_detail": {
    "edition": "Windows 11 Pro", "version": "10.0.22631", "build": "22631",
    "patches": { "count": 5, "last_installed": "2026-02-20", "hotfixes": ["KB5034765", "KB5032189"] }
  },
  "findings": [
    { "id": "SEC-001", "severity": "high", "title": "No active antivirus detected", "detail": "..." }
  ],
  "risk_score": { "score": 30, "level": "medium", "factors": ["SEC-001"] },
  "snapshot": { "generated_at_utc": "2026-02-26T10:30:00+00:00", "tool_version": "2.0.0" },
  "os": { "hostname": "DESKTOP-ABC123", "os": { "name": "Windows", "release": "11" }, "..." : "..." },
  "reboot": { "last_boot_utc": "2026-02-19T08:00:00+00:00", "uptime": { "days": 7, "human_readable": "7d 2h 30m 0s" } },
  "disks": []
}
```

> **Backward compatibility**: the legacy `snapshot`, `os`, `reboot`, and `disks` keys from v1.0.0 are always present in the output with their original structure.

---

## Project structure

```
it-snapshot/
├── src/
│   ├── __init__.py                   # version = "2.0.0"
│   ├── cli.py                        # Argument parsing & orchestration
│   ├── collectors/
│   │   ├── base.py                   # BaseCollector + CollectorResult
│   │   ├── common/                   # Cross-platform: hardware, storage, network, uptime
│   │   ├── windows/                  # Windows: device_identity, hardware, storage, os_info, software, security, network, logs
│   │   └── macos/                    # macOS: device_identity, hardware, software, security, network, logs
│   ├── models/
│   │   └── schema.py                 # Pydantic v2 models
│   └── report/
│       ├── findings.py               # Findings engine & risk scoring
│       ├── json_reporter.py          # JSON output
│       └── html_reporter.py          # Self-contained HTML output
├── main.py                           # Entry point
├── requirements.txt                  # psutil, pydantic, requests
└── README.md
```

---

## Running tests

```cmd
pip install pytest
pytest tests/ -v
```

77 tests cover the findings engine, Pydantic schema validation, and Windows collector JSON parsing (all PowerShell calls are mocked — no elevated privileges required).

---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Fatal error (report could not be written, invalid arguments) |
