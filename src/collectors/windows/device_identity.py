"""Collect Windows device identity information."""

import json
import socket

import psutil

from ..base import BaseCollector
from . import _utils


class DeviceIdentityCollector(BaseCollector):
    name = "windows.device_identity"

    def _collect(self) -> dict:
        import winreg

        hostname = socket.gethostname()
        fqdn = socket.getfqdn()

        machine_guid = None
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
            )
            machine_guid = winreg.QueryValueEx(key, "MachineGuid")[0]
            winreg.CloseKey(key)
        except Exception:
            pass

        domain = None
        workgroup = None
        try:
            ps = _utils.run_powershell(
                "Get-WmiObject Win32_ComputerSystem "
                "| Select-Object Domain,Workgroup "
                "| ConvertTo-Json"
            )
            cs = json.loads(ps)
            domain = cs.get("Domain")
            workgroup = cs.get("Workgroup")
        except Exception:
            pass

        primary_macs = []
        try:
            for name, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if (
                        addr.family == psutil.AF_LINK
                        and addr.address
                        and addr.address not in ("", "00:00:00:00:00:00")
                    ):
                        primary_macs.append(addr.address)
        except Exception:
            pass

        azure_ad_device_id = None
        try:
            output = _utils.run_powershell("dsregcmd /status")
            for line in output.splitlines():
                if "DeviceId" in line and ":" in line:
                    azure_ad_device_id = line.split(":", 1)[1].strip()
                    break
        except Exception:
            pass

        return {
            "hostname": hostname,
            "fqdn": fqdn,
            "domain": domain,
            "workgroup": workgroup,
            "os_machine_id": machine_guid,
            "primary_macs": primary_macs[:4],
            "azure_ad_device_id": azure_ad_device_id,
        }
