"""Pydantic models for the inventory server API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── Ingest ────────────────────────────────────────────────────────────────────

class IngestPayload(BaseModel):
    """Minimal required shape of an it-snapshot report.

    ``extra = "allow"`` lets any additional fields through so the server
    stores the full payload regardless of future schema additions.
    """

    schema_version: str
    collected_at: str

    # Optional but expected fields
    agent_version: str | None = None
    run_id:        str | None = None

    # Device identity block (v2)
    device_identity: dict[str, Any] | None = None

    # OS detail block (v2)
    os_detail: dict[str, Any] | None = None

    # Legacy OS block (v1 / v2 compat)
    os: dict[str, Any] | None = None

    # Risk and findings
    risk_score: Any | None = None          # int or {"score": int, "level": str, ...}
    findings:   list[Any] | None = None

    model_config = {"extra": "allow"}


class IngestResponse(BaseModel):
    ok:        bool
    device_id: int
    report_id: int
    hostname:  str


# ── Device list ───────────────────────────────────────────────────────────────

class DeviceSummary(BaseModel):
    id:         int
    hostname:   str
    domain:     str
    last_seen:  str
    os_name:    str | None
    os_version: str | None
    risk_score: int


# ── Reports ───────────────────────────────────────────────────────────────────

class ReportSummary(BaseModel):
    id:           int
    device_id:    int
    collected_at: str
    risk_score:   int
    ingested_at:  str


class ReportDetail(ReportSummary):
    findings: list[Any]
    raw:      dict[str, Any]
