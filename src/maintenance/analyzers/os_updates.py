"""Suggest OS patching actions based on patch staleness.

Reads report.os_detail.patches. No network calls, no Windows Update
API access - purely advisory based on the last-installed date already
collected.
"""

from __future__ import annotations

import datetime
import re

# Regex to extract epoch ms from WMI date strings like:
#   "{'value': '/Date(1764190800000)/', 'DateTime': '...'}"
_DATE_RE = re.compile(r"/Date\((\d+)\)/")

# Minimum days-since-patch before emitting a suggestion
_THRESHOLD_HIGH   = 90
_THRESHOLD_MEDIUM = 30
_THRESHOLD_LOW    = 14


def _parse_last_patch(raw: str | None) -> datetime.datetime | None:
    """Extract a UTC datetime from a raw WMI last-installed string."""
    if not raw:
        return None
    m = _DATE_RE.search(str(raw))
    if not m:
        return None
    epoch_ms = int(m.group(1))
    return datetime.datetime.fromtimestamp(epoch_ms / 1000, tz=datetime.timezone.utc)


def analyze_os_updates(report: dict) -> list[dict]:
    """Return OS-update suggestions derived from the os_detail section.

    Args:
        report: Full assembled report dict.

    Returns:
        List of suggestion dicts.
    """
    suggestions: list[dict] = []
    os_detail: dict = report.get("os_detail") or {}
    patches:   dict = os_detail.get("patches") or {}
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    # ── Patch staleness ───────────────────────────────────────────────────────
    last_raw   = patches.get("last_installed")
    last_dt    = _parse_last_patch(last_raw)
    patch_count = patches.get("count", 0)
    hotfixes   = patches.get("hotfixes") or []
    most_recent_kb = hotfixes[0].get("id") if hotfixes else None

    if last_dt is None:
        # Cannot determine patch date - emit a medium reminder
        suggestions.append({
            "id":               "MAINT-OSU-001",
            "priority":         "medium",
            "safe_to_automate": False,
            "title":            "Verify Windows Update status",
            "detail":           "The last patch installation date could not be determined from the collected data.",
            "rationale":        "Regular patching is the highest-impact security control. Manual verification is recommended.",
            "patch_info":       {"last_patch_date": None, "days_since_last_patch": None},
            "action": {
                "type":        "suggest_only",
                "description": "Open Windows Update and check for pending updates",
                "manual_steps": [
                    "Open Settings > Windows Update",
                    "Click 'Check for updates'",
                    "Install all available updates",
                    "Reboot when prompted",
                ],
            },
        })
    else:
        days_ago  = (now_utc - last_dt).days
        date_str  = last_dt.strftime("%Y-%m-%d")

        if days_ago >= _THRESHOLD_HIGH:
            priority = "high"
        elif days_ago >= _THRESHOLD_MEDIUM:
            priority = "medium"
        elif days_ago >= _THRESHOLD_LOW:
            priority = "low"
        else:
            priority = None  # patched recently - no suggestion needed

        if priority:
            suggestions.append({
                "id":               "MAINT-OSU-001",
                "priority":         priority,
                "safe_to_automate": False,
                "title":            "Apply pending Windows updates",
                "detail":           f"Last patch installed on {date_str} - {days_ago} day(s) ago.",
                "rationale": (
                    "Regular patching is the single highest-impact security control. "
                    "Delaying patches increases exposure to known CVEs."
                ),
                "patch_info": {
                    "last_patch_date":       date_str,
                    "days_since_last_patch": days_ago,
                    "patch_count_in_report": patch_count,
                    "most_recent_kb":        most_recent_kb,
                },
                "action": {
                    "type":        "suggest_only",
                    "description": "Open Windows Update and install all available updates",
                    "manual_steps": [
                        "Open Settings > Windows Update",
                        "Click 'Check for updates'",
                        "Install all available updates",
                        "Reboot when prompted",
                    ],
                },
            })

    # ── Standing Windows Update reminder ─────────────────────────────────────
    # Always include an informational reminder regardless of patch state.
    suggestions.append({
        "id":               "MAINT-OSU-002",
        "priority":         "info",
        "safe_to_automate": False,
        "title":            "Confirm Windows Update is set to automatic",
        "detail": (
            "Ensure Windows Update is configured to download and install "
            "updates automatically to minimise exposure windows."
        ),
        "rationale":        "Automatic updates reduce the chance of a long patch gap going unnoticed.",
        "action": {
            "type":        "suggest_only",
            "description": "Verify the Windows Update policy setting",
            "manual_steps": [
                "Open Settings > Windows Update > Advanced options",
                "Confirm 'Receive updates for other Microsoft products' is enabled",
                "Confirm 'Automatic (recommended)' is selected under Active hours",
                "Check Group Policy: Computer Configuration > Administrative Templates > Windows Components > Windows Update",
            ],
        },
    })

    return suggestions
