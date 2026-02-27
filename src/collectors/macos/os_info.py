"""Collect macOS OS version, build, and boot information."""

import datetime
import re

from ..base import BaseCollector
from . import _utils


class OsInfoCollector(BaseCollector):
    name = "macos.os_info"

    def _collect(self) -> dict:
        return {
            "edition":          self._get_value("sw_vers", "-productName"),
            "version":          self._get_value("sw_vers", "-productVersion"),
            "build":            self._get_value("sw_vers", "-buildVersion"),
            "install_date":     None,   # not reliably available on macOS
            "last_boot":        self._get_last_boot(),
            "registered_owner": None,
            "patches":          self._get_patches(),
            "local_admins":     self._get_local_admins(),
        }

    def _get_value(self, *cmd) -> str | None:
        return _utils.run_cmd(list(cmd)) or None

    def _get_last_boot(self) -> str | None:
        """Parse kern.boottime sysctl output → ISO UTC string."""
        raw = _utils.run_cmd(["sysctl", "-n", "kern.boottime"])
        # Output: { sec = 1740000000, usec = 0 } Thu Feb 20 08:00:00 2025
        m = re.search(r"sec\s*=\s*(\d+)", raw)
        if m:
            ts = int(m.group(1))
            dt = datetime.datetime.utcfromtimestamp(ts)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        return None

    def _get_patches(self) -> dict:
        """List recently installed software updates via softwareupdate --history."""
        raw = _utils.run_cmd(["softwareupdate", "--history"], timeout=30)
        packages = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("Display Name") or line.startswith("---"):
                continue
            packages.append(line)
        return {
            "count":          len(packages),
            "last_installed": None,
            "packages":       packages[:50],
        }

    def _get_local_admins(self) -> list | None:
        """List members of the local admin group via dscl."""
        raw = _utils.run_cmd(["dscl", ".", "-read", "/Groups/admin", "GroupMembership"])
        if not raw:
            return None
        # Output: GroupMembership: root user1 user2
        parts = raw.replace("GroupMembership:", "").split()
        return [p.strip() for p in parts if p.strip()]
