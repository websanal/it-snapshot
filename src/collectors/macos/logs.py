"""Collect macOS system logs."""

import json
import subprocess

from ..base import BaseCollector


class LogsCollector(BaseCollector):
    name = "macos.logs"

    def _collect(self) -> dict:
        return {
            "recent_errors": self._get_logs("error"),
            "recent_warnings": self._get_logs("fault"),
            "failed_logins": [],
        }

    def _get_logs(self, level: str) -> list:
        try:
            result = subprocess.run(
                [
                    "log", "show",
                    "--last", "1h",
                    "--style", "json",
                    "--predicate", f'messageType == "{level}"',
                ],
                capture_output=True, text=True, timeout=60,
            )
            entries = json.loads(result.stdout)
            if not isinstance(entries, list):
                entries = []
            return [
                {
                    "time": e.get("timestamp"),
                    "event_id": None,
                    "source": e.get("processImagePath"),
                    "message": (e.get("eventMessage") or "")[:300],
                    "level": level,
                }
                for e in entries[:10]
            ]
        except Exception:
            return []
