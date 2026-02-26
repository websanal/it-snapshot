"""Collect macOS security configuration."""

import subprocess

from ..base import BaseCollector


def _run(cmd: list) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.stdout.strip()
    except Exception:
        return ""


class SecurityCollector(BaseCollector):
    name = "macos.security"

    def _collect(self) -> dict:
        return {
            "antivirus": [],
            "firewall": self._get_firewall(),
            "uac_enabled": None,
            "encryption": {"filevault_enabled": self._get_filevault()},
            "windows_defender": None,
            "secure_boot_enabled": None,
            "gatekeeper_enabled": self._get_gatekeeper(),
            "sip_enabled": self._get_sip(),
        }

    def _get_filevault(self):
        out = _run(["fdesetup", "status"])
        if "On" in out:
            return True
        if "Off" in out:
            return False
        return None

    def _get_gatekeeper(self):
        out = _run(["spctl", "--status"])
        if "enabled" in out.lower():
            return True
        if "disabled" in out.lower():
            return False
        return None

    def _get_sip(self):
        out = _run(["csrutil", "status"])
        if "enabled" in out.lower():
            return True
        if "disabled" in out.lower():
            return False
        return None

    def _get_firewall(self) -> dict:
        try:
            out = _run([
                "defaults", "read",
                "/Library/Preferences/com.apple.alf", "globalstate",
            ])
            enabled = out.strip() not in ("0", "")
        except Exception:
            enabled = None
        return {
            "domain_enabled": enabled,
            "private_enabled": enabled,
            "public_enabled": enabled,
        }
