"""Collect macOS network configuration."""

import re
import subprocess

from ..base import BaseCollector


def _run(cmd: list) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.stdout.strip()
    except Exception:
        return ""


class NetworkCollector(BaseCollector):
    name = "macos.network"

    def _collect(self) -> dict:
        return {
            "dns_servers": self._get_dns(),
            "default_gateway": self._get_gateway(),
        }

    def _get_dns(self) -> list:
        out = _run(["scutil", "--dns"])
        servers = []
        for line in out.splitlines():
            m = re.search(r"nameserver\[\d+\]\s*:\s*(\S+)", line)
            if m and m.group(1) not in servers:
                servers.append(m.group(1))
        return servers

    def _get_gateway(self):
        out = _run(["route", "-n", "get", "default"])
        for line in out.splitlines():
            if "gateway:" in line:
                return line.split("gateway:", 1)[1].strip()
        return None
