"""Findings engine and risk scoring for it-snapshot v2."""

from .unwanted_software import match_installed

_SEVERITY_WEIGHTS = {"low": 5, "medium": 15, "high": 30, "critical": 50}


def compute_findings(report: dict) -> tuple[list[dict], dict]:
    """Evaluate the report dict and return (findings, risk_score) dicts."""
    findings = []

    security = report.get("security", {})
    logs = report.get("logs", {})
    reboot = report.get("reboot", {})
    storage = report.get("storage", [])

    # SEC-001: No active antivirus
    av_list = security.get("antivirus", [])
    active_av = [av for av in av_list if av.get("enabled")]
    if not active_av:
        findings.append({
            "id": "SEC-001",
            "severity": "high",
            "title": "No active antivirus detected",
            "detail": "No enabled antivirus product was found via SecurityCenter2.",
        })

    # SEC-002: UAC disabled
    if security.get("uac_enabled") is False:
        findings.append({
            "id": "SEC-002",
            "severity": "high",
            "title": "UAC is disabled",
            "detail": "User Account Control (EnableLUA) is set to 0 in the registry.",
        })

    # SEC-003: Public firewall disabled
    fw = security.get("firewall", {})
    if fw.get("public_enabled") is False:
        findings.append({
            "id": "SEC-003",
            "severity": "high",
            "title": "Public firewall profile is disabled",
            "detail": "The Windows Firewall public profile is not active.",
        })

    # SEC-004: BitLocker not active on all volumes
    bl_vols = security.get("encryption", {}).get("bitlocker_volumes", [])
    unprotected = [v for v in bl_vols if v.get("protection_status") != 1]
    if bl_vols and unprotected:
        findings.append({
            "id": "SEC-004",
            "severity": "medium",
            "title": "BitLocker not active on all volumes",
            "detail": f"{len(unprotected)} volume(s) lack active BitLocker protection.",
        })

    # SEC-005: Failed login attempts
    failed_logins = logs.get("failed_logins", [])
    count = len(failed_logins)
    if count >= 5:
        findings.append({
            "id": "SEC-005",
            "severity": "high" if count >= 10 else "medium",
            "title": "Multiple failed login attempts detected",
            "detail": f"{count} failed login event(s) found in the Security log.",
        })

    # SYS-001: Long uptime
    uptime_days = (reboot.get("uptime") or {}).get("days", 0) or 0
    if uptime_days > 60:
        findings.append({
            "id": "SYS-001",
            "severity": "high",
            "title": "System uptime exceeds 60 days",
            "detail": f"System has been running for {uptime_days} days without a reboot.",
        })
    elif uptime_days > 30:
        findings.append({
            "id": "SYS-001",
            "severity": "medium",
            "title": "System uptime exceeds 30 days",
            "detail": f"System has been running for {uptime_days} days without a reboot.",
        })

    # SWU-001: Unwanted software detected
    installed = (report.get("software") or {}).get("installed", [])
    for match in match_installed(installed):
        findings.append({
            "id":       "SWU-001",
            "severity": match["severity"],
            "title":    f"Unwanted software detected: {match['installed_name']}",
            "detail":   (
                f"Matched pattern '{match['pattern']}' "
                f"[{match['category']}]: {match['reason']}"
            ),
        })

    # SYS-002: Disk nearly/critically full
    for disk in storage:
        pct = disk.get("percent_used") or 0
        mp = disk.get("mountpoint", "?")
        if pct > 95:
            findings.append({
                "id": "SYS-002",
                "severity": "high",
                "title": f"Disk critically full: {mp}",
                "detail": f"{mp} is {pct}% full (>95%).",
            })
        elif pct > 90:
            findings.append({
                "id": "SYS-002",
                "severity": "medium",
                "title": f"Disk nearly full: {mp}",
                "detail": f"{mp} is {pct}% full (>90%).",
            })

    # Risk score
    total = sum(_SEVERITY_WEIGHTS.get(f["severity"], 0) for f in findings)
    score = min(100, total)
    if score >= 61:
        level = "critical"
    elif score >= 31:
        level = "high"
    elif score >= 11:
        level = "medium"
    else:
        level = "low"

    risk_score = {
        "score": score,
        "level": level,
        "factors": [f["id"] for f in findings],
    }

    return findings, risk_score
