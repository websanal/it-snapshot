"""Collect macOS hardware info via system_profiler and psutil."""

import psutil

from ..base import BaseCollector
from . import _utils


class HardwareCollector(BaseCollector):
    name = "macos.hardware"

    def _collect(self) -> dict:
        return {
            "cpu":          self._get_cpu(),
            "ram":          self._get_ram(),
            "gpu":          self._get_gpu(),
            "motherboard":  self._get_motherboard(),
            "bios":         {},
            "tpm":          {},
            "secure_boot":  {},
            "monitors":     self._get_monitors(),
            "printers":     [],
        }

    # ── CPU ──────────────────────────────────────────────────────────────────

    def _get_cpu(self) -> dict:
        result: dict = {
            "brand":                None,
            "manufacturer":         None,
            "physical_cores":       psutil.cpu_count(logical=False),
            "logical_cores":        psutil.cpu_count(logical=True),
            "max_frequency_mhz":    None,
            "current_frequency_mhz": None,
            "usage_percent":        psutil.cpu_percent(interval=0.5),
        }
        try:
            freq = psutil.cpu_freq()
            if freq:
                result["max_frequency_mhz"]      = round(freq.max,     2)
                result["current_frequency_mhz"]  = round(freq.current, 2)
        except Exception:
            pass
        try:
            data = _utils.run_json(["system_profiler", "SPHardwareDataType", "-json"])
            hw = data.get("SPHardwareDataType", [{}])[0]
            brand = hw.get("cpu_type") or hw.get("chip_type")
            if brand:
                result["brand"] = brand
            # Apple Silicon vs Intel
            chip = hw.get("chip_type") or ""
            if "Apple" in chip:
                result["manufacturer"] = "Apple"
            else:
                result["manufacturer"] = "Intel"
        except Exception:
            pass
        return result

    # ── RAM ──────────────────────────────────────────────────────────────────

    def _get_ram(self) -> dict:
        mem = psutil.virtual_memory()
        result: dict = {
            "total_gb":     round(mem.total     / (1024 ** 3), 2),
            "available_gb": round(mem.available / (1024 ** 3), 2),
            "used_gb":      round(mem.used      / (1024 ** 3), 2),
            "percent_used": mem.percent,
            "modules":      [],
        }
        try:
            data = _utils.run_json(["system_profiler", "SPMemoryDataType", "-json"])
            for slot_group in data.get("SPMemoryDataType", []):
                for item in slot_group.get("_items", []):
                    result["modules"].append({
                        "slot":         item.get("dimm_slot") or item.get("_name"),
                        "capacity_gb":  _parse_size_gb(item.get("dimm_size") or item.get("size")),
                        "speed_mhz":    _parse_speed_mhz(item.get("dimm_speed") or item.get("speed")),
                        "manufacturer": item.get("dimm_manufacturer") or item.get("vendor"),
                        "part_number":  item.get("dimm_part_number") or item.get("part-number"),
                        "serial":       item.get("dimm_serial_number"),
                    })
        except Exception:
            pass
        return result

    # ── GPU ──────────────────────────────────────────────────────────────────

    def _get_gpu(self) -> list:
        gpu = []
        try:
            data = _utils.run_json(["system_profiler", "SPDisplaysDataType", "-json"])
            for d in data.get("SPDisplaysDataType", []):
                vram_mb = None
                vram_str = (d.get("spdisplays_vram") or d.get("spdisplays_vram_shared") or "")
                if vram_str:
                    try:
                        vram_mb = int(vram_str.split()[0])
                    except Exception:
                        pass
                gpu.append({
                    "name":           d.get("sppci_model") or d.get("_name"),
                    "driver_version": d.get("spdisplays_metalfamily") or d.get("spdisplays_gmux_version"),
                    "vram_mb":        vram_mb,
                })
        except Exception:
            pass
        return gpu

    # ── Motherboard (Mac model info) ──────────────────────────────────────────

    def _get_motherboard(self) -> dict:
        try:
            data = _utils.run_json(["system_profiler", "SPHardwareDataType", "-json"])
            hw = data.get("SPHardwareDataType", [{}])[0]
            return {
                "manufacturer": "Apple Inc.",
                "product":      hw.get("machine_model"),
                "serial":       hw.get("serial_number"),
            }
        except Exception:
            return {"manufacturer": "Apple Inc.", "product": None, "serial": None}

    # ── Monitors ─────────────────────────────────────────────────────────────

    def _get_monitors(self) -> list:
        monitors = []
        try:
            data = _utils.run_json(["system_profiler", "SPDisplaysDataType", "-json"])
            for d in data.get("SPDisplaysDataType", []):
                for monitor in d.get("spdisplays_ndrvs", []):
                    monitors.append({
                        "name":       monitor.get("_name"),
                        "resolution": monitor.get("spdisplays_resolution"),
                    })
        except Exception:
            pass
        return monitors


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_size_gb(s) -> float | None:
    if not s:
        return None
    try:
        parts = str(s).split()
        val  = float(parts[0].replace(",", ""))
        unit = parts[1].upper() if len(parts) > 1 else "GB"
        if unit in ("GB", "GIB"):
            return round(val, 2)
        if unit in ("MB", "MIB"):
            return round(val / 1024, 2)
        if unit in ("TB", "TIB"):
            return round(val * 1024, 2)
    except Exception:
        pass
    return None


def _parse_speed_mhz(s) -> int | None:
    if not s:
        return None
    try:
        return int(str(s).split()[0].replace(",", ""))
    except Exception:
        return None
