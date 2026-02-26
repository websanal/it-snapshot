"""Collect system boot and uptime information."""

import datetime
import psutil


def collect_reboot_time() -> dict:
    """Return last boot time and current uptime."""
    boot_timestamp = psutil.boot_time()
    boot_dt = datetime.datetime.fromtimestamp(boot_timestamp, tz=datetime.timezone.utc)
    now_dt = datetime.datetime.now(tz=datetime.timezone.utc)
    uptime = now_dt - boot_dt

    total_seconds = int(uptime.total_seconds())
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    return {
        "last_boot_utc": boot_dt.isoformat(),
        "snapshot_utc": now_dt.isoformat(),
        "uptime": {
            "total_seconds": total_seconds,
            "days": days,
            "hours": hours,
            "minutes": minutes,
            "seconds": seconds,
            "human_readable": f"{days}d {hours}h {minutes}m {seconds}s",
        },
    }
