"""Suggest startup item reductions based on the collected startup section.

No registry writes or process changes are made. This module only reads
report["startup"] and produces advisory suggestions. Security-critical
entries are explicitly exempted from suggestions.
"""

from __future__ import annotations

# Names that must never be flagged - security tools and OS essentials.
_EXEMPT: set[str] = {
    "egui",            # ESET real-time protection
    "securityhealth",  # Windows Security Health (already disabled here, handled separately)
    "globalprotect",   # Palo Alto VPN
    "keepass",         # Password manager
    "keepass 2",
}

# Patterns flagged as optional/low-value for standard workstations.
# Each tuple: (substring_lower, friendly_reason)
_OPTIONAL_PATTERNS: list[tuple[str, str]] = [
    ("microsoftedge",         "Edge browser convenience launch - start manually when needed"),
    ("opera",                 "Browser auto-start - start manually when needed"),
    ("googledrivefs",         "Google Drive sync - can start on-demand"),
    ("onedrive",              "OneDrive sync - can start on-demand if not required immediately at login"),
    ("clickshare",            "ClickShare conferencing client - optional outside meeting rooms"),
    ("adobecollabsync",       "Adobe Acrobat collaboration sync - optional"),
    ("adobe acrobat sync",    "Adobe Acrobat collaboration sync - optional"),
    ("ituneshelper",          "iTunes helper - optional if iPhone not regularly connected at login"),
    ("claude",                "Claude desktop - start manually when needed"),
    ("teams",                 "Microsoft Teams - can be launched manually; auto-start delays login"),
]

# Scheduled-task path prefixes that are always OS-owned and must not be flagged.
_TASK_OS_PREFIXES: tuple[str, ...] = (
    "\\microsoft\\windows\\",
    "\\microsoft\\",
)


def _is_exempt(name: str) -> bool:
    low = name.lower()
    return any(ex in low for ex in _EXEMPT)


def _optional_reason(name: str) -> str | None:
    low = name.lower()
    for pattern, reason in _OPTIONAL_PATTERNS:
        if pattern in low:
            return reason
    return None


def analyze_startup_reduction(report: dict) -> list[dict]:
    """Return startup-reduction suggestions from report["startup"].

    Args:
        report: Full assembled report dict.

    Returns:
        List of suggestion dicts.
    """
    suggestions: list[dict] = []
    startup: dict = report.get("startup") or {}
    entries: list[dict] = startup.get("entries") or []
    tasks:   list[dict] = startup.get("scheduled_tasks") or []

    counter = 1

    # ── Registry / startup-folder entries ─────────────────────────────────────
    for entry in entries:
        name     = entry.get("name") or ""
        etype    = entry.get("type") or ""
        enabled  = entry.get("enabled", True)
        location = entry.get("location") or ""
        command  = entry.get("command") or ""

        if _is_exempt(name):
            continue

        # RunOnce entries that still exist after boot are stale
        if etype == "registry_runonce":
            suggestions.append(_make_suggestion(
                sid=f"MAINT-STR-{counter:03d}",
                priority="medium",
                title=f"Review lingering RunOnce entry: '{name}'",
                detail=(
                    f"'{name}' is registered under {location}. "
                    "RunOnce entries should self-delete after running; a persistent entry "
                    "may indicate an incomplete installation or failed operation."
                ),
                rationale="Stale RunOnce entries can slow login and indicate unresolved installer issues.",
                entry=entry,
                manual_steps=[
                    f"Open Registry Editor and navigate to {location}",
                    f"Verify whether '{name}' still needs to run",
                    "If the associated operation completed, delete the value",
                    "If unsure, check the application's installer logs",
                ],
            ))
            counter += 1
            continue

        # Already-disabled entries are dead weight - suggest cleanup
        if not enabled:
            suggestions.append(_make_suggestion(
                sid=f"MAINT-STR-{counter:03d}",
                priority="info",
                title=f"Remove disabled startup entry: '{name}'",
                detail=(
                    f"'{name}' exists in {location} but has been disabled "
                    "(marked off in StartupApproved). It has no effect and can be removed."
                ),
                rationale="Orphaned disabled entries accumulate over time and clutter startup management tools.",
                entry=entry,
                manual_steps=[
                    f"Open Registry Editor and navigate to {location}",
                    f"Delete the '{name}' value",
                    "WARNING: Only delete values you are confident are no longer needed",
                ],
            ))
            counter += 1
            continue

        # Known optional entry
        reason = _optional_reason(name)
        if reason:
            if "hklm" in location.lower():
                reg_path = location
                note = (
                    f"Note: this entry is in {location} (machine-wide). "
                    "Disabling it affects all users on this machine."
                )
            else:
                reg_path = location
                note = f"This entry is in {location} (current user only)."

            manual_steps = [
                "Open Task Manager (Ctrl+Shift+Esc) and go to the Startup Apps tab",
                f"Find '{name}' and click 'Disable'",
                f"Alternatively: open Registry Editor, navigate to {reg_path}, delete the '{name}' value",
                note,
            ]

            suggestions.append(_make_suggestion(
                sid=f"MAINT-STR-{counter:03d}",
                priority="low",
                title=f"Consider disabling '{name}' from startup",
                detail=f"'{name}' launches automatically at login via {location}.",
                rationale=reason,
                entry=entry,
                manual_steps=manual_steps,
            ))
            counter += 1

    # ── Scheduled tasks with logon/boot triggers ──────────────────────────────
    for task in tasks:
        name  = task.get("name") or ""
        path  = task.get("path") or "\\"
        state = task.get("state")
        trigger = task.get("trigger_type") or ""

        if _is_exempt(name):
            continue

        # Skip OS-owned task paths
        full_path = (path + name).lower()
        if any(full_path.startswith(pfx) for pfx in _TASK_OS_PREFIXES):
            continue

        # Only flag Ready (state=3) tasks - disabled ones are already inactive
        if state != 3:
            continue

        trigger_label = trigger or "LogonTrigger/BootTrigger"
        suggestions.append(_make_suggestion(
            sid=f"MAINT-STR-{counter:03d}",
            priority="low",
            title=f"Review scheduled task at startup: '{name}'",
            detail=(
                f"The scheduled task '{name}' (path: {path}) has a {trigger_label} "
                "and runs automatically at login or boot."
            ),
            rationale=(
                "Third-party scheduled tasks that run at logon can delay startup "
                "and consume resources. Review whether each task is still necessary."
            ),
            entry={
                "name":         name,
                "path":         path,
                "trigger_type": trigger,
                "state":        state,
            },
            manual_steps=[
                "Open Task Scheduler (taskschd.msc)",
                f"Locate the task '{name}' under '{path}'",
                "Review its trigger, action, and history",
                "Right-click and select 'Disable' if the task is no longer needed",
                "Do not disable tasks related to system health, security, or backup",
            ],
        ))
        counter += 1

    return suggestions


def _make_suggestion(
    *,
    sid: str,
    priority: str,
    title: str,
    detail: str,
    rationale: str,
    entry: dict,
    manual_steps: list[str],
) -> dict:
    return {
        "id":               sid,
        "priority":         priority,
        "safe_to_automate": False,
        "title":            title,
        "detail":           detail,
        "rationale":        rationale,
        "entry":            entry,
        "action": {
            "type":        "suggest_only",
            "description": "Review and disable via Task Manager, Registry Editor, or Task Scheduler",
            "manual_steps": manual_steps,
        },
    }
