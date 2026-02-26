"""Collect macOS hardware info via system_profiler."""

import json
import subprocess

from ..base import BaseCollector


def _sp(data_type: str) -> dict:
    result = subprocess.run(
        ["system_profiler", data_type, "-json"],
        capture_output=True, text=True, timeout=60,
    )
    return json.loads(result.stdout)


class HardwareCollector(BaseCollector):
    name = "macos.hardware"

    def _collect(self) -> dict:
        gpu = []
        motherboard = {}

        try:
            data = _sp("SPHardwareDataType")
            hw = data.get("SPHardwareDataType", [{}])[0]
            motherboard = {
                "manufacturer": "Apple Inc.",
                "product": hw.get("machine_model"),
                "serial": hw.get("serial_number"),
            }
        except Exception:
            pass

        try:
            data = _sp("SPDisplaysDataType")
            for d in data.get("SPDisplaysDataType", []):
                gpu.append({
                    "name": d.get("sppci_model"),
                    "driver_version": d.get("spdisplays_metalfamily"),
                    "vram_mb": None,
                })
        except Exception:
            pass

        return {"gpu": gpu, "bios": {}, "motherboard": motherboard}
