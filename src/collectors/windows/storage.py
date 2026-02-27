"""Collect detailed Windows storage information (physical disks + logical volumes)."""

import json

import psutil

from ..base import BaseCollector
from . import _utils


def _loads_array(ps_output: str) -> list:
    try:
        data = json.loads(ps_output)
        return data if isinstance(data, list) else [data]
    except Exception:
        return []


class StorageCollector(BaseCollector):
    name = "windows.storage"

    def _collect(self) -> dict:
        return {
            "physical_disks":  self._get_physical_disks(),
            "logical_volumes": self._get_logical_volumes(),
        }

    # ── Physical disks (Win32_DiskDrive) ─────────────────────────────────────

    def _get_physical_disks(self) -> list:
        try:
            ps = _utils.run_powershell(
                "Get-CimInstance Win32_DiskDrive "
                "| Select-Object Model,SerialNumber,MediaType,Size,InterfaceType "
                "| ConvertTo-Json"
            )
            disks = []
            for d in _loads_array(ps):
                raw_size = d.get("Size")
                try:
                    size_bytes = int(raw_size) if raw_size else None
                except (TypeError, ValueError):
                    size_bytes = None
                disks.append({
                    "model":      (d.get("Model")        or "").strip() or None,
                    "serial":     (d.get("SerialNumber") or "").strip() or None,
                    "media_type": (d.get("MediaType")    or "").strip() or None,
                    "interface":  (d.get("InterfaceType") or "").strip() or None,
                    "size_gb":    round(size_bytes / (1024 ** 3), 2) if size_bytes else None,
                })
            return disks
        except Exception:
            return []

    # ── Logical volumes (psutil + BitLocker enrichment) ───────────────────────

    def _get_logical_volumes(self) -> list:
        volumes = []

        for part in psutil.disk_partitions(all=False):
            entry: dict = {
                "drive_letter":          part.mountpoint,
                "device":                part.device,
                "fstype":                part.fstype,
                "total_gb":              None,
                "used_gb":               None,
                "free_gb":               None,
                "percent_used":          None,
                "status":                "ok",
                "bitlocker_status":      None,
                "bitlocker_protection":  None,
            }
            try:
                usage = psutil.disk_usage(part.mountpoint)
                entry.update({
                    "total_gb":    round(usage.total / (1024 ** 3), 2),
                    "used_gb":     round(usage.used  / (1024 ** 3), 2),
                    "free_gb":     round(usage.free  / (1024 ** 3), 2),
                    "percent_used": usage.percent,
                })
            except PermissionError:
                entry["status"] = "permission_denied"
            except OSError as exc:
                entry.update({"status": "error", "error": str(exc)})

            volumes.append(entry)

        # Enrich with BitLocker status
        try:
            ps = _utils.run_powershell(
                "Get-BitLockerVolume "
                "| Select-Object MountPoint,VolumeStatus,ProtectionStatus "
                "| ConvertTo-Json"
            )
            bl_map = {
                item.get("MountPoint", "").rstrip("\\"): item
                for item in _loads_array(ps)
            }
            for vol in volumes:
                key = vol["drive_letter"].rstrip("\\")
                bl = bl_map.get(key)
                if bl:
                    vol["bitlocker_status"] = str(bl.get("VolumeStatus") or "")
                    ps_val = bl.get("ProtectionStatus")
                    vol["bitlocker_protection"] = (
                        "On" if ps_val == 1 else "Off" if ps_val == 0 else str(ps_val)
                    )
        except Exception:
            pass

        return volumes
