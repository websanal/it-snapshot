"""Device and report query endpoints."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..auth import require_api_key
from ..db import get_db
from ..models import DeviceSummary, ReportDetail, ReportSummary

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get(
    "",
    response_model=list[DeviceSummary],
    summary="List all known devices",
    description="Returns every device that has ever sent a report, ordered by most-recently seen.",
)
async def list_devices(
    _: None = Depends(require_api_key),
) -> list[dict[str, Any]]:
    async with get_db() as db:
        cur = await db.execute(
            "SELECT id, hostname, domain, last_seen, os_name, os_version, risk_score "
            "FROM devices ORDER BY last_seen DESC"
        )
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.get(
    "/{device_id}/latest",
    response_model=ReportDetail,
    summary="Get the latest report for a device",
    description="Returns the most-recent report for the given device, including the full raw payload.",
)
async def get_latest_report(
    device_id: int,
    _: None = Depends(require_api_key),
) -> dict[str, Any]:
    async with get_db() as db:
        cur = await db.execute("SELECT id FROM devices WHERE id = ?", (device_id,))
        if not await cur.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Device {device_id} not found.",
            )

        cur = await db.execute(
            """
            SELECT id, device_id, collected_at, risk_score, findings_json, raw_json, ingested_at
            FROM reports
            WHERE device_id = ?
            ORDER BY collected_at DESC
            LIMIT 1
            """,
            (device_id,),
        )
        row = await cur.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No reports found for device {device_id}.",
        )

    r = dict(row)
    return {
        "id":           r["id"],
        "device_id":    r["device_id"],
        "collected_at": r["collected_at"],
        "risk_score":   r["risk_score"],
        "ingested_at":  r["ingested_at"],
        "findings":     json.loads(r["findings_json"] or "[]"),
        "raw":          json.loads(r["raw_json"]),
    }


@router.get(
    "/{device_id}/reports",
    response_model=list[ReportSummary],
    summary="List report history for a device",
    description=(
        "Returns report summaries for the given device in reverse-chronological order. "
        "Use ``GET /devices/{device_id}/latest`` to retrieve the full raw payload."
    ),
)
async def list_device_reports(
    device_id: int,
    limit: int = Query(default=50, ge=1, le=500, description="Maximum number of reports to return"),
    _: None = Depends(require_api_key),
) -> list[dict[str, Any]]:
    async with get_db() as db:
        cur = await db.execute("SELECT id FROM devices WHERE id = ?", (device_id,))
        if not await cur.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Device {device_id} not found.",
            )

        cur = await db.execute(
            """
            SELECT id, device_id, collected_at, risk_score, ingested_at
            FROM reports
            WHERE device_id = ?
            ORDER BY collected_at DESC
            LIMIT ?
            """,
            (device_id, limit),
        )
        rows = await cur.fetchall()

    return [dict(r) for r in rows]
