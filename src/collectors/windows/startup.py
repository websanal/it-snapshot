"""Collect startup items from registry Run keys, startup folders, and scheduled tasks."""

from __future__ import annotations

import json
import os
import winreg

from ..base import BaseCollector
from . import _utils

# Registry paths that cause programs to run at login
_RUN_KEYS: list[tuple] = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",     "HKLM\\Run",     "registry_run"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce", "HKLM\\RunOnce", "registry_runonce"),
    (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",     "HKCU\\Run",     "registry_run"),
    (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce", "HKCU\\RunOnce", "registry_runonce"),
]

# Task Manager writes enable/disable state here (binary value; first byte 2=on, 3=off)
_APPROVED_KEYS: list[tuple] = [
    (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"),
    (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run32"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run32"),
]


class StartupCollector(BaseCollector):
    name = "windows.startup"

    def _collect(self) -> dict:
        approved = self._read_approved_map()
        entries  = self._read_registry_entries(approved)
        entries += self._read_startup_folders()
        tasks    = self._read_scheduled_tasks()

        count_by_type: dict[str, int] = {}
        for e in entries:
            count_by_type[e["type"]] = count_by_type.get(e["type"], 0) + 1
        count_by_type["scheduled_task"] = len(tasks)

        return {
            "count":        len(entries) + len(tasks),
            "entries":      entries,
            "scheduled_tasks": tasks,
            "count_by_type": count_by_type,
        }

    # ── StartupApproved (enabled/disabled flag) ────────────────────────────────

    def _read_approved_map(self) -> dict[str, bool]:
        """Return {name: enabled} from all StartupApproved registry paths."""
        state: dict[str, bool] = {}
        for hive, path in _APPROVED_KEYS:
            try:
                key = winreg.OpenKey(hive, path)
                count = winreg.QueryInfoKey(key)[1]
                for i in range(count):
                    try:
                        name, data, _ = winreg.EnumValue(key, i)
                        # First byte: 2 or 6 → enabled, 3 or 7 → disabled
                        enabled = (data[0] in (2, 6)) if isinstance(data, (bytes, bytearray)) else True
                        state[name] = enabled
                    except Exception:
                        pass
                winreg.CloseKey(key)
            except Exception:
                pass
        return state

    # ── Registry Run / RunOnce ─────────────────────────────────────────────────

    def _read_registry_entries(self, approved: dict[str, bool]) -> list[dict]:
        entries: list[dict] = []
        for hive, path, location, entry_type in _RUN_KEYS:
            try:
                key = winreg.OpenKey(hive, path)
                count = winreg.QueryInfoKey(key)[1]
                for i in range(count):
                    try:
                        name, command, _ = winreg.EnumValue(key, i)
                        entries.append({
                            "name":     name,
                            "command":  command,
                            "location": location,
                            "type":     entry_type,
                            # None means no override in StartupApproved → enabled by default
                            "enabled":  approved.get(name, True),
                        })
                    except Exception:
                        pass
                winreg.CloseKey(key)
            except Exception:
                pass
        return entries

    # ── Startup folders ────────────────────────────────────────────────────────

    def _read_startup_folders(self) -> list[dict]:
        entries: list[dict] = []
        dirs = [
            os.path.join(
                os.environ.get("APPDATA", ""),
                r"Microsoft\Windows\Start Menu\Programs\Startup",
            ),
            r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp",
        ]
        for folder in dirs:
            try:
                for fname in os.listdir(folder):
                    full = os.path.join(folder, fname)
                    entries.append({
                        "name":     fname,
                        "command":  full,
                        "location": "Startup folder",
                        "type":     "startup_folder",
                        "enabled":  True,
                    })
            except Exception:
                pass
        return entries

    # ── Scheduled tasks (logon / boot triggers) ────────────────────────────────

    def _read_scheduled_tasks(self) -> list[dict]:
        try:
            ps = _utils.run_powershell(
                "Get-ScheduledTask "
                "| Where-Object { $_.Triggers | Where-Object { "
                "    $_ -is [Microsoft.Management.Infrastructure.CimInstance] -and "
                "    ($_.CimClass.CimClassName -in @('MSFT_TaskLogonTrigger','MSFT_TaskBootTrigger')) "
                "}} "
                "| Select-Object TaskName,TaskPath,State,"
                "@{N='TriggerType';E={ ($_.Triggers | Select-Object -First 1).CimClass.CimClassName }},"
                "@{N='LastRunTime';E={ $_.LastRunTime }},"
                "@{N='NextRunTime';E={ $_.NextRunTime }} "
                "| ConvertTo-Json -Depth 3",
                timeout=45,
            )
            raw = json.loads(ps)
            if isinstance(raw, dict):
                raw = [raw]
            tasks = []
            for t in raw:
                trigger = (t.get("TriggerType") or "").replace("MSFT_Task", "")
                tasks.append({
                    "name":         t.get("TaskName"),
                    "path":         t.get("TaskPath"),
                    "state":        t.get("State"),
                    "trigger_type": trigger or None,
                    "last_run":     str(t.get("LastRunTime") or "") or None,
                    "next_run":     str(t.get("NextRunTime") or "") or None,
                })
            return tasks
        except Exception:
            return []
