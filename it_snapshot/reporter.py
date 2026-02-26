"""Build and write the final snapshot report."""

import json
import sys
from pathlib import Path


def build_report(os_info: dict, disk_usage: list, reboot_time: dict) -> dict:
    """Combine all collector outputs into a single report structure."""
    return {
        "snapshot": {
            "generated_at_utc": reboot_time["snapshot_utc"],
            "tool_version": "1.0.0",
        },
        "os": os_info,
        "reboot": reboot_time,
        "disks": disk_usage,
    }


def write_report(report: dict, output_path: Path, pretty: bool = True) -> None:
    """Serialise the report to JSON and write it to *output_path*.

    Raises:
        SystemExit: if the file cannot be written.
    """
    indent = 2 if pretty else None
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, indent=indent, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        print(f"[error] Could not write report to '{output_path}': {exc}", file=sys.stderr)
        sys.exit(1)
