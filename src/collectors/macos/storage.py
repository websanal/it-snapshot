"""Collect macOS storage information via diskutil and psutil."""

import psutil

from ..base import BaseCollector
from . import _utils


class StorageCollector(BaseCollector):
    name = "macos.storage"

    def _collect(self) -> dict:
        return {
            "physical_disks":  self._get_physical_disks(),
            "logical_volumes": self._get_logical_volumes(),
        }

    # ── Physical disks (diskutil list + info) ─────────────────────────────────

    def _get_physical_disks(self) -> list:
        disks = []
        data = _utils.run_plist(["diskutil", "list", "-plist"])
        whole_disks = data.get("WholeDisks", [])
        for disk_id in whole_disks:
            info = _utils.run_plist(["diskutil", "info", "-plist", f"/dev/{disk_id}"])
            if not info:
                continue
            size_bytes = info.get("TotalSize")
            disks.append({
                "device":      f"/dev/{disk_id}",
                "model":       info.get("MediaName") or info.get("IORegistryEntryName"),
                "serial":      info.get("DiskUUID"),
                "media_type":  "SSD" if info.get("SolidState") else "HDD",
                "interface":   info.get("BusProtocol"),
                "size_gb":     round(size_bytes / (1024 ** 3), 2) if size_bytes else None,
                "removable":   bool(info.get("RemovableMediaOrExternalDevice", False)),
            })
        return disks

    # ── Logical volumes (psutil + FileVault enrichment) ───────────────────────

    def _get_logical_volumes(self) -> list:
        filevault = _filevault_status()
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
                "filevault_enabled":     filevault if part.mountpoint == "/" else None,
            }
            try:
                usage = psutil.disk_usage(part.mountpoint)
                entry.update({
                    "total_gb":     round(usage.total / (1024 ** 3), 2),
                    "used_gb":      round(usage.used  / (1024 ** 3), 2),
                    "free_gb":      round(usage.free  / (1024 ** 3), 2),
                    "percent_used": usage.percent,
                })
            except PermissionError:
                entry["status"] = "permission_denied"
            except OSError as exc:
                entry.update({"status": "error", "error": str(exc)})
            volumes.append(entry)

        return volumes


def _filevault_status() -> bool | None:
    out = _utils.run_cmd(["fdesetup", "status"])
    if "On" in out:
        return True
    if "Off" in out:
        return False
    return None
