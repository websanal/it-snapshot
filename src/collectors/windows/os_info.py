"""Collect detailed Windows OS information: edition, patches, local admins."""

import json
import os
import platform
import socket

from ..base import BaseCollector
from . import _utils


def _loads_array(ps_output: str) -> list:
    try:
        data = json.loads(ps_output)
        return data if isinstance(data, list) else [data]
    except Exception:
        return []


def _loads_obj(ps_output: str) -> dict:
    try:
        data = json.loads(ps_output)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


class OsInfoCollector(BaseCollector):
    name = "windows.os_info"

    def _collect(self) -> dict:
        result: dict = {
            "hostname":        socket.gethostname(),
            "architecture":    platform.machine(),
            "python_version":  platform.python_version(),
            "current_user":    os.environ.get("USERNAME") or os.environ.get("USER", "unknown"),
        }
        result.update(self._get_os_cim())
        result["patches"]      = self._get_patches()
        result["local_admins"] = self._get_local_admins()
        return result

    # ── OS details from CIM ──────────────────────────────────────────────────

    def _get_os_cim(self) -> dict:
        try:
            ps = _utils.run_powershell(
                "Get-CimInstance Win32_OperatingSystem "
                "| Select-Object Caption,Version,BuildNumber,InstallDate,"
                "LastBootUpTime,RegisteredUser "
                "| ConvertTo-Json"
            )
            o = _loads_obj(ps)
            return {
                "edition":          (o.get("Caption")         or "").strip() or None,
                "version":          o.get("Version"),
                "build":            str(o.get("BuildNumber") or "").strip() or None,
                "install_date":     str(o.get("InstallDate") or "").strip() or None,
                "last_boot":        str(o.get("LastBootUpTime") or "").strip() or None,
                "registered_owner": o.get("RegisteredUser"),
            }
        except Exception:
            return {}

    # ── Patch / hotfix list ──────────────────────────────────────────────────

    def _get_patches(self) -> dict:
        try:
            ps = _utils.run_powershell(
                "Get-HotFix "
                "| Sort-Object InstalledOn -Descending "
                "| Select-Object HotFixID,Description,InstalledOn -First 50 "
                "| ConvertTo-Json",
                timeout=45,
            )
            items = _loads_array(ps)
            hotfixes = []
            last_date = None
            for item in items:
                kb   = item.get("HotFixID")
                desc = item.get("Description")
                date = str(item.get("InstalledOn") or "").strip()
                if kb:
                    hotfixes.append({
                        "id":           kb,
                        "description":  desc,
                        "installed_on": date or None,
                    })
                if not last_date and date:
                    last_date = date
            return {
                "count":          len(hotfixes),
                "last_installed": last_date,
                "hotfixes":       hotfixes,
            }
        except Exception as exc:
            return {
                "count":          0,
                "last_installed": None,
                "hotfixes":       [],
                "warning":        str(exc),
            }

    # ── Local Administrators group ───────────────────────────────────────────

    def _get_local_admins(self) -> dict:
        if not _utils.is_admin():
            return {
                "members": [],
                "warning": "Administrator privileges required to enumerate local admins.",
            }
        try:
            ps = _utils.run_powershell(
                "Get-LocalGroupMember -Group 'Administrators' "
                "| Select-Object Name,PrincipalSource,ObjectClass "
                "| ConvertTo-Json"
            )
            members = [
                {
                    "name":   item.get("Name"),
                    "source": str(item.get("PrincipalSource") or "").strip(),
                    "type":   item.get("ObjectClass"),
                }
                for item in _loads_array(ps)
            ]
            return {"members": members}
        except Exception as exc:
            return {"members": [], "warning": str(exc)}
