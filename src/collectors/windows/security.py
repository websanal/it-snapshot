"""Collect Windows security configuration."""

import json
import winreg

from ..base import BaseCollector
from . import _utils


class SecurityCollector(BaseCollector):
    name = "windows.security"

    def _collect(self) -> dict:
        return {
            "antivirus": self._get_av(),
            "firewall": self._get_firewall(),
            "uac_enabled": self._get_uac(),
            "encryption": {"bitlocker_volumes": self._get_bitlocker()},
            "windows_defender": self._get_defender(),
            "secure_boot_enabled": self._get_secure_boot(),
            "gatekeeper_enabled": None,
            "sip_enabled": None,
        }

    def _get_av(self) -> list:
        try:
            ps = _utils.run_powershell(
                "Get-WmiObject -Namespace root/SecurityCenter2 -Class AntiVirusProduct "
                "| Select-Object displayName,productState "
                "| ConvertTo-Json"
            )
            items = json.loads(ps)
            if isinstance(items, dict):
                items = [items]
            result = []
            for item in items:
                state = item.get("productState", 0) or 0
                hex_state = format(state, "06x")
                enabled = hex_state[2:4] == "10"
                up_to_date = hex_state[4:6] == "00"
                result.append({
                    "name": item.get("displayName"),
                    "enabled": enabled,
                    "up_to_date": up_to_date,
                    "product_state": state,
                })
            return result
        except Exception:
            return []

    def _get_firewall(self) -> dict:
        try:
            ps = _utils.run_powershell(
                "Get-NetFirewallProfile "
                "| Select-Object Name,Enabled "
                "| ConvertTo-Json"
            )
            profiles = json.loads(ps)
            if isinstance(profiles, dict):
                profiles = [profiles]
            fw = {"domain_enabled": None, "private_enabled": None, "public_enabled": None}
            for p in profiles:
                name = (p.get("Name") or "").lower()
                enabled = bool(p.get("Enabled"))
                if "domain" in name:
                    fw["domain_enabled"] = enabled
                elif "private" in name:
                    fw["private_enabled"] = enabled
                elif "public" in name:
                    fw["public_enabled"] = enabled
            return fw
        except Exception:
            return {"domain_enabled": None, "private_enabled": None, "public_enabled": None}

    def _get_uac(self):
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System",
            )
            val = winreg.QueryValueEx(key, "EnableLUA")[0]
            winreg.CloseKey(key)
            return bool(val)
        except Exception:
            return None

    def _get_bitlocker(self) -> list:
        try:
            ps = _utils.run_powershell(
                "Get-BitLockerVolume "
                "| Select-Object MountPoint,VolumeStatus,ProtectionStatus "
                "| ConvertTo-Json"
            )
            items = json.loads(ps)
            if isinstance(items, dict):
                items = [items]
            return [
                {
                    "mount_point": item.get("MountPoint"),
                    "volume_status": item.get("VolumeStatus"),
                    "protection_status": item.get("ProtectionStatus"),
                }
                for item in items
            ]
        except Exception:
            return []

    def _get_defender(self) -> dict:
        try:
            ps = _utils.run_powershell(
                "Get-MpComputerStatus "
                "| Select-Object AMServiceEnabled,RealTimeProtectionEnabled,"
                "AntivirusSignatureLastUpdated "
                "| ConvertTo-Json"
            )
            d = json.loads(ps)
            return {
                "enabled": d.get("AMServiceEnabled"),
                "real_time_protection": d.get("RealTimeProtectionEnabled"),
                "signatures_last_updated": str(d.get("AntivirusSignatureLastUpdated") or ""),
            }
        except Exception:
            return {
                "enabled": None,
                "real_time_protection": None,
                "signatures_last_updated": None,
            }

    def _get_secure_boot(self):
        try:
            ps = _utils.run_powershell("Confirm-SecureBootUEFI")
            return ps.strip().lower() == "true"
        except Exception:
            return None
