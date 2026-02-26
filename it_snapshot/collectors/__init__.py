"""Collector modules for it-snapshot."""

from .os_info import collect_os_info
from .disk_usage import collect_disk_usage
from .reboot_time import collect_reboot_time

__all__ = ["collect_os_info", "collect_disk_usage", "collect_reboot_time"]
