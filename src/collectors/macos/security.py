"""Collect macOS security configuration."""

from ..base import BaseCollector
from . import _utils


class SecurityCollector(BaseCollector):
    name = "macos.security"

    def _collect(self) -> dict:
        return {
            "antivirus":           [],
            "firewall":            self._get_firewall(),
            "uac_enabled":         None,
            "encryption":          {"filevault_enabled": self._get_filevault()},
            "windows_defender":    None,
            "secure_boot_enabled": None,
            "gatekeeper_enabled":  self._get_gatekeeper(),
            "sip_enabled":         self._get_sip(),
        }

    def _get_filevault(self):
        out = _utils.run_cmd(["fdesetup", "status"])
        if "On" in out:
            return True
        if "Off" in out:
            return False
        return None

    def _get_gatekeeper(self):
        out = _utils.run_cmd(["spctl", "--status"])
        if "enabled" in out.lower():
            return True
        if "disabled" in out.lower():
            return False
        return None

    def _get_sip(self):
        out = _utils.run_cmd(["csrutil", "status"])
        if "enabled" in out.lower():
            return True
        if "disabled" in out.lower():
            return False
        return None

    def _get_firewall(self) -> dict:
        # Prefer socketfilterfw for accurate state
        out = _utils.run_cmd([
            "/usr/libexec/ApplicationFirewall/socketfilterfw",
            "--getglobalstate",
        ])
        if out:
            enabled = "enabled" in out.lower()
        else:
            # Fallback: defaults read
            val = _utils.run_cmd([
                "defaults", "read",
                "/Library/Preferences/com.apple.alf", "globalstate",
            ])
            enabled = (val.strip() not in ("0", "")) if val.strip() else None
        return {
            "domain_enabled":  enabled,
            "private_enabled": enabled,
            "public_enabled":  enabled,
        }
