"""Command-line interface for it-snapshot."""

import argparse
import sys
from pathlib import Path

from . import __version__
from .collectors import collect_disk_usage, collect_os_info, collect_reboot_time
from .reporter import build_report, write_report


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="it-snapshot",
        description="Collect a point-in-time IT snapshot of this Windows machine.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py\n"
            "  python main.py --output C:\\reports\\snapshot.json\n"
            "  python main.py --output snapshot.json --no-pretty\n"
        ),
    )
    parser.add_argument(
        "--output", "-o",
        default="report.json",
        metavar="PATH",
        help="Destination path for the JSON report (default: report.json)",
    )
    parser.add_argument(
        "--no-pretty",
        action="store_true",
        default=False,
        help="Write compact JSON instead of indented output",
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"it-snapshot {__version__}",
    )
    return parser.parse_args(argv)


def run(argv=None) -> None:
    """Main entry point — collect, build, and write the report."""
    args = parse_args(argv)
    output_path = Path(args.output)

    print("[it-snapshot] Collecting system information…")

    steps = [
        ("OS info", collect_os_info),
        ("Disk usage", collect_disk_usage),
        ("Reboot time", collect_reboot_time),
    ]

    results = {}
    for label, collector in steps:
        print(f"  - {label}...", end=" ", flush=True)
        try:
            results[label] = collector()
            print("done")
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED ({exc})", file=sys.stderr)
            sys.exit(1)

    report = build_report(
        os_info=results["OS info"],
        disk_usage=results["Disk usage"],
        reboot_time=results["Reboot time"],
    )

    pretty = not args.no_pretty
    write_report(report, output_path, pretty=pretty)

    print(f"\n[it-snapshot] Report written -> {output_path.resolve()}")
