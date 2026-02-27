"""API-key authentication dependency for the inventory server.

The key is read once from the IT_SNAPSHOT_API_KEY environment variable.
Agents must send it in the ``X-API-Key`` request header.
"""

from __future__ import annotations

import os

from fastapi import Header, HTTPException, status

# Loaded at import time so a missing env var is immediately obvious on startup.
_API_KEY: str = os.environ.get("IT_SNAPSHOT_API_KEY", "")


async def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> None:
    """FastAPI dependency: validate the X-API-Key header.

    Raises:
        503 if the server has no API key configured.
        401 if the provided key does not match.
    """
    if not _API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The server API key is not configured. "
                "Set the IT_SNAPSHOT_API_KEY environment variable."
            ),
        )
    if x_api_key != _API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
