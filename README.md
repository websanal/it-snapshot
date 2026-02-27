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
| **Physical Disks** | Model, serial number, media type (SSD/HDD), interface (NVMe/SATA/USB/BusProtocol), size |
| **Storage** | All partitions — drive letter, filesystem, total / used / free / %, BitLocker (Windows) / FileVault (macOS) status |
| **OS Detail** | Edition, version, build number, last boot; Windows: hotfix KB list + last installed date, local Administrators; macOS: softwareupdate history, admin group members |
| **Network** | Per-adapter detail: MAC, link speed, IP / IPv6 addresses, DNS servers, default gateway; active Wi-Fi SSID |
| **Software** | Full installed software list with version and publisher; Windows: startup entries (registry Run keys & startup folders); macOS: /Applications scan (Info.plist) + pkgutil package count |
| **Security** | Antivirus, firewall profiles, UAC, BitLocker / FileVault, Windows Defender, Secure Boot, Gatekeeper (macOS), SIP (macOS) |
| **Logs** | Windows: 7-day event log summary (Critical / Error / Warning counts, top 10 sources, 20 most recent events); macOS: last-hour unified log errors/faults + failed authentication attempts |
| **Findings** | Automated risk findings with severity ratings |
| **Risk Score** | Weighted score (0–100) with level: low / medium / high / critical |

---

## Requirements

- Python 3.10 or newer
- Windows 10/11 or macOS (Windows Server supported)

### macOS permissions

Some collectors require elevated access or specific permissions:

| Collector | Command | Required access |
|---|---|---|
| FileVault status | `fdesetup status` | May require `sudo` on managed devices |
| System Integrity Protection | `csrutil status` | Read-only — no special privilege needed |
| Gatekeeper | `spctl --status` | No special privilege needed |
| Firewall state | `socketfilterfw --getglobalstate` | No special privilege needed |
| Full disk access (logs) | `log show` | May require **Full Disk Access** in System Settings → Privacy |
| Software update history | `softwareupdate --history` | No special privilege needed |

If `log show` returns empty results, grant **Full Disk Access** to Terminal (or the Python executable) in **System Settings → Privacy & Security → Full Disk Access**.

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
| `--config` | auto | Path to an agent config YAML file (see [Enterprise deployment](#enterprise-deployment)) |
| `--output`, `-o` | `report` | Base path for output files (`report` → `report.json` + `report.html`) |
| `--format` | `both` | Output format: `json`, `html`, or `both` |
| `--mode` | `local` | Delivery mode: `local`, `post`, or `share` |
| `--post-url` | — | URL to POST the JSON report to (required with `--mode=post`) |
| `--api-key` | — | Bearer token for the Authorization header when posting |
| `--share-path` | — | UNC or local path to copy the JSON to (required with `--mode=share`) |
| `--maintenance` | — | Generate a maintenance plan: `plan` → writes `maintenance_plan.json` |
| `--dry-run` | false | Skip privileged / external commands; return empty stubs (useful for testing) |
| `--no-pretty` | false | Write compact JSON without indentation |
| `--version`, `-v` | — | Show version and exit |

---

## Enterprise deployment

### Agent configuration file

For fleet deployments you can place a YAML config file in a central location
instead of passing CLI flags to every machine individually. The agent resolves
the config using the following priority order (first match wins):

1. `--config <path>` CLI flag
2. `IT_SNAPSHOT_CONFIG` environment variable (full path to YAML file)
3. UNC path: `\\<IT_SNAPSHOT_UNC_SERVER>\it-snapshot$\config\agent.yaml` (Windows only — set `IT_SNAPSHOT_UNC_SERVER` to your file server hostname)
4. Local fallback: `%PROGRAMDATA%\it-snapshot\agent.yaml` (Windows) or `/Library/Application Support/it-snapshot/agent.yaml` (macOS)

**UNC caching** — when a UNC config is successfully read it is copied to the
local fallback path. If the file server is unreachable on a subsequent run the
agent falls back to this cached copy automatically.

#### Full config reference (`agent.yaml`)

```yaml
# Delivery mode: local | post | share
# Equivalent to --mode. CLI flag takes priority.
mode: local

# POST delivery (mode: post)
post_url: https://it-management.corp.example.com/api/snapshots
api_key:  YOUR_BEARER_TOKEN

# Share delivery (mode: share)
# %COMPUTERNAME% is expanded to the machine hostname at runtime.
share_path: \\fileserver\it-snapshot$\reports\%COMPUTERNAME%

# Output directory for local mode.
# %COMPUTERNAME% expansion supported.
output_dir: C:\IT\snapshots\%COMPUTERNAME%

# What to collect
collect:
  logs_level: warning        # minimum event level: info | warning | error | critical
  software_list: true        # include installed software list
  security: true             # include security / AV / firewall data
  startup_items: true        # include startup entries and scheduled tasks

# Privacy controls
privacy:
  sanitize_logs: false                  # strip usernames from log messages
  truncate_event_message_len: 500       # max characters per event message (0 = unlimited)
  mask_user_paths: false                # replace C:\Users\<name>\ with C:\Users\<user>\

# Run frequency throttling
intervals:
  run_on_startup: false          # run automatically when the user logs in (informational)
  min_hours_between_runs: 24     # skip the run if last run was less than N hours ago
                                 # set to 0 to disable throttling (default)
```

> String values support `%VARNAME%` placeholder expansion using the current
> process environment (e.g. `%COMPUTERNAME%`, `%USERNAME%`, `%PROGRAMDATA%`).

### Run-interval gate

When `intervals.min_hours_between_runs` is set to a positive value the agent
stores a timestamp in `%PROGRAMDATA%\it-snapshot\run_state.json` (Windows) or
`/Library/Application Support/it-snapshot/run_state.json` (macOS) after each
successful run. If a subsequent invocation occurs before the minimum interval
has elapsed the agent prints a message and exits with code `0` without
collecting or writing any files.

This is useful when the agent is launched from a login script and you want to
avoid repeated collections on fast re-logins or reboots.

### Typical GPO / login-script deployment (Windows)

```cmd
REM Run via Group Policy Logon Script or scheduled task
python "\\fileserver\it-snapshot$\main.py" ^
    --config "\\fileserver\it-snapshot$\config\agent.yaml"
```

Or without a `--config` flag — set `IT_SNAPSHOT_UNC_SERVER` as a machine
environment variable in Group Policy and the agent resolves the UNC path
automatically:

```cmd
REM Computer Configuration > Preferences > Environment
IT_SNAPSHOT_UNC_SERVER = fileserver.corp.example.com

REM Then the login script needs no --config flag:
python "\\fileserver\it-snapshot$\main.py"
```

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
├── src/                              # Agent source
│   ├── __init__.py                   # version = "2.0.0"
│   ├── cli.py                        # Argument parsing & orchestration
│   ├── config/
│   │   ├── agent_config.py           # Config loader (UNC / local / env-var + caching)
│   │   └── run_state.py              # Run-interval gate & last-run timestamp
│   ├── collectors/
│   │   ├── base.py                   # BaseCollector + CollectorResult
│   │   ├── common/                   # Cross-platform: hardware, storage, network, uptime
│   │   ├── windows/                  # Windows: device_identity, hardware, storage, os_info,
│   │   │                             #   software, security, antivirus, startup, network, logs
│   │   └── macos/                    # macOS: device_identity, hardware, software, security, network, logs
│   ├── maintenance/
│   │   ├── generator.py              # Maintenance plan orchestrator (--maintenance plan)
│   │   └── analyzers/                # temp_cleanup, os_updates, startup_reduction
│   ├── models/
│   │   └── schema.py                 # Pydantic v2 models
│   ├── recommendations/
│   │   └── engine.py                 # Advisory recommendations engine
│   └── report/
│       ├── findings.py               # Findings engine & risk scoring
│       ├── unwanted_software.py      # YAML-based unwanted software matcher
│       ├── json_reporter.py          # JSON output
│       └── html_reporter.py          # Self-contained HTML output
├── server/                           # Central inventory server
│   ├── main.py                       # FastAPI app + admin UI
│   ├── auth.py                       # X-API-Key dependency
│   ├── db.py                         # SQLite init & connection helper
│   ├── models.py                     # Pydantic request / response models
│   ├── routers/
│   │   ├── ingest.py                 # POST /ingest
│   │   └── devices.py                # GET /devices, /latest, /reports
│   ├── requirements.txt              # fastapi, uvicorn, aiosqlite, pydantic
│   └── Dockerfile
├── packaging/
│   └── windows/                      # WiX v4 MSI project
│       ├── it-snapshot.wxs
│       ├── ITSnapshotAgent.xml       # Scheduled task XML
│       └── agent.yaml                # Default config installed by MSI
├── enterprise-config/                # Reference files for UNC file server
│   ├── agent.example.yaml
│   ├── unwanted_apps.yaml
│   └── README.md
├── config/
│   └── unwanted_apps.yaml            # Built-in unwanted software pattern list
├── docker-compose.yml                # Runs the inventory server
├── .env.example                      # Template for IT_SNAPSHOT_API_KEY
├── main.py                           # Agent entry point
├── requirements.txt                  # Agent: psutil, pydantic, pyyaml, requests
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

---

## Central inventory server

The `server/` directory contains a FastAPI-based inventory server that receives
reports from all agents and stores them in SQLite. It exposes a REST API and a
browser admin UI.

### API endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/ingest` | Accept a report from an agent (requires `X-API-Key` header) |
| `GET`  | `/devices` | List all known devices |
| `GET`  | `/devices/{id}/latest` | Full latest report for a device |
| `GET`  | `/devices/{id}/reports?limit=50` | Report history (summaries only) |
| `GET`  | `/health` | Health check (no auth) |
| `GET`  | `/docs` | Interactive OpenAPI docs (Swagger UI) |
| `GET`  | `/redoc` | ReDoc API reference |
| `GET`  | `/admin` | Browser admin UI |

All endpoints except `/health` require the `X-API-Key` request header.

### Quick start with Docker Compose

```bash
# 1. Generate a strong API key and put it in .env
cp .env.example .env
python -c "import secrets; print('IT_SNAPSHOT_API_KEY=' + secrets.token_urlsafe(32))" >> .env
# (or edit .env manually and set IT_SNAPSHOT_API_KEY)

# 2. Start the server
docker compose up -d

# 3. Verify
curl http://localhost:8000/health
# {"status":"ok"}

# 4. Open the admin UI
# http://localhost:8000/admin  (enter your API key in the toolbar)

# 5. Open the interactive API docs
# http://localhost:8000/docs
```

The SQLite database is stored in a named Docker volume (`inventory_data`) and
survives container restarts and image upgrades.

### Running without Docker

```bash
cd server
pip install -r requirements.txt
export IT_SNAPSHOT_API_KEY="your-secret-key"
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Configuring agents to POST reports

In the agent config file (`agent.yaml`) on each endpoint, set:

```yaml
mode: post
post_url: https://it-management.corp.example.com/api/ingest
api_key:  your-secret-key
```

> Replace `it-management.corp.example.com` with the DNS name or IP of your
> server host.  If you run behind a reverse proxy (nginx, Caddy) make sure TLS
> is terminated there — agents should use `https://` in production.

Or pass the values on the command line:

```cmd
python main.py --mode post ^
               --post-url https://inventory.corp.example.com/ingest ^
               --api-key  your-secret-key
```

### Deploying on a domain — recommended pattern

1. **Run the server** on any always-on Linux host (VM, bare metal, or a Docker
   host) reachable from all managed endpoints.

2. **Set the agent config** centrally on the UNC share
   (`\\fileserver\it-snapshot$\config\agent.yaml`):

   ```yaml
   mode: post
   post_url: https://inventory.corp.example.com/ingest
   api_key:  your-secret-key
   intervals:
     min_hours_between_runs: 24
   ```

3. **Push the agent** to endpoints via GPO Software Installation (MSI) or a
   login script. With the UNC config in place, every machine automatically
   picks it up — no per-machine configuration needed.

4. **Monitor** from the admin UI at `https://inventory.corp.example.com/admin`
   or query the API directly from your SIEM / ITSM tooling.

### Admin UI

Open `http://<server>:8000/admin` in a browser. Enter your API key in the
toolbar — it is stored only in `sessionStorage` (cleared when the tab closes)
and sent in the `X-API-Key` header directly from your browser to the server.

The UI shows:
- Device count, critical-risk count, and high-risk count
- Sortable device table with hostname, domain, OS, last-seen time, and risk level
- "Latest report" button per device that opens the full raw JSON in a modal

### Database

SQLite is used for the MVP. The database file path defaults to
`/data/db.sqlite` inside the Docker container (mapped to the `inventory_data`
named volume). Override with the `IT_SNAPSHOT_DB` environment variable.

**Schema:**

```sql
devices(id, hostname, domain, last_seen, os_name, os_version, risk_score)
reports(id, device_id, collected_at, risk_score, findings_json, raw_json, ingested_at)
```

- `devices` is an upsert table — one row per `(hostname, domain)`.
- `reports` is append-only — every ingest creates a new row, keeping full history.

---

## Packaging (Windows MSI)

### 1. Build the standalone executable with PyInstaller

```cmd
pip install pyinstaller
pyinstaller --onefile --name it-snapshot main.py
REM Output: dist\it-snapshot.exe
```

### 2. Build the MSI with WiX Toolset v4

```cmd
REM Install WiX v4 (once)
dotnet tool install --global wix

REM Build the MSI from the packaging directory
cd packaging\windows
wix build it-snapshot.wxs -o it-snapshot.msi
```

The MSI installs:

| Path | Contents |
|---|---|
| `C:\Program Files\it-snapshot\it-snapshot.exe` | Agent executable |
| `C:\Program Files\it-snapshot\ITSnapshotAgent.xml` | Scheduled task XML |
| `C:\ProgramData\it-snapshot\agent.yaml` | Default config (not overwritten on upgrade) |
| `C:\ProgramData\it-snapshot\logs\` | Empty logs directory |

The MSI also creates a scheduled task **ITSnapshotAgent** that runs the agent
as `SYSTEM` at every boot (with a 60-second delay) when a network connection is
available.

### 3. Uninstall

**Standard uninstall** (keeps state and logs):
```cmd
msiexec /x it-snapshot.msi
```

**Full cleanup** (removes `C:\ProgramData\it-snapshot\` too):
```cmd
msiexec /x it-snapshot.msi REMOVEALL=YES
```

### 4. Deploy via Active Directory (GPO Software Installation)

1. Copy `it-snapshot.msi` to a network share, e.g. `\\fileserver\GPO$\it-snapshot.msi`
2. Open **Group Policy Management** → create or edit a GPO linked to the target OU
3. Navigate to **Computer Configuration → Policies → Software Settings → Software Installation**
4. Right-click → **New → Package** → select the MSI from the UNC path
5. Choose **Assigned** deployment — the MSI installs on next boot/logon

> **Tip**: Set `IT_SNAPSHOT_UNC_SERVER` as a Computer environment variable in
> the same GPO (**Computer Configuration → Preferences → Windows Settings →
> Environment**). Agents will then automatically load the central config from
> the file server and fall back to the local copy when offline.

---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success (or interval gate skipped the run — see `min_hours_between_runs`) |
| `1` | Fatal error (report could not be written, invalid arguments, config file not found) |
