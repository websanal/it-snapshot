"""Collect Windows event log summary and recent critical/error events."""

import json

from ..base import BaseCollector
from . import _utils

PERIOD_DAYS = 7
# Per-level cap to keep queries fast on busy systems
_MAX_EVENTS_COUNT = 500
_MAX_EVENTS_SAMPLE = 10   # per log per level for the top-20 sample


def _loads_array(ps_output: str) -> list:
    try:
        data = json.loads(ps_output)
        return data if isinstance(data, list) else [data]
    except Exception:
        return []


class LogsCollector(BaseCollector):
    name = "windows.logs"

    def _collect(self) -> dict:
        sys_summary, sys_events   = self._get_log_data("System")
        app_summary, app_events   = self._get_log_data("Application")
        failed_logins             = self._get_failed_logins()

        # Top-20 most recent critical+error across both logs
        all_events = sorted(
            sys_events + app_events,
            key=lambda e: e.get("time", ""),
            reverse=True,
        )[:20]

        # Top-10 error sources derived from the sample events
        source_counts: dict = {}
        for e in all_events:
            src = e.get("source") or "Unknown"
            source_counts[src] = source_counts.get(src, 0) + 1
        top_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # Keep legacy keys for backward compatibility with HTML reporter / findings
        recent_errors   = [e for e in all_events if e.get("level_num") in (1, 2)][:10]
        recent_warnings = []

        return {
            "summary": {
                "period_days":       PERIOD_DAYS,
                "system":            sys_summary,
                "application":       app_summary,
                "top_error_sources": [{"source": s, "count": c} for s, c in top_sources],
            },
            "recent_critical_errors": all_events,
            "failed_logins":          failed_logins,
            # legacy keys
            "recent_errors":   recent_errors,
            "recent_warnings": recent_warnings,
        }

    # ── Per-log data ──────────────────────────────────────────────────────────

    def _get_log_data(self, log_name: str) -> tuple[dict, list]:
        summary = {"critical": 0, "error": 0, "warning": 0}
        events:  list = []

        # --- Counts (capped at _MAX_EVENTS_COUNT each to stay fast) ---
        try:
            ps = f"""
$c = (Get-WinEvent -FilterHashtable @{{LogName='{log_name}';Level=1}} `
      -MaxEvents {_MAX_EVENTS_COUNT} -EA SilentlyContinue | Measure-Object).Count
$e = (Get-WinEvent -FilterHashtable @{{LogName='{log_name}';Level=2}} `
      -MaxEvents {_MAX_EVENTS_COUNT} -EA SilentlyContinue | Measure-Object).Count
$w = (Get-WinEvent -FilterHashtable @{{LogName='{log_name}';Level=3}} `
      -MaxEvents {_MAX_EVENTS_COUNT} -EA SilentlyContinue | Measure-Object).Count
@{{critical=$c;error=$e;warning=$w}} | ConvertTo-Json
"""
            raw = json.loads(_utils.run_powershell(ps, timeout=60))
            if isinstance(raw, dict):
                summary["critical"] = int(raw.get("critical") or 0)
                summary["error"]    = int(raw.get("error")    or 0)
                summary["warning"]  = int(raw.get("warning")  or 0)
        except Exception:
            pass

        # --- Sample events (critical + error) ---
        try:
            ps2 = f"""
$ev = @()
$ev += @(Get-WinEvent -FilterHashtable @{{LogName='{log_name}';Level=1}} `
         -MaxEvents {_MAX_EVENTS_SAMPLE} -EA SilentlyContinue)
$ev += @(Get-WinEvent -FilterHashtable @{{LogName='{log_name}';Level=2}} `
         -MaxEvents {_MAX_EVENTS_SAMPLE} -EA SilentlyContinue)
if ($ev) {{
    $ev | Sort-Object TimeCreated -Descending |
    Select-Object TimeCreated,Id,ProviderName,Level,LevelDisplayName,LogName,
      @{{N='Message';E={{if ($_.Message) {{($_.Message -split "`n")[0].Trim()}} else {{''}} }}}} |
    ConvertTo-Json
}} else {{ '[]' }}
"""
            for item in _loads_array(_utils.run_powershell(ps2, timeout=60)):
                events.append({
                    "time":       str(item.get("TimeCreated") or ""),
                    "event_id":   item.get("Id"),
                    "source":     item.get("ProviderName"),
                    "level":      item.get("LevelDisplayName"),
                    "level_num":  item.get("Level"),
                    "log":        item.get("LogName"),
                    "message":    (item.get("Message") or "")[:400],
                })
        except Exception:
            pass

        return summary, events

    # ── Failed logins (Security log, Event 4625) ──────────────────────────────

    def _get_failed_logins(self) -> list:
        try:
            ps = r"""
$ev = Get-WinEvent -FilterHashtable @{LogName='Security';Id=4625} `
      -MaxEvents 20 -EA SilentlyContinue
if ($ev) {
    $ev | Select-Object TimeCreated,Id,
      @{N='Message';E={if ($_.Message) {($_.Message -split "`n")[0].Trim()} else {''}}} |
    ConvertTo-Json
} else { '[]' }
"""
            return [
                {
                    "time":     str(item.get("TimeCreated") or ""),
                    "event_id": item.get("Id"),
                    "source":   "Security",
                    "message":  (item.get("Message") or "")[:300],
                    "level":    "Error",
                }
                for item in _loads_array(_utils.run_powershell(ps, timeout=30))
            ]
        except Exception:
            return []
