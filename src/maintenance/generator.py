"""Maintenance plan generator - orchestrates all analyzers into a single plan dict.

This module is the sole entry point called by the CLI. It is a pure
function: given a report dict, it returns a maintenance plan dict.
Nothing is written to disk or modified on the system.
"""

from __future__ import annotations

import datetime


def generate(report: dict) -> dict:
    """Produce a maintenance plan from an assembled report.

    Args:
        report: Full assembled report dict (as produced by cli._assemble_report).

    Returns:
        A maintenance plan dict ready to be serialised to JSON.
        Every suggestion has ``safe_to_automate: false`` and
        ``action.type: "suggest_only"`` - no changes are applied.
    """
    from .analyzers.temp_cleanup      import analyze_temp_cleanup
    from .analyzers.startup_reduction import analyze_startup_reduction
    from .analyzers.os_updates        import analyze_os_updates

    temp    = analyze_temp_cleanup(report)
    startup = analyze_startup_reduction(report)
    os_upd  = analyze_os_updates(report)

    by_category = {
        "temp_cleanup":      len(temp),
        "startup_reduction": len(startup),
        "os_updates":        len(os_upd),
    }
    total = sum(by_category.values())

    hostname = (
        (report.get("device_identity") or {}).get("hostname")
        or (report.get("os") or {}).get("hostname")
    )

    return {
        "schema_version": "1.0",
        "plan_version":   "1.0",
        "generated_at":   datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_report_id": report.get("run_id"),
        "hostname":       hostname,
        "agent_version":  report.get("agent_version"),
        # Safety notice is embedded in the file itself so any downstream
        # consumer sees it without needing to read external documentation.
        "safety_notice": (
            "This plan contains suggestions only. "
            "No changes are applied automatically. "
            "Review every item carefully before taking any action."
        ),
        "summary": {
            "total_suggestions":            total,
            "by_category":                  by_category,
            # Cannot know recoverable space without scanning filesystems.
            "estimated_space_recoverable_gb": None,
        },
        "suggestions": {
            "temp_cleanup":      temp,
            "startup_reduction": startup,
            "os_updates":        os_upd,
        },
    }
