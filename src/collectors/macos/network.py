"""Collect macOS network configuration."""

import re
import socket

import psutil

from ..base import BaseCollector
from . import _utils


class NetworkCollector(BaseCollector):
    name = "macos.network"

    def _collect(self) -> dict:
        adapters = self._get_adapters()
        return {
            "adapters":        adapters,
            "wifi_ssid":       self._get_wifi_ssid(),
            "dns_servers":     self._get_dns(),
            "default_gateway": self._get_gateway(),
        }

    # ── Adapters ──────────────────────────────────────────────────────────────

    def _get_adapters(self) -> list:
        adapters = []
        net_addrs = psutil.net_if_addrs()
        net_stats = psutil.net_if_stats()

        for name, addrs in net_addrs.items():
            mac   = None
            ipv4s = []
            ipv6s = []

            for addr in addrs:
                if addr.family == psutil.AF_LINK:
                    if addr.address and addr.address not in ("", "00:00:00:00:00:00"):
                        mac = addr.address
                elif addr.family == socket.AF_INET:
                    ipv4s.append(addr.address)
                elif addr.family == socket.AF_INET6:
                    ipv6s.append(addr.address)

            stats = net_stats.get(name)
            adapters.append({
                "name":           name,
                "mac_address":    mac,
                "ip_addresses":   ipv4s,
                "ipv6_addresses": ipv6s,
                "is_up":          stats.isup  if stats else None,
                "speed_mbps":     stats.speed if stats else None,
                "driver_version": None,
                "dhcp_enabled":   None,
                "gateway":        None,
                "dns_servers":    [],
            })
        return adapters

    # ── Wi-Fi SSID ────────────────────────────────────────────────────────────

    def _get_wifi_ssid(self) -> str | None:
        # Try airport utility (available on most macOS versions)
        airport = (
            "/System/Library/PrivateFrameworks/Apple80211.framework"
            "/Versions/Current/Resources/airport"
        )
        raw = _utils.run_cmd([airport, "-I"])
        if raw:
            for line in raw.splitlines():
                if "SSID:" in line and "BSSID:" not in line:
                    ssid = line.split("SSID:", 1)[1].strip()
                    return ssid or None
        # Fallback: networksetup
        raw = _utils.run_cmd(["networksetup", "-getairportnetwork", "en0"])
        if raw and "Current Wi-Fi Network:" in raw:
            return raw.split("Current Wi-Fi Network:", 1)[1].strip() or None
        return None

    # ── DNS + Gateway ─────────────────────────────────────────────────────────

    def _get_dns(self) -> list:
        out = _utils.run_cmd(["scutil", "--dns"])
        servers = []
        for line in out.splitlines():
            m = re.search(r"nameserver\[\d+\]\s*:\s*(\S+)", line)
            if m and m.group(1) not in servers:
                servers.append(m.group(1))
        return servers

    def _get_gateway(self) -> str | None:
        out = _utils.run_cmd(["route", "-n", "get", "default"])
        for line in out.splitlines():
            if "gateway:" in line:
                return line.split("gateway:", 1)[1].strip() or None
        return None
