"""Collect operating system information."""

import platform
import socket
import os
import psutil


def collect_os_info() -> dict:
    """Return a dictionary of OS and hardware information."""
    uname = platform.uname()
    cpu_freq = psutil.cpu_freq()
    ram = psutil.virtual_memory()

    return {
        "hostname": socket.gethostname(),
        "os": {
            "name": uname.system,
            "version": uname.version,
            "release": uname.release,
            "build": platform.version(),
        },
        "architecture": uname.machine,
        "processor": uname.processor or platform.processor(),
        "cpu": {
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
            "max_frequency_mhz": round(cpu_freq.max, 2) if cpu_freq else None,
            "current_frequency_mhz": round(cpu_freq.current, 2) if cpu_freq else None,
        },
        "ram": {
            "total_gb": round(ram.total / (1024 ** 3), 2),
            "available_gb": round(ram.available / (1024 ** 3), 2),
            "used_gb": round(ram.used / (1024 ** 3), 2),
            "percent_used": ram.percent,
        },
        "python_version": platform.python_version(),
        "current_user": os.environ.get("USERNAME") or os.environ.get("USER", "unknown"),
    }
