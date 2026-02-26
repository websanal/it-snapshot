# it-snapshot

A lightweight Windows CLI tool that collects a point-in-time IT snapshot of a machine and outputs a structured `report.json`.

## What it collects

| Category | Details |
|---|---|
| **OS** | Name, version, release, build number |
| **Hardware** | Hostname, architecture, CPU cores & frequency, RAM |
| **Disks** | All partitions — total / used / free / % for each |
| **Uptime** | Last reboot timestamp (UTC) and human-readable uptime |

---

## Requirements

- Python 3.10 or newer
- Windows 10 / 11 (works on Windows Server too)

---

## Installation

```cmd
# 1. Clone / copy this project
cd it-snapshot

# 2. Create a virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Usage

```cmd
# Basic run — writes report.json in the current directory
python main.py

# Custom output path
python main.py --output C:\reports\snapshot.json

# Compact (minified) JSON
python main.py --no-pretty

# Show version
python main.py --version

# Help
python main.py --help
```

### Options

| Flag | Default | Description |
|---|---|---|
| `--output`, `-o` | `report.json` | Output file path |
| `--no-pretty` | false | Write compact JSON (no indentation) |
| `--version`, `-v` | — | Show version and exit |

---

## Sample output (`report.json`)

```json
{
  "snapshot": {
    "generated_at_utc": "2026-02-26T10:30:00+00:00",
    "tool_version": "1.0.0"
  },
  "os": {
    "hostname": "DESKTOP-ABC123",
    "os": {
      "name": "Windows",
      "version": "10.0.22631",
      "release": "11",
      "build": "10.0.22631"
    },
    "architecture": "AMD64",
    "processor": "Intel64 Family 6 ...",
    "cpu": {
      "physical_cores": 8,
      "logical_cores": 16,
      "max_frequency_mhz": 3600.0,
      "current_frequency_mhz": 2400.0
    },
    "ram": {
      "total_gb": 32.0,
      "available_gb": 18.4,
      "used_gb": 13.6,
      "percent_used": 42.5
    },
    "python_version": "3.12.0",
    "current_user": "john.doe"
  },
  "reboot": {
    "last_boot_utc": "2026-02-25T08:00:00+00:00",
    "snapshot_utc": "2026-02-26T10:30:00+00:00",
    "uptime": {
      "total_seconds": 95400,
      "days": 1,
      "hours": 2,
      "minutes": 30,
      "seconds": 0,
      "human_readable": "1d 2h 30m 0s"
    }
  },
  "disks": [
    {
      "device": "C:\\",
      "mountpoint": "C:\\",
      "fstype": "NTFS",
      "opts": "rw,fixed",
      "total_gb": 476.84,
      "used_gb": 210.5,
      "free_gb": 266.34,
      "percent_used": 44.1,
      "status": "ok"
    }
  ]
}
```

---

## Project structure

```
it-snapshot/
├── it_snapshot/
│   ├── __init__.py
│   ├── cli.py               # Argument parsing & orchestration
│   ├── reporter.py          # Report assembly & JSON output
│   └── collectors/
│       ├── __init__.py
│       ├── os_info.py       # OS + hardware info
│       ├── disk_usage.py    # Disk partition usage
│       └── reboot_time.py   # Last boot / uptime
├── main.py                  # Entry point
├── requirements.txt
└── README.md
```

---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | A collector failed or the report could not be written |
