"""Collect detailed Windows network information."""

import json

from ..base import BaseCollector
from . import _utils


def _loads_array(ps_output: str) -> list:
    try:
        data = json.loads(ps_output)
        return data if isinstance(data, list) else [data]
    except Exception:
        return []


class NetworkCollector(BaseCollector):
    name = "windows.network"

    def _collect(self) -> dict:
        adapters = self._get_adapters()
        return {
            "adapters":        adapters,
            "wifi_ssid":       self._get_wifi_ssid(),
            "dns_servers":     self._aggregate_dns(adapters),
            "default_gateway": self._get_gateway(),
        }

    # ── Adapters (Get-NetAdapter + Get-NetIPConfiguration) ───────────────────

    def _get_adapters(self) -> list:
        try:
            ps = r"""
$adapters = Get-NetAdapter
$result = foreach ($a in $adapters) {
    $cfg  = Get-NetIPConfiguration -InterfaceIndex $a.ifIndex -ErrorAction SilentlyContinue
    $dns  = (Get-DnsClientServerAddress -InterfaceIndex $a.ifIndex `
              -AddressFamily IPv4 -ErrorAction SilentlyContinue).ServerAddresses
    $dv   = (Get-NetAdapterAdvancedProperty -Name $a.Name `
              -DisplayName 'Driver Version' -ErrorAction SilentlyContinue).DisplayValue
    [PSCustomObject]@{
        Name          = $a.Name
        Description   = $a.InterfaceDescription
        MacAddress    = $a.MacAddress
        Status        = [string]$a.Status
        LinkSpeed     = [string]$a.LinkSpeed
        DriverVersion = $dv
        IpAddresses   = @($cfg.IPv4Address.IPAddress)
        IPv6Addresses = @($cfg.IPv6Address.IPAddress)
        DhcpEnabled   = ($cfg.IPv4Address.PrefixOrigin -contains 'Dhcp')
        Gateway       = $cfg.IPv4DefaultGateway.NextHop
        DnsServers    = @($dns)
    }
}
$result | ConvertTo-Json
"""
            items = _loads_array(_utils.run_powershell(ps, timeout=45))
            adapters = []
            for item in items:
                adapters.append({
                    "name":          item.get("Name"),
                    "description":   item.get("Description"),
                    "mac_address":   item.get("MacAddress"),
                    "status":        item.get("Status"),
                    "link_speed":    item.get("LinkSpeed"),
                    "driver_version": item.get("DriverVersion"),
                    "ip_addresses":   [ip for ip in (item.get("IpAddresses")  or []) if ip],
                    "ipv6_addresses": [ip for ip in (item.get("IPv6Addresses") or []) if ip],
                    "dhcp_enabled":   bool(item.get("DhcpEnabled")),
                    "gateway":        item.get("Gateway"),
                    "dns_servers":    [d for d in (item.get("DnsServers") or []) if d],
                })
            return adapters
        except Exception:
            return []

    # ── Wi-Fi SSID ────────────────────────────────────────────────────────────

    def _get_wifi_ssid(self):
        out = _utils.run_command(["netsh", "wlan", "show", "interfaces"])
        for line in out.splitlines():
            if "SSID" in line and "BSSID" not in line and ":" in line:
                return line.split(":", 1)[1].strip() or None
        return None

    # ── DNS (aggregate unique servers from all adapters) ─────────────────────

    @staticmethod
    def _aggregate_dns(adapters: list) -> list:
        seen: list = []
        for a in adapters:
            for srv in (a.get("dns_servers") or []):
                if srv and srv not in seen:
                    seen.append(srv)
        return seen

    # ── Default gateway ───────────────────────────────────────────────────────

    def _get_gateway(self):
        try:
            ps = (
                "Get-NetRoute -DestinationPrefix '0.0.0.0/0' "
                "| Sort-Object RouteMetric "
                "| Select-Object -First 1 -ExpandProperty NextHop"
            )
            return _utils.run_powershell(ps).strip() or None
        except Exception:
            return None
