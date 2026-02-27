"""Collect macOS system logs via the unified logging system."""

import json

from ..base import BaseCollector
from . import _utils


class LogsCollector(BaseCollector):
    name = "macos.logs"

    def _collect(self) -> dict:
        errors, warnings = self._get_recent_logs()
        return {
            "recent_errors":   errors,
            "recent_warnings": warnings,
            "failed_logins":   self._get_failed_logins(),
            "summary":         {},
        }

    # ── Recent errors and warnings ────────────────────────────────────────────

    def _get_recent_logs(self) -> tuple[list, list]:
        errors   = []
        warnings = []
        raw = _utils.run_cmd([
            "log", "show",
            "--last", "1h",
            "--style", "json",
            "--predicate", 'messageType == "error" OR messageType == "fault"',
        ], timeout=60)
        if not raw:
            return errors, warnings
        try:
            entries = json.loads(raw)
            if not isinstance(entries, list):
                return errors, warnings
            for e in entries[:30]:
                level = e.get("messageType", "")
                entry = {
                    "time":     e.get("timestamp"),
                    "event_id": None,
                    "source":   e.get("processImagePath") or e.get("process"),
                    "message":  (e.get("eventMessage") or "")[:300],
                    "level":    level,
                }
                if level == "fault":
                    warnings.append(entry)
                else:
                    errors.append(entry)
        except Exception:
            pass
        return errors[:10], warnings[:10]

    # ── Failed logins ─────────────────────────────────────────────────────────

    def _get_failed_logins(self) -> list:
        logins = []

        # Primary: unified log — authentication failures
        raw = _utils.run_cmd([
            "log", "show",
            "--last", "1d",
            "--style", "json",
            "--predicate",
            'eventMessage CONTAINS "authentication failed"'
            ' OR eventMessage CONTAINS "Authentication failed"',
        ], timeout=30)
        if raw:
            try:
                entries = json.loads(raw)
                for e in (entries if isinstance(entries, list) else [])[:20]:
                    logins.append({
                        "time":    e.get("timestamp"),
                        "source":  e.get("processImagePath") or e.get("process"),
                        "message": (e.get("eventMessage") or "")[:200],
                        "level":   "warning",
                    })
            except Exception:
                pass

        # Fallback: last command (shows console logins; may not show FAILED)
        if not logins:
            raw = _utils.run_cmd(["last", "-F", "-50"])
            for line in raw.splitlines():
                lower = line.lower()
                if "failed" in lower or "bad" in lower:
                    logins.append({"message": line.strip(), "level": "warning"})

        return logins[:20]
