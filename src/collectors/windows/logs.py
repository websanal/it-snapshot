"""Collect Windows event log entries."""

import json

from ..base import BaseCollector
from ._utils import run_powershell


class LogsCollector(BaseCollector):
    name = "windows.logs"

    def _collect(self) -> dict:
        return {
            "recent_errors": self._get_system_events("Error"),
            "recent_warnings": self._get_system_events("Warning"),
            "failed_logins": self._get_failed_logins(),
        }

    def _get_system_events(self, entry_type: str) -> list:
        try:
            ps = (
                f"Get-EventLog -LogName System -EntryType {entry_type} -Newest 10 "
                "| Select-Object TimeGenerated,EventID,Source,Message "
                "| ConvertTo-Json -AsArray"
            )
            items = json.loads(run_powershell(ps))
            if isinstance(items, dict):
                items = [items]
            return [
                {
                    "time": str(item.get("TimeGenerated", "")),
                    "event_id": item.get("EventID"),
                    "source": item.get("Source"),
                    "message": (item.get("Message") or "")[:300],
                    "level": entry_type,
                }
                for item in items
            ]
        except Exception:
            return []

    def _get_failed_logins(self) -> list:
        try:
            ps = (
                "Get-WinEvent -FilterHashtable @{LogName='Security';Id=4625} -MaxEvents 20 "
                "| Select-Object TimeCreated,Id,Message "
                "| ConvertTo-Json -AsArray"
            )
            items = json.loads(run_powershell(ps))
            if isinstance(items, dict):
                items = [items]
            return [
                {
                    "time": str(item.get("TimeCreated", "")),
                    "event_id": item.get("Id"),
                    "source": "Security",
                    "message": (item.get("Message") or "")[:300],
                    "level": "Error",
                }
                for item in items
            ]
        except Exception:
            return []
