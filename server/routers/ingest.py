"""POST /ingest endpoint — receives and stores agent reports."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from ..auth import require_api_key
from ..db import get_db
from ..models import IngestPayload, IngestResponse

router = APIRouter()

# Schema versions this server can handle
_ACCEPTED_SCHEMA_VERSIONS: frozenset[str] = frozenset({"1.0", "2.0"})


def _extract_device_identity(payload: IngestPayload) -> tuple[str, str]:
    """Return (hostname, domain) from the payload, normalised for storage."""
    dev = payload.device_identity or {}
    hostname: str = (
        dev.get("hostname")
        or (payload.os or {}).get("hostname")
        or "unknown"
    )
    domain: str = (
        dev.get("domain")
        or dev.get("workgroup")
        or ""
    )
    return hostname.strip(), domain.strip()


def _extract_os_info(payload: IngestPayload) -> tuple[str | None, str | None]:
    """Return (os_name, os_version) from the payload."""
    det  = payload.os_detail or {}
    legacy_os = (payload.os or {}).get("os") or {}
    os_name: str | None = (
        det.get("edition")
        or det.get("caption")
        or legacy_os.get("name")
    )
    os_version: str | None = (
        det.get("version")
        or legacy_os.get("release")
    )
    return os_name, os_version


def _extract_risk_score(raw: Any) -> int:
    if isinstance(raw, dict):
        return int(raw.get("score", 0))
    if isinstance(raw, (int, float)):
        return int(raw)
    return 0


@router.post(
    "/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest an agent report",
    description=(
        "Accepts a JSON report from an it-snapshot agent. "
        "Creates or updates the device row and appends a new report row. "
        "Requires the ``X-API-Key`` header."
    ),
)
async def ingest(
    payload: IngestPayload,
    _: None = Depends(require_api_key),
) -> IngestResponse:
    # ── Schema validation ─────────────────────────────────────────────────────
    if payload.schema_version not in _ACCEPTED_SCHEMA_VERSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Unsupported schema_version: '{payload.schema_version}'. "
                f"Accepted: {sorted(_ACCEPTED_SCHEMA_VERSIONS)}"
            ),
        )

    hostname, domain    = _extract_device_identity(payload)
    os_name, os_version = _extract_os_info(payload)
    risk_score          = _extract_risk_score(payload.risk_score)

    findings_json = json.dumps(payload.findings or [])
    raw_json      = json.dumps(payload.model_dump(mode="json"))

    async with get_db() as db:
        # Upsert device — update mutable fields on every report from this host
        await db.execute(
            """
            INSERT INTO devices (hostname, domain, last_seen, os_name, os_version, risk_score)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (hostname, domain) DO UPDATE SET
                last_seen  = excluded.last_seen,
                os_name    = excluded.os_name,
                os_version = excluded.os_version,
                risk_score = excluded.risk_score
            """,
            (hostname, domain, payload.collected_at, os_name, os_version, risk_score),
        )

        cur = await db.execute(
            "SELECT id FROM devices WHERE hostname = ? AND domain = ?",
            (hostname, domain),
        )
        row = await cur.fetchone()
        device_id: int = row["id"]

        # Append report (history is kept indefinitely)
        cur = await db.execute(
            """
            INSERT INTO reports (device_id, collected_at, risk_score, findings_json, raw_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (device_id, payload.collected_at, risk_score, findings_json, raw_json),
        )
        report_id: int = cur.lastrowid  # type: ignore[assignment]

        await db.commit()

    return IngestResponse(
        ok=True,
        device_id=device_id,
        report_id=report_id,
        hostname=hostname,
    )
