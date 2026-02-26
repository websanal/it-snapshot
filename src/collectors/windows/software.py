"""Collect installed software from the Windows registry."""

import winreg

from ..base import BaseCollector

_UNINSTALL_PATHS = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
]


class SoftwareCollector(BaseCollector):
    name = "windows.software"

    def _collect(self) -> dict:
        installed = {}
        for hive, path in _UNINSTALL_PATHS:
            try:
                key = winreg.OpenKey(hive, path)
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        sub_name = winreg.EnumKey(key, i)
                        sub_key = winreg.OpenKey(key, sub_name)

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
                            "name": display_name,
                            "version": qv("DisplayVersion"),
                            "publisher": qv("Publisher"),
                            "install_date": qv("InstallDate"),
                        }
                        winreg.CloseKey(sub_key)
                    except Exception:
                        pass
                winreg.CloseKey(key)
            except Exception:
                pass

        items = sorted(installed.values(), key=lambda x: (x["name"] or "").lower())
        return {"installed": items, "count": len(items)}
