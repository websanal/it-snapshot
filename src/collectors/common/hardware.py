"""Collect CPU and RAM information via psutil."""

import psutil

from ..base import BaseCollector


class HardwareCollector(BaseCollector):
    name = "common.hardware"

    def _collect(self) -> dict:
        cpu_freq = psutil.cpu_freq()
        ram = psutil.virtual_memory()
        return {
            "cpu": {
                "physical_cores": psutil.cpu_count(logical=False),
                "logical_cores": psutil.cpu_count(logical=True),
                "max_frequency_mhz": round(cpu_freq.max, 2) if cpu_freq else None,
                "current_frequency_mhz": round(cpu_freq.current, 2) if cpu_freq else None,
                "usage_percent": psutil.cpu_percent(interval=0.5),
            },
            "ram": {
                "total_gb": round(ram.total / (1024 ** 3), 2),
                "available_gb": round(ram.available / (1024 ** 3), 2),
                "used_gb": round(ram.used / (1024 ** 3), 2),
                "percent_used": ram.percent,
            },
        }
