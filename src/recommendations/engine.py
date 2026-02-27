"""Recommendations engine — analyze a full report and return findings + risk score.

Severity scale: info | warning | critical
Each finding carries: severity, title, detail, remediation.

Rules
-----
- disk > 90% used  → critical
- disk > 80% used  → warning
- uptime > 90 days → critical
- uptime > 30 days → warning
- no active antivirus detected → critical
- more than 8 startup entries  → warning
"""

from __future__ import annotations

_SEVERITY_WEIGHT: dict[str, int] = {"critical": 30, "warning": 10, "info": 2}
_SEVERITY_ORDER: dict[str, int]  = {"critical": 0, "warning": 1, "info": 2}


# ── individual rule checks ─────────────────────────────────────────────────────

def _check_disks(report: dict) -> list[dict]:
    findings: list[dict] = []
    # v2 uses "storage"; v1 legacy key is "disks" — check both, prefer v2
    volumes = report.get("storage") or report.get("disks") or []
    for vol in volumes:
        pct = vol.get("percent_used")
        if pct is None:
            continue
        device = vol.get("device") or vol.get("mountpoint") or "unknown"
        if pct > 90:
            findings.append({
                "severity": "critical",
                "title": f"Disk {device} critically full",
                "detail": f"{device} is {pct}% full.",
                "remediation": (
                    "Free up disk space immediately or expand storage capacity."
                ),
            })
        elif pct > 80:
            findings.append({
                "severity": "warning",
                "title": f"Disk {device} nearly full",
                "detail": f"{device} is {pct}% full.",
                "remediation": (
                    "Review and clean up disk usage to prevent reaching critical levels."
                ),
            })
    return findings


def _check_uptime(report: dict) -> list[dict]:
    uptime = (report.get("reboot") or {}).get("uptime") or {}
    days: int = uptime.get("days", 0) or 0
    human: str = uptime.get("human_readable", f"{days}d")
    if days > 90:
        return [{
            "severity": "critical",
            "title": "System uptime critically high",
            "detail": f"System has been running for {human} without a reboot.",
            "remediation": (
                "Reboot the system as soon as possible to apply pending updates "
                "and release accumulated resources."
            ),
        }]
    if days > 30:
        return [{
            "severity": "warning",
            "title": "System uptime high",
            "detail": f"System has been running for {human} without a reboot.",
            "remediation": (
                "Schedule a reboot to apply pending patches and refresh system state."
            ),
        }]
    return []


def _check_antivirus(report: dict) -> list[dict]:
    """Critical if no antivirus entry has enabled=True."""
    av_list = (report.get("security") or {}).get("antivirus") or []
    active = [av for av in av_list if av.get("enabled")]
    if not active:
        return [{
            "severity": "critical",
            "title": "No antivirus detected",
            "detail": "No enabled antivirus product was found on this system.",
            "remediation": (
                "Install and enable a reputable antivirus solution immediately."
            ),
        }]
    return []


def _check_startup(report: dict) -> list[dict]:
    """Warning if more than 8 startup registry entries are present."""
    software = report.get("software") or {}
    # v2: software.startup_entries; fall back to top-level startup key
    entries = software.get("startup_entries") or report.get("startup") or None
    if entries is None:
        return []
    count = len(entries)
    if count > 8:
        return [{
            "severity": "warning",
            "title": "Too many startup items",
            "detail": f"{count} programs are configured to run at startup.",
            "remediation": (
                "Disable unnecessary startup items to improve boot time and performance."
            ),
        }]
    return []


# ── scoring ────────────────────────────────────────────────────────────────────

def _compute_risk_score(findings: list[dict]) -> int:
    """Map findings to a 0-100 risk score (critical=30, warning=10, info=2, capped)."""
    return min(sum(_SEVERITY_WEIGHT.get(f["severity"], 0) for f in findings), 100)


# ── public API ─────────────────────────────────────────────────────────────────

def analyze(report: dict) -> dict:
    """Analyze a full report dict and return the recommendations section.

    Args:
        report: Complete snapshot report produced by the CLI assembler.

    Returns:
        ``{"risk_score": int, "findings": list[dict]}``
        Findings are sorted critical-first; each has
        ``severity``, ``title``, ``detail``, ``remediation``.
    """
    findings: list[dict] = []
    findings.extend(_check_disks(report))
    findings.extend(_check_uptime(report))
    findings.extend(_check_antivirus(report))
    findings.extend(_check_startup(report))

    findings.sort(key=lambda f: _SEVERITY_ORDER.get(f["severity"], 3))

    return {
        "risk_score": _compute_risk_score(findings),
        "findings":   findings,
    }
