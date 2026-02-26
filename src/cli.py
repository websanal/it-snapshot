"""Command-line interface and orchestration for it-snapshot v2."""

from __future__ import annotations

import argparse
import datetime
import os
import platform
import shutil
import socket
import sys
import uuid
from pathlib import Path

from . import __version__


# ── argument parsing ──────────────────────────────────────────────────────────

def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="it-snapshot",
        description="Cross-platform endpoint inventory agent (v2).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py\n"
            "  python main.py --format json --output snap\n"
            "  python main.py --mode post --post-url https://server/api --api-key TOKEN\n"
            "  python main.py --mode share --share-path \\\\server\\reports\n"
        ),
    )
    parser.add_argument(
        "--output", "-o",
        default="report",
        metavar="PATH",
        help="Base path for output files (default: report -> report.json + report.html)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "html", "both"],
        default="both",
        help="Output format (default: both)",
    )
    parser.add_argument(
        "--mode",
        choices=["local", "post", "share"],
        default="local",
        help="Delivery mode (default: local)",
    )
    parser.add_argument(
        "--post-url",
        metavar="URL",
        help="URL to POST the JSON report to (required when --mode=post)",
    )
    parser.add_argument(
        "--api-key",
        metavar="KEY",
        help="Bearer token for Authorization header when posting",
    )
    parser.add_argument(
        "--share-path",
        metavar="PATH",
        help="UNC or local path to copy JSON to (required when --mode=share)",
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


# ── output path resolution ────────────────────────────────────────────────────

def _resolve_paths(output_arg: str) -> tuple[Path, Path]:
    """Return (json_path, html_path) from --output value."""
    p = Path(output_arg)
    stem = p.with_suffix("") if p.suffix.lower() in (".json", ".html") else p
    return stem.with_suffix(".json"), stem.with_suffix(".html")


# ── legacy v1 collector helpers ───────────────────────────────────────────────

def _collect_legacy_os() -> dict:
    uname = platform.uname()
    import psutil
    cpu_freq = psutil.cpu_freq()
    ram = psutil.virtual_memory()
    return {
        "hostname": socket.gethostname(),
        "os": {
            "name": uname.system,
            "version": uname.version,
            "release": uname.release,
            "build": platform.version(),
        },
        "architecture": uname.machine,
        "processor": uname.processor or platform.processor(),
        "cpu": {
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
            "max_frequency_mhz": round(cpu_freq.max, 2) if cpu_freq else None,
            "current_frequency_mhz": round(cpu_freq.current, 2) if cpu_freq else None,
        },
        "ram": {
            "total_gb": round(ram.total / (1024 ** 3), 2),
            "available_gb": round(ram.available / (1024 ** 3), 2),
            "used_gb": round(ram.used / (1024 ** 3), 2),
            "percent_used": ram.percent,
        },
        "python_version": platform.python_version(),
        "current_user": os.environ.get("USERNAME") or os.environ.get("USER", "unknown"),
    }


# ── platform collector factory ────────────────────────────────────────────────

def _load_platform_collectors():
    """Return platform-specific collector instances."""
    if sys.platform == "win32":
        from .collectors.windows.device_identity import DeviceIdentityCollector
        from .collectors.windows.hardware import HardwareCollector as WinHW
        from .collectors.windows.software import SoftwareCollector
        from .collectors.windows.security import SecurityCollector
        from .collectors.windows.network import NetworkCollector as WinNet
        from .collectors.windows.logs import LogsCollector
        return [
            ("device_identity", DeviceIdentityCollector()),
            ("_win_hardware",   WinHW()),
            ("software",        SoftwareCollector()),
            ("security",        SecurityCollector()),
            ("_win_network",    WinNet()),
            ("logs",            LogsCollector()),
        ]
    elif sys.platform == "darwin":
        from .collectors.macos.device_identity import DeviceIdentityCollector
        from .collectors.macos.hardware import HardwareCollector as MacHW
        from .collectors.macos.software import SoftwareCollector
        from .collectors.macos.security import SecurityCollector
        from .collectors.macos.network import NetworkCollector as MacNet
        from .collectors.macos.logs import LogsCollector
        return [
            ("device_identity", DeviceIdentityCollector()),
            ("_mac_hardware",   MacHW()),
            ("software",        SoftwareCollector()),
            ("security",        SecurityCollector()),
            ("_mac_network",    MacNet()),
            ("logs",            LogsCollector()),
        ]
    else:
        return []


# ── report assembly ───────────────────────────────────────────────────────────

def _assemble_report(
    common_hw: dict,
    common_storage: dict,
    common_net: dict,
    uptime: dict,
    platform_results: dict,
    legacy_os: dict,
    all_errors: list[str],
) -> dict:
    from .report.findings import compute_findings

    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Merge hardware: common psutil + platform-specific GPU/BIOS/mobo
    hw_section = {
        "cpu": common_hw.get("cpu"),
        "ram": common_hw.get("ram"),
        "gpu": [],
        "bios": {},
        "motherboard": {},
    }
    for key in ("_win_hardware", "_mac_hardware"):
        plat_hw = platform_results.get(key, {})
        if plat_hw:
            hw_section["gpu"] = plat_hw.get("gpu", [])
            hw_section["bios"] = plat_hw.get("bios", {})
            hw_section["motherboard"] = plat_hw.get("motherboard", {})

    # Merge network: common psutil interfaces + platform DNS/gateway
    net_section = {
        "interfaces": common_net.get("interfaces", []),
        "dns_servers": [],
        "default_gateway": None,
    }
    for key in ("_win_network", "_mac_network"):
        plat_net = platform_results.get(key, {})
        if plat_net:
            net_section["dns_servers"] = plat_net.get("dns_servers", [])
            net_section["default_gateway"] = plat_net.get("default_gateway")

    storage_list = common_storage.get("partitions", [])

    report: dict = {
        "schema_version": "2.0",
        "agent_version": __version__,
        "run_id": str(uuid.uuid4()),
        "collected_at": now_utc,
        # v2 sections
        "device_identity": platform_results.get("device_identity", {}),
        "hardware": hw_section,
        "storage": storage_list,
        "network": net_section,
        "software": platform_results.get("software", {"installed": [], "count": 0}),
        "security": platform_results.get("security", {}),
        "logs": platform_results.get("logs", {}),
        "findings": [],
        "risk_score": {"score": 0, "level": "low", "factors": []},
        "errors": all_errors,
        # Legacy v1 keys (exact same shape as v1)
        "snapshot": {
            "generated_at_utc": uptime.get("snapshot_utc", now_utc),
            "tool_version": __version__,
        },
        "os": legacy_os,
        "reboot": uptime,
        "disks": storage_list,
    }

    findings, risk_score = compute_findings(report)
    report["findings"] = findings
    report["risk_score"] = risk_score

    return report


# ── delivery ──────────────────────────────────────────────────────────────────

def _post_report(report: dict, url: str, api_key: str | None) -> None:
    try:
        import requests
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        resp = requests.post(url, json=report, headers=headers, timeout=30)
        resp.raise_for_status()
        print(f"  [post] Delivered to {url} -> HTTP {resp.status_code}")
    except Exception as exc:
        print(f"  [post] FAILED: {exc}", file=sys.stderr)


def _share_report(json_path: Path, share_path: str) -> None:
    try:
        dest = Path(share_path)
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / json_path.name
        shutil.copy(str(json_path), str(target))
        print(f"  [share] Copied to {target}")
    except Exception as exc:
        print(f"  [share] FAILED: {exc}", file=sys.stderr)


# ── main entry point ──────────────────────────────────────────────────────────

def run(argv=None) -> None:
    args = parse_args(argv)

    if args.mode == "post" and not args.post_url:
        print("[error] --post-url is required when --mode=post", file=sys.stderr)
        sys.exit(1)
    if args.mode == "share" and not args.share_path:
        print("[error] --share-path is required when --mode=share", file=sys.stderr)
        sys.exit(1)

    json_path, html_path = _resolve_paths(args.output)
    pretty = not args.no_pretty

    print("[it-snapshot] Collecting system information...")

    from .collectors.common.hardware import HardwareCollector
    from .collectors.common.storage import StorageCollector
    from .collectors.common.network import NetworkCollector
    from .collectors.common.uptime import UptimeCollector

    all_errors: list[str] = []

    # Common collectors
    common_hw_result   = HardwareCollector().collect()
    common_stor_result = StorageCollector().collect()
    common_net_result  = NetworkCollector().collect()
    uptime_result      = UptimeCollector().collect()

    for r in (common_hw_result, common_stor_result, common_net_result, uptime_result):
        all_errors.extend(r.errors)

    # Legacy OS info
    legacy_os: dict = {}
    try:
        print("  - OS info...", end=" ", flush=True)
        legacy_os = _collect_legacy_os()
        print("done")
    except Exception as exc:
        print(f"FAILED ({exc})")
        all_errors.append(f"legacy_os: {exc}")

    # Platform-specific collectors
    platform_collectors = _load_platform_collectors()
    platform_results: dict = {}

    for label, collector in platform_collectors:
        display = label.lstrip("_")
        print(f"  - {display}...", end=" ", flush=True)
        result = collector.collect()
        if result.errors:
            print(f"partial ({'; '.join(result.errors[:2])})")
            all_errors.extend(result.errors)
        else:
            print("done")
        platform_results[label] = result.data

    print("  - Assembling report...", end=" ", flush=True)
    report = _assemble_report(
        common_hw=common_hw_result.data,
        common_storage=common_stor_result.data,
        common_net=common_net_result.data,
        uptime=uptime_result.data,
        platform_results=platform_results,
        legacy_os=legacy_os,
        all_errors=all_errors,
    )
    print("done")

    # Write outputs
    from .report.json_reporter import write_json
    from .report.html_reporter import write_html

    if args.format in ("json", "both"):
        write_json(report, json_path, pretty=pretty)
        print(f"\n[it-snapshot] JSON  -> {json_path.resolve()}")

    if args.format in ("html", "both"):
        write_html(report, html_path)
        print(f"[it-snapshot] HTML  -> {html_path.resolve()}")

    # Delivery
    if args.mode == "post":
        _post_report(report, args.post_url, args.api_key)
    elif args.mode == "share":
        _share_report(json_path, args.share_path)

    # Summary
    risk = report.get("risk_score", {})
    findings_count = len(report.get("findings", []))
    errors_count = len(all_errors)
    print(
        f"\n[it-snapshot] Done. "
        f"Risk: {risk.get('level','?').upper()} ({risk.get('score',0)}/100) | "
        f"Findings: {findings_count} | "
        f"Collection errors: {errors_count}"
    )
