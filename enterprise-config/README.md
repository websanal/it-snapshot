# it-snapshot — Enterprise Configuration Files

This folder contains the reference configuration files intended to be hosted
on a central file server and consumed by all agents in your fleet.

---

## Files

| File | Purpose |
|---|---|
| `agent.example.yaml` | Full agent config reference with every option documented. Copy to `agent.yaml` and edit. |
| `unwanted_apps.yaml` | Software pattern list used by the unwanted-software detector. Add/remove patterns to match your environment. |

---

## Hosting on a UNC path (recommended for Windows fleets)

### 1. Create the share

On your Windows file server, create a share with a `$` suffix so it is
hidden from network browsing:

```cmd
REM Run on the file server (as Administrator)
mkdir C:\it-snapshot-config
New-SmbShare -Name "it-snapshot$" -Path "C:\it-snapshot-config" -ReadAccess "Domain Computers" -FullAccess "Domain Admins"
```

### 2. Place config files on the share

```
\\fileserver\it-snapshot$\
  config\
    agent.yaml          <- copy agent.example.yaml here, rename, and customise
    unwanted_apps.yaml  <- copy from this folder
```

### 3. Point agents at the share

**Option A — `IT_SNAPSHOT_UNC_SERVER` environment variable (recommended)**

Set the variable as a Machine environment variable via Group Policy:

```
Computer Configuration
  → Preferences
    → Windows Settings
      → Environment
        Name:  IT_SNAPSHOT_UNC_SERVER
        Value: fileserver.corp.example.com
```

The agent then resolves the UNC config path automatically:
```
\\fileserver.corp.example.com\it-snapshot$\config\agent.yaml
```

No `--config` flag is needed in your login script or scheduled task.

**Option B — `--config` CLI flag**

Pass the full UNC path explicitly:

```cmd
it-snapshot.exe --config \\fileserver\it-snapshot$\config\agent.yaml
```

**Option C — `IT_SNAPSHOT_CONFIG` environment variable**

Set the full path (local or UNC) as an environment variable:

```
IT_SNAPSHOT_CONFIG = \\fileserver\it-snapshot$\config\agent.yaml
```

---

## Config resolution order

The agent checks the following in order, stopping at the first match:

1. `--config <path>` CLI flag
2. `IT_SNAPSHOT_CONFIG` environment variable
3. `\\<IT_SNAPSHOT_UNC_SERVER>\it-snapshot$\config\agent.yaml` (Windows)
4. Local fallback:
   - Windows: `%PROGRAMDATA%\it-snapshot\agent.yaml`
   - macOS: `/Library/Application Support/it-snapshot/agent.yaml`

### UNC caching (offline resilience)

When the agent successfully reads a UNC config it saves a copy to the local
fallback path. If the file server is unreachable on a subsequent run the agent
uses this cached copy and continues normally. The cache is refreshed every time
the UNC path is reachable.

---

## Placeholder expansion

String values in `agent.yaml` may contain `%VARNAME%` tokens. The following
tokens are expanded at runtime on **all platforms**:

| Token | Example value | Notes |
|---|---|---|
| `%COMPUTERNAME%` | `DESKTOP-ABC123` | `COMPUTERNAME` env var on Windows; `socket.gethostname()` on macOS/Linux |
| `%USERNAME%` | `jsmith` | `USERNAME` on Windows; `USER` env var / `getpass.getuser()` on macOS/Linux |
| `%USERDOMAIN%` | `CORP` | `USERDOMAIN` on Windows; hostname stem on macOS/Linux |
| `%USERPROFILE%` | `C:\Users\jsmith` | `USERPROFILE` on Windows; `HOME` on macOS/Linux |
| `%PROGRAMDATA%` | `C:\ProgramData` | Windows only (kept as-is on other platforms) |
| `%TEMP%` | varies | `TEMP` / `TMPDIR` env var or `/tmp` |
| `%SYSTEMROOT%` | `C:\Windows` | Windows only |
| `%<any env var>%` | (current value) | Any variable in the agent process environment |

Unknown tokens (no matching env var) are left unchanged in the string.

**Example — per-machine output directory:**

```yaml
output_dir: \\fileserver\it-snapshot$\reports\%COMPUTERNAME%
```

At runtime on `DESKTOP-ABC123` this becomes:
```
\\fileserver\it-snapshot$\reports\DESKTOP-ABC123
```

---

## Customising the unwanted software list

Edit `unwanted_apps.yaml` to add or remove patterns:

```yaml
patterns:
  - name: "MyApp"           # case-insensitive substring match
    category: "Remote Access"
    reason: "Verify this is explicitly authorised"
    severity: medium        # low | medium | high  (default: medium)
```

Point the agent at your customised copy by setting `IT_SNAPSHOT_CONFIG` or
`--config` to the YAML file path. The `unwanted_apps.yaml` path is controlled
separately — to use a custom location set the `IT_SNAPSHOT_UNWANTED_APPS`
environment variable or pass the path in agent config if your deployment
supports it.

> The built-in copy at `config/unwanted_apps.yaml` in the repository is used
> as the default when no custom path is provided.
