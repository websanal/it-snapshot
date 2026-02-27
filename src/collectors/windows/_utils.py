"""Windows-specific utility functions."""

import ctypes
import subprocess
import sys

# When True, run_powershell() and run_command() return empty stubs instead of
# executing real commands. Set by CLI --dry-run flag before collectors run.
DRY_RUN: bool = False


def is_admin() -> bool:
    """Return True if the current process has administrator privileges."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _decode(raw: bytes) -> str:
    """Decode subprocess bytes with UTF-8; fall back to cp1252 then replace."""
    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def run_powershell(cmd: str, timeout: int = 30) -> str:
    """Run a PowerShell command and return stdout as a string.

    Returns '[]' immediately when DRY_RUN is True.
    Raises RuntimeError on non-zero exit code.
    """
    if DRY_RUN:
        return "[]"

    # Force UTF-8 output encoding so JSON is readable regardless of system locale
    full_cmd = (
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "[Console]::InputEncoding  = [System.Text.Encoding]::UTF8; "
        + cmd
    )

    kwargs: dict = {
        "args": [
            "powershell",
            "-NonInteractive",
            "-ExecutionPolicy", "Bypass",
            "-Command", full_cmd,
        ],
        "capture_output": True,
        "timeout": timeout,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW

    result = subprocess.run(**kwargs)
    stdout = _decode(result.stdout).strip()
    stderr = _decode(result.stderr).strip()

    if result.returncode != 0:
        raise RuntimeError(stderr or f"PowerShell exited with code {result.returncode}")
    return stdout


def run_command(cmd: list[str], timeout: int = 15) -> str:
    """Run an arbitrary subprocess command and return stdout.

    Returns '' immediately when DRY_RUN is True.
    Never raises — returns '' on any failure.
    """
    if DRY_RUN:
        return ""
    try:
        kwargs: dict = {
            "args": cmd,
            "capture_output": True,
            "timeout": timeout,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        result = subprocess.run(**kwargs)
        return _decode(result.stdout).strip()
    except Exception:
        return ""
