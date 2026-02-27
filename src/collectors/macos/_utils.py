"""macOS-specific utility functions."""

import json
import subprocess

# When True, run_cmd() returns empty stubs instead of executing real commands.
# Set by CLI --dry-run flag before collectors run.
DRY_RUN: bool = False


def run_cmd(cmd: list[str], timeout: int = 30) -> str:
    """Run a command and return stdout as a string.

    Returns '' immediately when DRY_RUN is True.
    Never raises — returns '' on any failure.
    """
    if DRY_RUN:
        return ""
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return result.stdout.decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def run_json(cmd: list[str], timeout: int = 60) -> dict | list:
    """Run a command, parse stdout as JSON.

    Returns {} on DRY_RUN or any failure.
    """
    raw = run_cmd(cmd, timeout=timeout)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}


def run_plist(cmd: list[str], timeout: int = 60) -> dict:
    """Run a command that outputs plist data and return parsed dict.

    Returns {} on DRY_RUN or any failure.
    """
    if DRY_RUN:
        return {}
    try:
        import plistlib
        result = subprocess.run(cmd, capture_output=True, timeout=timeout)
        if result.returncode != 0 or not result.stdout:
            return {}
        return plistlib.loads(result.stdout)
    except Exception:
        return {}
