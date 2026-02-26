"""Collect network interface information via psutil."""

import socket

import psutil

from ..base import BaseCollector


class NetworkCollector(BaseCollector):
    name = "common.network"

    def _collect(self) -> dict:
        interfaces = []
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()

        for name, addr_list in addrs.items():
            iface_stats = stats.get(name)
            ip_addresses = []
            ipv6_addresses = []
            mac_address = None

            for addr in addr_list:
                if addr.family == socket.AF_INET:
                    ip_addresses.append(addr.address)
                elif addr.family == socket.AF_INET6:
                    ipv6_addresses.append(addr.address)
                elif addr.family == psutil.AF_LINK:
                    mac_address = addr.address

            interfaces.append({
                "name": name,
                "mac_address": mac_address,
                "ip_addresses": ip_addresses,
                "ipv6_addresses": ipv6_addresses,
                "is_up": iface_stats.isup if iface_stats else False,
                "speed_mbps": iface_stats.speed if iface_stats else None,
            })

        return {"interfaces": interfaces}
