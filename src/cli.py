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
            "  python main.py --dry-run\n"
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
        "--dry-run",
        action="store_true",
        default=False,
        help=(
            "Skip all privileged/external commands (PowerShell, netsh). "
            "Registry and psutil reads still run. Useful for testing."
        ),
    )
    parser.add_argument(
        "--maintenance",
        choices=["plan"],
        metavar="ACTION",
        default=None,
        help=(
            "Generate a maintenance plan alongside the report. "
            "Supported action: 'plan'. "
            "Writes maintenance_plan.json next to the report output. "
            "No changes are applied to the system (read-only, advisory only)."
        ),
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"it-snapshot {__version__}",
    )
    return parser.parse_args(argv)


# ── output path resolution ────────────────────────────────────────────────────

def _resolve_paths(output_arg: str) -> tuple[Path, Path]:
    p = Path(output_arg)
    stem = p.with_suffix("") if p.suffix.lower() in (".json", ".html") else p
    return stem.with_suffix(".json"), stem.with_suffix(".html")


def _resolve_maintenance_path(output_arg: str) -> Path:
    """Return the maintenance_plan.json path alongside the report output."""
    p = Path(output_arg)
    stem = p.with_suffix("") if p.suffix.lower() in (".json", ".html") else p
    return stem.parent / "maintenance_plan.json"


# ── legacy v1 OS helper ───────────────────────────────────────────────────────

def _collect_legacy_os() -> dict:
    import psutil
    uname    = platform.uname()
    cpu_freq = psutil.cpu_freq()
    ram      = psutil.virtual_memory()
    return {
        "hostname": socket.gethostname(),
        "os": {
            "name":    uname.system,
            "version": uname.version,
            "release": uname.release,
            "build":   platform.version(),
        },
        "architecture": uname.machine,
        "processor":    uname.processor or platform.processor(),
        "cpu": {
            "physical_cores":       psutil.cpu_count(logical=False),
            "logical_cores":        psutil.cpu_count(logical=True),
            "max_frequency_mhz":    round(cpu_freq.max,     2) if cpu_freq else None,
            "current_frequency_mhz": round(cpu_freq.current, 2) if cpu_freq else None,
        },
        "ram": {
            "total_gb":      round(ram.total     / (1024 ** 3), 2),
            "available_gb":  round(ram.available / (1024 ** 3), 2),
            "used_gb":       round(ram.used      / (1024 ** 3), 2),
            "percent_used":  ram.percent,
        },
        "python_version": platform.python_version(),
        "current_user":   os.environ.get("USERNAME") or os.environ.get("USER", "unknown"),
    }


# ── platform collector factory ────────────────────────────────────────────────

def _load_platform_collectors():
    if sys.platform == "win32":
        from .collectors.windows.device_identity import DeviceIdentityCollector
        from .collectors.windows.hardware        import HardwareCollector     as WinHW
        from .collectors.windows.storage         import StorageCollector      as WinStorage
        from .collectors.windows.os_info         import OsInfoCollector
        from .collectors.windows.software        import SoftwareCollector
        from .collectors.windows.security        import SecurityCollector
        from .collectors.windows.antivirus       import AntivirusCollector
        from .collectors.windows.startup         import StartupCollector
        from .collectors.windows.network         import NetworkCollector      as WinNet
        from .collectors.windows.logs            import LogsCollector
        return [
            ("device_identity", DeviceIdentityCollector()),
            ("_win_hardware",   WinHW()),
            ("_win_storage",    WinStorage()),
            ("os_detail",       OsInfoCollector()),
            ("software",        SoftwareCollector()),
            ("security",        SecurityCollector()),
            ("_antivirus",      AntivirusCollector()),
            ("_startup",        StartupCollector()),
            ("_win_network",    WinNet()),
            ("logs",            LogsCollector()),
        ]
    elif sys.platform == "darwin":
        from .collectors.macos.device_identity import DeviceIdentityCollector
        from .collectors.macos.hardware        import HardwareCollector as MacHW
        from .collectors.macos.storage         import StorageCollector  as MacStorage
        from .collectors.macos.os_info         import OsInfoCollector
        from .collectors.macos.software        import SoftwareCollector
        from .collectors.macos.security        import SecurityCollector
        from .collectors.macos.network         import NetworkCollector  as MacNet
        from .collectors.macos.logs            import LogsCollector
        return [
            ("device_identity", DeviceIdentityCollector()),
            ("_mac_hardware",   MacHW()),
            ("_mac_storage",    MacStorage()),
            ("os_detail",       OsInfoCollector()),
            ("software",        SoftwareCollector()),
            ("security",        SecurityCollector()),
            ("_mac_network",    MacNet()),
            ("logs",            LogsCollector()),
        ]
    return []


# ── report assembly ───────────────────────────────────────────────────────────

def _assemble_report(
    common_hw:      dict,
    common_storage: dict,
    common_net:     dict,
    uptime:         dict,
    platform_results: dict,
    legacy_os:      dict,
    all_errors:     list[str],
) -> dict:
    from .report.findings        import compute_findings
    from .recommendations.engine import analyze as compute_recommendations

    now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # ── Hardware: merge common psutil data with Windows-specific CIM detail ──
    win_hw   = platform_results.get("_win_hardware", {})
    mac_hw   = platform_results.get("_mac_hardware", {})
    plat_hw  = win_hw or mac_hw

    common_cpu = common_hw.get("cpu") or {}
    common_ram = common_hw.get("ram") or {}
    plat_cpu   = plat_hw.get("cpu")   or {}
    plat_ram   = plat_hw.get("ram")   or {}

    hw_section: dict = {
        # psutil as base; CIM values fill in name/manufacturer and override cores/clocks
        "cpu": {**common_cpu, **plat_cpu},
        # psutil for usage/totals; CIM adds module list
        "ram": {**common_ram, **plat_ram},
        "gpu":          plat_hw.get("gpu",         []),
        "motherboard":  plat_hw.get("motherboard",  {}),
        "bios":         plat_hw.get("bios",         {}),
        "tpm":          plat_hw.get("tpm",          {}),
        "secure_boot":  plat_hw.get("secure_boot",  {}),
        "monitors":     plat_hw.get("monitors",     []),
        "printers":     plat_hw.get("printers",     []),
    }

    # ── Storage: prefer platform-specific (has physical disks + encryption) ─
    win_storage = platform_results.get("_win_storage", {})
    mac_storage = platform_results.get("_mac_storage", {})
    plat_storage = win_storage or mac_storage

    storage_list = (
        plat_storage.get("logical_volumes")
        if plat_storage
        else common_storage.get("partitions", [])
    )
    physical_disks = plat_storage.get("physical_disks", []) if plat_storage else []

    # ── Network: common psutil interfaces + Windows-specific adapter detail ──
    win_net = platform_results.get("_win_network", {})
    mac_net = platform_results.get("_mac_network", {})
    plat_net = win_net or mac_net

    net_section: dict = {
        "interfaces":      common_net.get("interfaces", []),
        "adapters":        plat_net.get("adapters",        []),   # richer than interfaces
        "wifi_ssid":       plat_net.get("wifi_ssid"),
        "dns_servers":     plat_net.get("dns_servers",     []),
        "default_gateway": plat_net.get("default_gateway"),
    }

    # Merge dedicated startup collector output.
    # Expose as top-level "startup" key and keep software.startup_entries in sync
    # so the recommendations engine and any existing consumers still work.
    startup_data = platform_results.get("_startup") or {}
    if startup_data:
        sw = platform_results.setdefault("software", {})
        sw["startup_entries"] = startup_data.get("entries", [])

    # Merge dedicated antivirus collector output into the security section.
    # This overwrites the basic AV list from SecurityCollector with the richer
    # data (exe_path, timestamp, detailed Defender telemetry).
    antivirus_data = platform_results.get("_antivirus") or {}
    if antivirus_data:
        sec = platform_results.setdefault("security", {})
        if antivirus_data.get("products") is not None:
            sec["antivirus"] = antivirus_data["products"]
        if antivirus_data.get("defender"):
            sec["windows_defender"] = antivirus_data["defender"]

    report: dict = {
        "schema_version": "2.0",
        "agent_version":  __version__,
        "run_id":         str(uuid.uuid4()),
        "collected_at":   now_utc,
        # v2 sections
        "device_identity": platform_results.get("device_identity", {}),
        "hardware":        hw_section,
        "physical_disks":  physical_disks,
        "storage":         storage_list,
        "network":         net_section,
        "os_detail":       platform_results.get("os_detail", {}),
        "software":        platform_results.get("software", {"installed": [], "count": 0}),
        "startup":         platform_results.get("_startup", {}),
        "security":        platform_results.get("security", {}),
        "logs":            platform_results.get("logs", {}),
        "findings":        [],
        "risk_score":      {"score": 0, "level": "low", "factors": []},
        "errors":          all_errors,
        # Legacy v1 keys (exact same shape as v1)
        "snapshot": {
            "generated_at_utc": uptime.get("snapshot_utc", now_utc),
            "tool_version":     __version__,
        },
        "os":    legacy_os,
        "reboot": uptime,
        "disks":  storage_list,
    }

    findings, risk_score = compute_findings(report)
    report["findings"]        = findings
    report["risk_score"]      = risk_score
    report["recommendations"] = compute_recommendations(report)

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
        dest   = Path(share_path)
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

    # Apply dry-run flag before any collector imports
    if args.dry_run:
        if sys.platform == "win32":
            from .collectors.windows import _utils as _win_utils
            _win_utils.DRY_RUN = True
        elif sys.platform == "darwin":
            from .collectors.macos import _utils as _mac_utils
            _mac_utils.DRY_RUN = True
        print("[it-snapshot] DRY-RUN mode: external commands are stubbed.")

    json_path, html_path = _resolve_paths(args.output)
    pretty = not args.no_pretty

    print("[it-snapshot] Collecting system information...")

    from .collectors.common.hardware import HardwareCollector
    from .collectors.common.storage  import StorageCollector
    from .collectors.common.network  import NetworkCollector
    from .collectors.common.uptime   import UptimeCollector

    all_errors: list[str] = []

    # Common collectors (psutil — always run)
    common_hw_result   = HardwareCollector().collect()
    common_stor_result = StorageCollector().collect()
    common_net_result  = NetworkCollector().collect()
    uptime_result      = UptimeCollector().collect()

    for r in (common_hw_result, common_stor_result, common_net_result, uptime_result):
        all_errors.extend(r.errors)

    # Legacy OS info (always run)
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
    platform_results:   dict = {}

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

    # Maintenance plan (read-only — no system changes)
    if args.maintenance == "plan":
        print("  - Generating maintenance plan...", end=" ", flush=True)
        from .maintenance.generator import generate as generate_maintenance
        maintenance_plan = generate_maintenance(report)
        maint_path = _resolve_maintenance_path(args.output)
        write_json(maintenance_plan, maint_path, pretty=pretty)
        print("done")
        print(f"[it-snapshot] MAINT -> {maint_path.resolve()}")

    # Summary line
    risk           = report.get("risk_score", {})
    findings_count = len(report.get("findings", []))
    errors_count   = len(all_errors)
    admin_note     = ""
    if sys.platform == "win32":
        from .collectors.windows._utils import is_admin
        if not is_admin():
            admin_note = " (not admin: some data skipped)"

    print(
        f"\n[it-snapshot] Done. "
        f"Risk: {risk.get('level','?').upper()} ({risk.get('score',0)}/100) | "
        f"Findings: {findings_count} | "
        f"Collection errors: {errors_count}{admin_note}"
    )
