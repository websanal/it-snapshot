"""Write the report as JSON."""

import json
import sys
from pathlib import Path


def write_json(report: dict, output_path: Path, pretty: bool = True) -> None:
    """Serialise report to JSON and write to output_path."""
    indent = 2 if pretty else None
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, indent=indent, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    except OSError as exc:
        print(f"[error] Could not write JSON to '{output_path}': {exc}", file=sys.stderr)
        sys.exit(1)
