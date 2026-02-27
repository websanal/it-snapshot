"""Agent configuration loader for it-snapshot.

Resolution order (first match wins):
  1. --config <path> CLI flag (explicit_path argument)
  2. IT_SNAPSHOT_CONFIG environment variable
  3. UNC path: \\<server>\\it-snapshot$\\config\\agent.yaml  (Windows only)
     The UNC server is read from IT_SNAPSHOT_UNC_SERVER env var.
  4. Local system fallback:
       Windows: %PROGRAMDATA%\\it-snapshot\\agent.yaml
       macOS:   /Library/Application Support/it-snapshot/agent.yaml
       Linux:   /etc/it-snapshot/agent.yaml

UNC caching:
  When the UNC path is reachable the file is copied to the local fallback path
  as a cache. When the UNC is unreachable the cached copy is used so agents
  continue to run on the last known config during network outages.

Placeholder expansion:
  String values in the config may contain %VARNAME% tokens (Windows env-var
  style). These are expanded using the current process environment.
  Example: share_path: \\\\fileserver\\reports\\%COMPUTERNAME%
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any


# Environment variable names
_UNC_SERVER_ENV = "IT_SNAPSHOT_UNC_SERVER"
_CONFIG_ENV     = "IT_SNAPSHOT_CONFIG"

# Default config schema with all supported keys and their default values.
_DEFAULTS: dict[str, Any] = {
    "mode":       None,   # local | post | share
    "post_url":   None,
    "api_key":    None,
    "share_path": None,   # supports %COMPUTERNAME% placeholder
    "collect": {
        "logs_level":     "warning",
        "software_list":  True,
        "security":       True,
        "startup_items":  True,
    },
    "privacy": {
        "sanitize_logs":              False,
        "truncate_event_message_len": 500,
        "mask_user_paths":            False,
    },
    "intervals": {
        "run_on_startup":        False,
        "min_hours_between_runs": 0,   # 0 = no throttling
    },
    "output_dir": None,
}


# ── path helpers ──────────────────────────────────────────────────────────────

def _local_config_dir() -> Path:
    """Return the platform-specific directory for local config / state files."""
    if sys.platform == "win32":
        base = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        return Path(base) / "it-snapshot"
    elif sys.platform == "darwin":
        return Path("/Library/Application Support/it-snapshot")
    else:
        return Path("/etc/it-snapshot")


def _local_config_path() -> Path:
    return _local_config_dir() / "agent.yaml"


def _unc_config_path() -> Path | None:
    """Return the UNC config path if IT_SNAPSHOT_UNC_SERVER is set (Windows only)."""
    if sys.platform != "win32":
        return None
    server = os.environ.get(_UNC_SERVER_ENV)
    if not server:
        return None
    return Path(f"\\\\{server}\\it-snapshot$\\config\\agent.yaml")


# ── YAML loading ──────────────────────────────────────────────────────────────

def _load_yaml(path: Path) -> dict:
    """Load a YAML file and return its top-level mapping."""
    import yaml  # pyyaml - already a project dependency
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a YAML mapping, got {type(data).__name__}: {path}")
    return data


# ── merging and expansion ─────────────────────────────────────────────────────

def _deep_merge(base: dict, override: dict) -> dict:
    """Return a new dict with override merged recursively into base."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


_PLACEHOLDER_RE = re.compile(r"%([A-Za-z0-9_]+)%")


def _build_expansion_map() -> dict[str, str]:
    """Build a token → value map covering Windows env vars and macOS equivalents.

    Supported tokens (case-insensitive lookup not used — match exact case as
    the OS provides):

    Token               Windows source          macOS / Linux equivalent
    ──────────────────  ──────────────────────  ──────────────────────────────
    %COMPUTERNAME%      env COMPUTERNAME        socket.gethostname()
    %USERNAME%          env USERNAME            env USER / getpass.getuser()
    %USERDOMAIN%        env USERDOMAIN          env USERDOMAIN / hostname stem
    %PROGRAMDATA%       env PROGRAMDATA         n/a (returned as-is)
    %USERPROFILE%       env USERPROFILE         env HOME / Path.home()
    %TEMP%              env TEMP                env TMPDIR / /tmp
    %SYSTEMROOT%        env SystemRoot          n/a
    (any other env var) os.environ.get(name)    os.environ.get(name)
    """
    import getpass
    import socket
    from pathlib import Path

    mapping: dict[str, str] = dict(os.environ)  # start with all env vars

    # Ensure COMPUTERNAME is always populated (macOS / Linux don't set it)
    if "COMPUTERNAME" not in mapping:
        mapping["COMPUTERNAME"] = socket.gethostname().split(".")[0].upper()

    # Ensure USERNAME is always populated
    if "USERNAME" not in mapping:
        try:
            mapping["USERNAME"] = getpass.getuser()
        except Exception:
            mapping["USERNAME"] = "unknown"

    # Ensure USERDOMAIN is always populated
    if "USERDOMAIN" not in mapping:
        # Use the hostname stem as a reasonable stand-in on non-domain machines
        mapping["USERDOMAIN"] = socket.gethostname().split(".")[0].upper()

    # Ensure USERPROFILE / HOME are cross-populated
    if "USERPROFILE" not in mapping and "HOME" in mapping:
        mapping["USERPROFILE"] = mapping["HOME"]
    if "HOME" not in mapping and "USERPROFILE" in mapping:
        mapping["HOME"] = mapping["USERPROFILE"]

    # Ensure TEMP is available
    if "TEMP" not in mapping:
        import tempfile
        mapping["TEMP"] = tempfile.gettempdir()

    return mapping


def _expand_placeholder(value: str, _map: dict[str, str] | None = None) -> str:
    """Expand %VARNAME% tokens using the platform-normalised expansion map.

    Args:
        value: String potentially containing ``%VARNAME%`` tokens.
        _map:  Pre-built expansion map. Built lazily on first call if omitted.

    Returns:
        String with all recognised tokens replaced. Unknown tokens are left
        unchanged (e.g. ``%UNKNOWN%`` stays ``%UNKNOWN%``).
    """
    if _map is None:
        _map = _build_expansion_map()

    def _replace(m: re.Match) -> str:
        return _map.get(m.group(1), m.group(0))

    return _PLACEHOLDER_RE.sub(_replace, value)


def _expand_strings(obj: Any, _map: dict[str, str] | None = None) -> None:
    """Recursively expand %VARNAME% placeholders in all string values (in-place).

    The expansion map is built once per call tree and reused for efficiency.
    """
    if _map is None:
        _map = _build_expansion_map()
    if isinstance(obj, dict):
        for key, val in obj.items():
            if isinstance(val, str):
                obj[key] = _expand_placeholder(val, _map)
            else:
                _expand_strings(val, _map)
    elif isinstance(obj, list):
        for i, val in enumerate(obj):
            if isinstance(val, str):
                obj[i] = _expand_placeholder(val, _map)
            else:
                _expand_strings(val, _map)


# ── public API ────────────────────────────────────────────────────────────────

def load_config(explicit_path: str | None = None) -> dict:
    """Load, validate, and return the resolved agent configuration dict.

    Args:
        explicit_path: Path passed via ``--config``. When provided, this is
            used exclusively and an error is raised if the file is missing.
            If ``None`` the auto-resolution chain is used.

    Returns:
        Config dict deeply merged over ``_DEFAULTS``.  All ``%VARNAME%``
        placeholders in string values are expanded.

    Raises:
        FileNotFoundError: If ``explicit_path`` is given but does not exist.
        ValueError: If the YAML file is not a mapping.
    """
    raw: dict = {}

    if explicit_path is not None:
        p = Path(explicit_path)
        if not p.exists():
            raise FileNotFoundError(f"Config file not found: {p}")
        raw = _load_yaml(p)

    else:
        # 1. Environment variable override
        env_path_str = os.environ.get(_CONFIG_ENV)
        if env_path_str:
            env_p = Path(env_path_str)
            if env_p.exists():
                raw = _load_yaml(env_p)
            else:
                print(
                    f"  [config] Warning: {_CONFIG_ENV} points to missing file: {env_p}",
                    flush=True,
                )

        if not raw:
            # 2. UNC path (Windows only) with local cache fallback
            unc   = _unc_config_path()
            local = _local_config_path()

            if unc is not None:
                try:
                    raw = _load_yaml(unc)
                    # Update the local cache while the UNC is reachable
                    try:
                        local.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(unc), str(local))
                    except Exception:
                        pass  # Cache update failure is non-fatal
                    print(f"  [config] Loaded from UNC: {unc}", flush=True)
                except Exception:
                    # UNC unreachable - fall through to local cache
                    if local.exists():
                        try:
                            raw = _load_yaml(local)
                            print(
                                f"  [config] UNC unreachable; using cached config: {local}",
                                flush=True,
                            )
                        except Exception:
                            pass

            # 3. Local fallback (no UNC configured, or UNC and cache both failed)
            if not raw and local.exists():
                try:
                    raw = _load_yaml(local)
                    print(f"  [config] Loaded from local: {local}", flush=True)
                except Exception:
                    pass

    # Merge user config over built-in defaults
    config = _deep_merge(_DEFAULTS, raw)

    # Expand %VARNAME% placeholders in all string values
    _expand_strings(config)

    return config
