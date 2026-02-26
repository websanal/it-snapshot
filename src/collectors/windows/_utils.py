"""Windows-specific utility functions."""

import subprocess
import sys


def run_powershell(cmd: str, timeout: int = 30) -> str:
    """Run a PowerShell command and return stdout as a string.

    Raises RuntimeError on non-zero exit code.
    """
    kwargs = {
        "args": [
            "powershell",
            "-NonInteractive",
            "-ExecutionPolicy", "Bypass",
            "-Command", cmd,
        ],
        "capture_output": True,
        "text": True,
        "timeout": timeout,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW

    result = subprocess.run(**kwargs)
    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip() or f"PowerShell exited with code {result.returncode}"
        )
    return result.stdout.strip()
