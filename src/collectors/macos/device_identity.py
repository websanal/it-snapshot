"""Collect macOS device identity information."""

import socket

import psutil

from ..base import BaseCollector
from . import _utils


class DeviceIdentityCollector(BaseCollector):
    name = "macos.device_identity"

    def _collect(self) -> dict:
        hostname = socket.gethostname()
        fqdn     = socket.getfqdn()

        platform_uuid = None
        try:
            data = _utils.run_json(["system_profiler", "SPHardwareDataType", "-json"])
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
            "hostname":          hostname,
            "fqdn":              fqdn,
            "domain":            self._get_domain(),
            "workgroup":         None,
            "os_machine_id":     platform_uuid,
            "primary_macs":      primary_macs[:4],
            "azure_ad_device_id": None,
        }

    def _get_domain(self) -> str | None:
        raw = _utils.run_cmd(["scutil", "--get", "LocalHostName"])
        return raw or None
