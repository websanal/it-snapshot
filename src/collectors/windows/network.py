"""Collect Windows network configuration via PowerShell."""

import json

from ..base import BaseCollector
from ._utils import run_powershell


class NetworkCollector(BaseCollector):
    name = "windows.network"

    def _collect(self) -> dict:
        return {
            "dns_servers": self._get_dns(),
            "default_gateway": self._get_gateway(),
        }

    def _get_dns(self) -> list:
        try:
            ps = run_powershell(
                "Get-DnsClientServerAddress -AddressFamily IPv4 "
                "| Select-Object ServerAddresses "
                "| ConvertTo-Json -AsArray"
            )
            items = json.loads(ps)
            if isinstance(items, dict):
                items = [items]
            seen = []
            for item in items:
                for addr in (item.get("ServerAddresses") or []):
                    if addr and addr not in seen:
                        seen.append(addr)
            return seen
        except Exception:
            return []

    def _get_gateway(self):
        try:
            ps = run_powershell(
                "Get-NetRoute -DestinationPrefix '0.0.0.0/0' "
                "| Sort-Object RouteMetric "
                "| Select-Object -First 1 -ExpandProperty NextHop"
            )
            return ps.strip() or None
        except Exception:
            return None
