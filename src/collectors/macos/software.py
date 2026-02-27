"""Collect macOS installed applications."""

import os
import plistlib
from pathlib import Path

from ..base import BaseCollector
from . import _utils


class SoftwareCollector(BaseCollector):
    name = "macos.software"

    def _collect(self) -> dict:
        installed = self._get_applications()
        return {
            "installed":     installed,
            "count":         len(installed),
            "startup":       [],
            "pkgutil_count": self._get_pkgutil_count(),
        }

    # ── /Applications scan ────────────────────────────────────────────────────

    def _get_applications(self) -> list:
        apps = []
        search_dirs = [
            Path("/Applications"),
            Path(os.path.expanduser("~/Applications")),
        ]
        for search_dir in search_dirs:
            if not search_dir.is_dir():
                continue
            try:
                items = sorted(search_dir.iterdir())
            except PermissionError:
                continue
            for item in items:
                if not item.name.endswith(".app"):
                    continue
                info = _read_info_plist(item)
                apps.append({
                    "name":         (
                        info.get("CFBundleDisplayName")
                        or info.get("CFBundleName")
                        or item.stem
                    ),
                    "version":      (
                        info.get("CFBundleShortVersionString")
                        or info.get("CFBundleVersion")
                    ),
                    "publisher":    (
                        info.get("CFBundleIdentifier")
                    ),
                    "install_date": None,
                    "bundle_id":    info.get("CFBundleIdentifier"),
                    "path":         str(item),
                })
        return apps

    # ── pkgutil ───────────────────────────────────────────────────────────────

    def _get_pkgutil_count(self) -> int:
        raw = _utils.run_cmd(["pkgutil", "--pkgs"], timeout=30)
        if not raw:
            return 0
        return len([line for line in raw.splitlines() if line.strip()])


# ── Helper ────────────────────────────────────────────────────────────────────

def _read_info_plist(app_path: Path) -> dict:
    """Read Contents/Info.plist from a .app bundle."""
    try:
        plist_path = app_path / "Contents" / "Info.plist"
        if plist_path.exists():
            with open(plist_path, "rb") as f:
                return plistlib.load(f)
    except Exception:
        pass
    return {}
