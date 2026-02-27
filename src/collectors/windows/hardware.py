"""Collect detailed Windows hardware information via CIM/WMI."""

import json

import psutil

from ..base import BaseCollector
from . import _utils


def _loads_array(ps_output: str) -> list:
    """Parse PowerShell JSON output; always return a list."""
    try:
        data = json.loads(ps_output)
        return data if isinstance(data, list) else [data]
    except Exception:
        return []


def _loads_obj(ps_output: str) -> dict:
    try:
        data = json.loads(ps_output)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


class HardwareCollector(BaseCollector):
    name = "windows.hardware"

    def _collect(self) -> dict:
        return {
            "cpu":          self._get_cpu(),
            "ram":          self._get_ram(),
            "gpu":          self._get_gpu(),
            "motherboard":  self._get_motherboard(),
            "bios":         self._get_bios(),
            "tpm":          self._get_tpm(),
            "secure_boot":  self._get_secure_boot(),
            "monitors":     self._get_monitors(),
            "printers":     self._get_printers(),
        }

    # ── CPU ──────────────────────────────────────────────────────────────────

    def _get_cpu(self) -> dict:
        base: dict = {}
        try:
            freq = psutil.cpu_freq()
            base = {
                "physical_cores":     psutil.cpu_count(logical=False),
                "logical_processors": psutil.cpu_count(logical=True),
                "max_clock_mhz":      round(freq.max, 2) if freq else None,
                "current_clock_mhz":  round(freq.current, 2) if freq else None,
                "usage_percent":      psutil.cpu_percent(interval=0.5),
            }
        except Exception:
            pass

        try:
            ps = _utils.run_powershell(
                "Get-CimInstance Win32_Processor "
                "| Select-Object Name,Manufacturer,NumberOfCores,"
                "NumberOfLogicalProcessors,MaxClockSpeed "
                "| ConvertTo-Json"
            )
            items = _loads_array(ps)
            if items:
                c = items[0]
                base["name"]               = (c.get("Name") or "").strip() or None
                base["manufacturer"]       = (c.get("Manufacturer") or "").strip() or None
                base["physical_cores"]     = c.get("NumberOfCores",    base.get("physical_cores"))
                base["logical_processors"] = c.get("NumberOfLogicalProcessors", base.get("logical_processors"))
                base["max_clock_mhz"]      = c.get("MaxClockSpeed",   base.get("max_clock_mhz"))
        except Exception:
            pass

        return base

    # ── RAM ──────────────────────────────────────────────────────────────────

    def _get_ram(self) -> dict:
        result: dict = {}
        try:
            vm = psutil.virtual_memory()
            result = {
                "total_bytes":   vm.total,
                "total_gb":      round(vm.total     / (1024 ** 3), 2),
                "available_gb":  round(vm.available / (1024 ** 3), 2),
                "used_gb":       round(vm.used      / (1024 ** 3), 2),
                "percent_used":  vm.percent,
                "modules":       [],
            }
        except Exception:
            result.setdefault("modules", [])

        try:
            ps = _utils.run_powershell(
                "Get-CimInstance Win32_PhysicalMemory "
                "| Select-Object DeviceLocator,Capacity,Speed,"
                "Manufacturer,PartNumber,SerialNumber "
                "| ConvertTo-Json"
            )
            for m in _loads_array(ps):
                cap = m.get("Capacity") or 0
                sn  = (m.get("SerialNumber") or "").strip()
                result["modules"].append({
                    "slot":        (m.get("DeviceLocator") or "").strip() or None,
                    "capacity_gb": round(cap / (1024 ** 3), 2) if cap else None,
                    "speed_mhz":   m.get("Speed"),
                    "manufacturer": (m.get("Manufacturer") or "").strip() or None,
                    "part_number":  (m.get("PartNumber") or "").strip() or None,
                    "serial":       sn if sn and sn.lower() not in ("", "unknown", "not specified") else None,
                })
        except Exception:
            pass

        return result

    # ── GPU ──────────────────────────────────────────────────────────────────

    def _get_gpu(self) -> list:
        try:
            ps = _utils.run_powershell(
                "Get-CimInstance Win32_VideoController "
                "| Select-Object Name,DriverVersion,AdapterRAM "
                "| ConvertTo-Json"
            )
            return [
                {
                    "name":           (item.get("Name") or "").strip() or None,
                    "driver_version": item.get("DriverVersion"),
                    "vram_mb":        round(item["AdapterRAM"] / (1024 ** 2))
                                      if item.get("AdapterRAM") else None,
                }
                for item in _loads_array(ps)
            ]
        except Exception:
            return []

    # ── Motherboard / BIOS ───────────────────────────────────────────────────

    def _get_motherboard(self) -> dict:
        try:
            ps = _utils.run_powershell(
                "Get-CimInstance Win32_BaseBoard "
                "| Select-Object Manufacturer,Product,SerialNumber "
                "| ConvertTo-Json"
            )
            m = _loads_obj(ps)
            return {
                "manufacturer": (m.get("Manufacturer") or "").strip() or None,
                "product":      (m.get("Product")      or "").strip() or None,
                "serial":       (m.get("SerialNumber")  or "").strip() or None,
            }
        except Exception:
            return {}

    def _get_bios(self) -> dict:
        try:
            ps = _utils.run_powershell(
                "Get-CimInstance Win32_BIOS "
                "| Select-Object Manufacturer,SMBIOSBIOSVersion,ReleaseDate "
                "| ConvertTo-Json"
            )
            b = _loads_obj(ps)
            return {
                "vendor":       (b.get("Manufacturer")    or "").strip() or None,
                "version":      b.get("SMBIOSBIOSVersion"),
                "release_date": str(b.get("ReleaseDate") or "").strip() or None,
            }
        except Exception:
            return {}

    # ── TPM ──────────────────────────────────────────────────────────────────

    def _get_tpm(self) -> dict:
        result: dict = {"present": None, "version": None}
        try:
            ps = _utils.run_powershell(
                "Get-Tpm | Select-Object TpmPresent,TpmReady | ConvertTo-Json"
            )
            t = _loads_obj(ps)
            result["present"] = bool(t.get("TpmPresent"))
            result["ready"]   = bool(t.get("TpmReady"))
        except Exception:
            pass

        try:
            ps2 = _utils.run_powershell(
                "Get-WmiObject -Namespace root/cimv2/security/microsofttpm "
                "-Class Win32_Tpm "
                "| Select-Object SpecVersion | ConvertTo-Json"
            )
            v = _loads_obj(ps2)
            spec = v.get("SpecVersion") or ""
            # SpecVersion looks like "2.0, 1.16, ..." — take first token
            result["version"] = spec.split(",")[0].strip() if spec else None
        except Exception:
            pass

        return result

    # ── Secure Boot ──────────────────────────────────────────────────────────

    def _get_secure_boot(self) -> dict:
        try:
            ps = _utils.run_powershell("Confirm-SecureBootUEFI")
            return {"enabled": ps.strip().lower() == "true"}
        except Exception:
            return {"enabled": None}

    # ── Peripherals ──────────────────────────────────────────────────────────

    def _get_monitors(self) -> list:
        try:
            ps = _utils.run_powershell(
                "Get-CimInstance Win32_DesktopMonitor "
                "| Select-Object Name,MonitorManufacturer,ScreenWidth,ScreenHeight "
                "| ConvertTo-Json"
            )
            result = []
            for item in _loads_array(ps):
                w, h = item.get("ScreenWidth"), item.get("ScreenHeight")
                result.append({
                    "name":         (item.get("Name") or "").strip() or None,
                    "manufacturer": item.get("MonitorManufacturer"),
                    "resolution":   f"{w}x{h}" if w and h else None,
                })
            return result
        except Exception:
            return []

    def _get_printers(self) -> list:
        try:
            ps = _utils.run_powershell(
                "Get-CimInstance Win32_Printer "
                "| Select-Object Name,Default,Network "
                "| ConvertTo-Json"
            )
            return [
                {
                    "name":    item.get("Name"),
                    "default": bool(item.get("Default")),
                    "network": bool(item.get("Network")),
                }
                for item in _loads_array(ps)
            ]
        except Exception:
            return []
