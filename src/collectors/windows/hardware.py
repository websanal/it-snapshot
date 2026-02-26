"""Collect Windows hardware info (GPU, BIOS, Motherboard) via PowerShell."""

import json

from ..base import BaseCollector
from ._utils import run_powershell


class HardwareCollector(BaseCollector):
    name = "windows.hardware"

    def _collect(self) -> dict:
        return {
            "gpu": self._get_gpu(),
            "bios": self._get_bios(),
            "motherboard": self._get_motherboard(),
        }

    def _get_gpu(self) -> list:
        try:
            ps = run_powershell(
                "Get-WmiObject Win32_VideoController "
                "| Select-Object Name,DriverVersion,AdapterRAM "
                "| ConvertTo-Json -AsArray"
            )
            items = json.loads(ps)
            if isinstance(items, dict):
                items = [items]
            return [
                {
                    "name": item.get("Name"),
                    "driver_version": item.get("DriverVersion"),
                    "vram_mb": (
                        round(item["AdapterRAM"] / (1024 ** 2))
                        if item.get("AdapterRAM")
                        else None
                    ),
                }
                for item in items
            ]
        except Exception:
            return []

    def _get_bios(self) -> dict:
        try:
            ps = run_powershell(
                "Get-WmiObject Win32_BIOS "
                "| Select-Object Manufacturer,SMBIOSBIOSVersion,ReleaseDate "
                "| ConvertTo-Json"
            )
            b = json.loads(ps)
            return {
                "manufacturer": b.get("Manufacturer"),
                "version": b.get("SMBIOSBIOSVersion"),
                "release_date": b.get("ReleaseDate"),
            }
        except Exception:
            return {}

    def _get_motherboard(self) -> dict:
        try:
            ps = run_powershell(
                "Get-WmiObject Win32_BaseBoard "
                "| Select-Object Manufacturer,Product,SerialNumber "
                "| ConvertTo-Json"
            )
            m = json.loads(ps)
            return {
                "manufacturer": m.get("Manufacturer"),
                "product": m.get("Product"),
                "serial": m.get("SerialNumber"),
            }
        except Exception:
            return {}
