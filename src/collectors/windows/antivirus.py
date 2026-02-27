"""Collect detailed antivirus status from Windows SecurityCenter2 and Defender."""

from __future__ import annotations

import json

from ..base import BaseCollector
from . import _utils


class AntivirusCollector(BaseCollector):
    name = "windows.antivirus"

    def _collect(self) -> dict:
        products = self._query_security_center()
        defender = self._query_defender()
        return {
            "products": products,
            "defender": defender,
            "any_active": any(p.get("enabled") for p in products),
        }

    # ── SecurityCenter2 ────────────────────────────────────────────────────────

    def _query_security_center(self) -> list[dict]:
        """Query WMI SecurityCenter2 for all registered antivirus products.

        Returns a list compatible with the existing security.antivirus schema
        shape, enriched with exe_path and timestamp.
        """
        try:
            ps = _utils.run_powershell(
                "Get-WmiObject -Namespace root/SecurityCenter2 -Class AntiVirusProduct "
                "| Select-Object displayName,productState,"
                "pathToSignedProductExe,pathToSignedReportingExe,timestamp "
                "| ConvertTo-Json"
            )
            raw = json.loads(ps)
            if isinstance(raw, dict):
                raw = [raw]

            result = []
            for item in raw:
                state = item.get("productState") or 0
                hex_state = format(int(state), "06x")
                # Byte 2 of the productState hex encodes run state (10 = enabled)
                # Byte 3 encodes definition update status (00 = up-to-date)
                enabled    = hex_state[2:4] == "10"
                up_to_date = hex_state[4:6] == "00"
                result.append({
                    "name":          item.get("displayName"),
                    "enabled":       enabled,
                    "up_to_date":    up_to_date,
                    "product_state": int(state),
                    "exe_path":      item.get("pathToSignedProductExe") or None,
                    "timestamp":     item.get("timestamp") or None,
                })
            return result
        except Exception:
            return []

    # ── Windows Defender ───────────────────────────────────────────────────────

    def _query_defender(self) -> dict:
        """Query Get-MpComputerStatus for detailed Windows Defender telemetry."""
        empty = {
            "enabled":               None,
            "real_time_protection":  None,
            "on_access_protection":  None,
            "behavior_monitor":      None,
            "signatures_last_updated": None,
            "signature_version":     None,
            "engine_version":        None,
            "product_version":       None,
            "last_full_scan":        None,
            "last_quick_scan":       None,
        }
        try:
            ps = _utils.run_powershell(
                "Get-MpComputerStatus "
                "| Select-Object AMServiceEnabled,RealTimeProtectionEnabled,"
                "OnAccessProtectionEnabled,BehaviorMonitorEnabled,"
                "AntivirusSignatureLastUpdated,AntivirusSignatureVersion,"
                "AMEngineVersion,AMProductVersion,"
                "FullScanEndTime,QuickScanEndTime "
                "| ConvertTo-Json"
            )
            d = json.loads(ps)
            return {
                "enabled":               d.get("AMServiceEnabled"),
                "real_time_protection":  d.get("RealTimeProtectionEnabled"),
                "on_access_protection":  d.get("OnAccessProtectionEnabled"),
                "behavior_monitor":      d.get("BehaviorMonitorEnabled"),
                "signatures_last_updated": str(d.get("AntivirusSignatureLastUpdated") or "") or None,
                "signature_version":     d.get("AntivirusSignatureVersion"),
                "engine_version":        d.get("AMEngineVersion"),
                "product_version":       d.get("AMProductVersion"),
                "last_full_scan":        str(d.get("FullScanEndTime") or "") or None,
                "last_quick_scan":       str(d.get("QuickScanEndTime") or "") or None,
            }
        except Exception:
            return empty
