"""Collect macOS installed applications via system_profiler."""

import json
import subprocess

from ..base import BaseCollector


class SoftwareCollector(BaseCollector):
    name = "macos.software"

    def _collect(self) -> dict:
        installed = []
        try:
            result = subprocess.run(
                ["system_profiler", "SPApplicationsDataType", "-json"],
                capture_output=True, text=True, timeout=120,
            )
            data = json.loads(result.stdout)
            for app in data.get("SPApplicationsDataType", []):
                installed.append({
                    "name": app.get("_name"),
                    "version": app.get("version"),
                    "publisher": app.get("obtained_from"),
                    "install_date": app.get("lastModified"),
                })
        except Exception:
            pass
        return {"installed": installed, "count": len(installed)}
