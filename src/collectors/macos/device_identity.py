"""Collect macOS device identity information."""

import json
import socket
import subprocess

import psutil

from ..base import BaseCollector


def _run(cmd: list, timeout: int = 30) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return result.stdout.strip()


class DeviceIdentityCollector(BaseCollector):
    name = "macos.device_identity"

    def _collect(self) -> dict:
        hostname = socket.gethostname()
        fqdn = socket.getfqdn()

        platform_uuid = None
        try:
            raw = _run(["system_profiler", "SPHardwareDataType", "-json"])
            data = json.loads(raw)
            hw = data.get("SPHardwareDataType", [{}])[0]
            platform_uuid = hw.get("platform_UUID")
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

        return {
            "hostname": hostname,
            "fqdn": fqdn,
            "domain": None,
            "workgroup": None,
            "os_machine_id": platform_uuid,
            "primary_macs": primary_macs[:4],
            "azure_ad_device_id": None,
        }
