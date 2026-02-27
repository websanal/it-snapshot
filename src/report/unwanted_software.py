"""Load and match the unwanted software list from config/unwanted_apps.yaml."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

# Resolved once at import time; works regardless of working directory.
_DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "unwanted_apps.yaml"


@lru_cache(maxsize=1)
def _load_patterns(config_path: str) -> list[dict]:
    """Parse the YAML and return the patterns list. Result is cached."""
    path = Path(config_path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data.get("patterns", [])


def load_patterns(config_path: Path | None = None) -> list[dict]:
    return _load_patterns(str(config_path or _DEFAULT_CONFIG))


def match_installed(
    installed: list[dict],
    config_path: Path | None = None,
) -> list[dict]:
    """Return a match record for every installed app that hits a pattern.

    Args:
        installed: List of software dicts with at least a ``name`` key,
                   as produced by ``SoftwareCollector``.
        config_path: Optional override for the YAML path.

    Returns:
        List of dicts::

            {
                "installed_name": str,   # full name as reported by Windows
                "pattern":        str,   # the pattern that matched
                "category":       str,
                "reason":         str,
                "severity":       str,   # low | medium | high
            }
    """
    patterns = load_patterns(config_path)
    if not patterns:
        return []

    matches: list[dict] = []
    for app in installed:
        app_name: str = app.get("name") or ""
        app_lower = app_name.lower()
        for entry in patterns:
            pattern: str = entry.get("name") or ""
            if pattern.lower() in app_lower:
                matches.append({
                    "installed_name": app_name,
                    "pattern":        pattern,
                    "category":       entry.get("category", "Uncategorized"),
                    "reason":         entry.get("reason", ""),
                    "severity":       entry.get("severity", "medium"),
                })
                break  # one finding per app — first matching pattern wins
    return matches
