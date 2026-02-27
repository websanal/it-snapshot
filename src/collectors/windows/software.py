"""Collect installed software and startup entries from the Windows registry."""

import os
import winreg

from ..base import BaseCollector

_UNINSTALL_PATHS = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
]

_STARTUP_REG_KEYS = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",     "HKLM\\Run"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce", "HKLM\\RunOnce"),
    (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",     "HKCU\\Run"),
    (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce", "HKCU\\RunOnce"),
]


class SoftwareCollector(BaseCollector):
    name = "windows.software"

    def _collect(self) -> dict:
        installed = self._get_installed()
        return {
            "installed":       installed,
            "count":           len(installed),
            "startup_entries": self._get_startup(),
        }

    # ── Installed apps ────────────────────────────────────────────────────────

    def _get_installed(self) -> list:
        installed: dict = {}
        for hive, path in _UNINSTALL_PATHS:
            try:
                key = winreg.OpenKey(hive, path)
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        sub_name = winreg.EnumKey(key, i)
                        sub_key  = winreg.OpenKey(key, sub_name)

                        def qv(n, sk=sub_key):
                            try:
                                return winreg.QueryValueEx(sk, n)[0]
                            except OSError:
                                return None

                        display_name = qv("DisplayName")
                        if not display_name:
                            winreg.CloseKey(sub_key)
                            continue
                        installed[display_name] = {
                            "name":         display_name,
                            "version":      qv("DisplayVersion"),
                            "publisher":    qv("Publisher"),
                            "install_date": qv("InstallDate"),
                        }
                        winreg.CloseKey(sub_key)
                    except Exception:
                        pass
                winreg.CloseKey(key)
            except Exception:
                pass

        return sorted(installed.values(), key=lambda x: (x["name"] or "").lower())

    # ── Startup entries ───────────────────────────────────────────────────────

    def _get_startup(self) -> list:
        entries: list = []

        # Registry Run / RunOnce keys
        for hive, path, location in _STARTUP_REG_KEYS:
            try:
                key = winreg.OpenKey(hive, path)
                for i in range(winreg.QueryInfoKey(key)[1]):
                    try:
                        name, data, _ = winreg.EnumValue(key, i)
                        entries.append({
                            "name":     name,
                            "command":  data,
                            "location": location,
                        })
                    except Exception:
                        pass
                winreg.CloseKey(key)
            except Exception:
                pass

        # Startup folders
        startup_dirs = [
            os.path.join(
                os.environ.get("APPDATA", ""),
                r"Microsoft\Windows\Start Menu\Programs\Startup",
            ),
            r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp",
        ]
        for d in startup_dirs:
            try:
                for f in os.listdir(d):
                    entries.append({
                        "name":     f,
                        "command":  os.path.join(d, f),
                        "location": f"Startup folder",
                    })
            except Exception:
                pass

        return entries
