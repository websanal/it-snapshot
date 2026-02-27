"""Suggest temp-file cleanup paths based on disk usage.

No filesystem access is performed here - this module only reads the
already-collected storage section of the report and produces advisory
suggestions. Nothing is deleted or modified.
"""

from __future__ import annotations


def analyze_temp_cleanup(report: dict) -> list[dict]:
    """Return temp-cleanup suggestions derived from the storage section.

    Args:
        report: Full assembled report dict.

    Returns:
        List of suggestion dicts. Empty if no NTFS volumes are present.
    """
    suggestions: list[dict] = []
    storage: list[dict] = report.get("storage") or []

    for volume in storage:
        if volume.get("fstype", "").upper() != "NTFS":
            continue

        drive = volume.get("drive_letter") or volume.get("device") or "?"
        pct   = volume.get("percent_used") or 0
        used  = volume.get("used_gb") or 0
        total = volume.get("total_gb") or 0
        free  = volume.get("free_gb") or 0

        # Derive the drive letter prefix (e.g. "C" from "C:\")
        dl = drive.rstrip("\\").rstrip("/").rstrip(":")
        dl = dl[-1] if dl else "C"

        if pct > 80:
            priority = "high"
        elif pct > 50:
            priority = "medium"
        else:
            priority = "low"

        rationale = (
            f"{drive} is {pct}% full "
            f"({used:.1f} GB used of {total:.1f} GB, {free:.1f} GB free)."
        )

        suggestions.append({
            "id":               "MAINT-TMP-001",
            "priority":         priority,
            "safe_to_automate": False,
            "title":            f"Clear Windows temporary files on {drive}",
            "detail": (
                "Windows accumulates temporary files from sessions, installers, "
                "and update downloads. Clearing them is safe and routine."
            ),
            "rationale": rationale,
            "paths_to_review": [
                "%TEMP%",
                f"{dl}:\\Windows\\Temp",
                f"{dl}:\\Windows\\SoftwareDistribution\\Download",
            ],
            "estimated_recoverable_gb": None,
            "action": {
                "type":        "suggest_only",
                "description": "Manually delete contents of standard temp folders",
                "manual_steps": [
                    "Press Win+R, type %TEMP%, press Enter",
                    "Select all files (Ctrl+A) and delete - skip any in-use files",
                    f"Press Win+R, type {dl}:\\Windows\\Temp, press Enter",
                    "Delete files you have permission to remove",
                    f"Alternatively: run 'cleanmgr /d {dl}:' and tick 'Temporary files'",
                    f"For update cache: stop 'wuauserv', clear {dl}:\\Windows\\SoftwareDistribution\\Download, restart service",
                ],
            },
        })

    return suggestions
