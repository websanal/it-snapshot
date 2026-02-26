"""Collect disk partition information via psutil."""

import psutil

from ..base import BaseCollector


class StorageCollector(BaseCollector):
    name = "common.storage"

    def _collect(self) -> dict:
        partitions = []
        for part in psutil.disk_partitions(all=False):
            entry = {
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "opts": part.opts,
            }
            try:
                usage = psutil.disk_usage(part.mountpoint)
                entry.update({
                    "total_gb": round(usage.total / (1024 ** 3), 2),
                    "used_gb": round(usage.used / (1024 ** 3), 2),
                    "free_gb": round(usage.free / (1024 ** 3), 2),
                    "percent_used": usage.percent,
                    "status": "ok",
                })
            except PermissionError:
                entry["status"] = "permission_denied"
            except OSError as exc:
                entry.update({"status": "error", "error": str(exc)})
            partitions.append(entry)
        return {"partitions": partitions}
