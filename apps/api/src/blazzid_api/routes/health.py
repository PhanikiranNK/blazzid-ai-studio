"""Liveness and readiness health probe endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

import redis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Engine

from blazzid_api.config import ApiSettings, get_api_settings
from blazzid_api.dependencies import get_engine
from blazzid_jobs.database import check_db_ready

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("/live", summary="Liveness probe")
def liveness() -> dict[str, str]:
    """Report process liveness."""
    return {"status": "alive"}


@router.get("/ready", summary="Readiness probe")
def readiness(
    engine: Engine = Depends(get_engine),
    settings: ApiSettings = Depends(get_api_settings),
) -> dict[str, object]:
    """Verify database and external queue readiness."""
    db_ok = check_db_ready(engine)

    redis_ok = True
    if settings.redis_url.startswith("redis://"):
        try:
            r = redis.Redis.from_url(settings.redis_url, socket_timeout=1.0)
            redis_ok = bool(r.ping())
        except Exception:
            redis_ok = False

    if not db_ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unavailable",
                "database_ready": False,
                "redis_ready": redis_ok,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    return {
        "status": "ready",
        "database_ready": db_ok,
        "redis_ready": redis_ok,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
