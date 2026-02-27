"""SQLite database initialisation and connection helper.

Schema
------
devices
    One row per unique (hostname, domain) pair. ``last_seen``, ``risk_score``,
    and OS fields are updated on every ingest from the same machine so the row
    always reflects the *current* state of the device.

reports
    Append-only. Every POST /ingest creates one row, keeping the full
    history for a device. ``findings_json`` stores the findings list as JSON;
    ``raw_json`` stores the entire report payload for lossless retrieval.

Configuration
-------------
Set the ``IT_SNAPSHOT_DB`` environment variable to control the database path.
Default: ``<server dir>/db.sqlite``
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import AsyncGenerator

import aiosqlite

DB_PATH: str = os.environ.get(
    "IT_SNAPSHOT_DB",
    str(Path(__file__).parent / "db.sqlite"),
)

_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS devices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    hostname    TEXT    NOT NULL,
    domain      TEXT    NOT NULL DEFAULT '',   -- '' when not domain-joined
    last_seen   TEXT    NOT NULL,              -- ISO-8601 UTC from report
    os_name     TEXT,
    os_version  TEXT,
    risk_score  INTEGER NOT NULL DEFAULT 0,
    UNIQUE (hostname, domain)
);

CREATE INDEX IF NOT EXISTS idx_devices_last_seen
    ON devices (last_seen DESC);

CREATE TABLE IF NOT EXISTS reports (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id     INTEGER NOT NULL REFERENCES devices (id) ON DELETE CASCADE,
    collected_at  TEXT    NOT NULL,            -- ISO-8601 UTC from report
    risk_score    INTEGER NOT NULL DEFAULT 0,
    findings_json TEXT    NOT NULL DEFAULT '[]',
    raw_json      TEXT    NOT NULL,
    ingested_at   TEXT    NOT NULL
                  DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_reports_device_collected
    ON reports (device_id, collected_at DESC);
"""


async def init_db() -> None:
    """Create tables if they do not exist. Called once at server startup."""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.executescript(_DDL)
        await conn.commit()


@contextlib.asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Async context manager that yields a configured SQLite connection.

    Usage::

        async with get_db() as db:
            await db.execute(...)
            await db.commit()
    """
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode = WAL")
        await conn.execute("PRAGMA foreign_keys = ON")
        yield conn
