"""Run-lock and interval gate for it-snapshot.

Prevents the agent from running more frequently than the configured minimum
interval. This is useful when the agent is deployed via login script or
scheduled task and the same machine might trigger multiple runs in a short
window (e.g. rapid reboots during patching).

State file location:
  Windows: %PROGRAMDATA%\\it-snapshot\\run_state.json
  macOS:   /Library/Application Support/it-snapshot/run_state.json
  Linux:   /var/lib/it-snapshot/run_state.json

The state file is a simple JSON object::

    {
      "last_run_utc": "2026-02-27T08:00:00+00:00"
    }
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path


def _state_path() -> Path:
    """Return the platform-specific path for the run state file."""
    if sys.platform == "win32":
        import os
        base = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        return Path(base) / "it-snapshot" / "run_state.json"
    elif sys.platform == "darwin":
        return Path("/Library/Application Support/it-snapshot/run_state.json")
    else:
        return Path("/var/lib/it-snapshot/run_state.json")


def _load_state() -> dict:
    p = _state_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    p = _state_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"  [run-state] Warning: could not write state file: {exc}", flush=True)


# ── public API ────────────────────────────────────────────────────────────────

def check_interval(min_hours: float) -> tuple[bool, str]:
    """Check whether enough time has elapsed since the last successful run.

    Args:
        min_hours: Minimum number of hours required between runs.
            Pass ``0`` (or any non-positive value) to disable the gate entirely.

    Returns:
        ``(True, "")`` if the run should proceed.
        ``(False, reason)`` if the minimum interval has not elapsed, where
        *reason* is a human-readable explanation suitable for printing.
    """
    if min_hours <= 0:
        return True, ""

    state = _load_state()
    last_run_str = state.get("last_run_utc")
    if not last_run_str:
        return True, ""

    try:
        last_run = datetime.datetime.fromisoformat(last_run_str)
    except ValueError:
        # Corrupt state - allow the run so we self-heal
        return True, ""

    now = datetime.datetime.now(datetime.timezone.utc)
    # Ensure last_run is timezone-aware for comparison
    if last_run.tzinfo is None:
        last_run = last_run.replace(tzinfo=datetime.timezone.utc)

    elapsed_hours = (now - last_run).total_seconds() / 3600
    if elapsed_hours < min_hours:
        remaining = min_hours - elapsed_hours
        return False, (
            f"last run was {elapsed_hours:.1f}h ago; "
            f"minimum interval is {min_hours}h "
            f"({remaining:.1f}h remaining)."
        )

    return True, ""


def record_run() -> None:
    """Persist the current UTC timestamp as the last successful run time.

    Should be called after the report has been written successfully.
    Failures to write the state file are logged but do not raise.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
    state = _load_state()
    state["last_run_utc"] = now_utc
    _save_state(state)
