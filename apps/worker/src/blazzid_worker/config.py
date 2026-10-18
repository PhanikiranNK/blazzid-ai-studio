"""Configuration settings for the BLAZZID media processing worker."""

from __future__ import annotations

import os
import socket
import uuid
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class WorkerSettings(BaseModel):
    """Runtime configuration for background media worker."""

    worker_id: str = Field(
        default_factory=lambda: os.getenv(
            "WORKER_ID",
            f"worker-{socket.gethostname().split('.')[0]}-{uuid.uuid4().hex[:6]}",
        )
    )
    database_url: str = Field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./blazzid_dev.db")
    )
    redis_url: str = Field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )
    storage_root: Path = Field(
        default_factory=lambda: Path(os.getenv("STORAGE_ROOT", "./data/storage"))
    )
    lease_seconds: int = Field(
        default_factory=lambda: int(os.getenv("WORKER_LEASE_SECONDS", "300"))
    )
    lease_heartbeat_interval_sec: float = Field(
        default_factory=lambda: float(os.getenv("WORKER_HEARTBEAT_INTERVAL_SEC", "30.0"))
    )
    max_job_execution_seconds: float = Field(default=600.0)
    subprocess_timeout_seconds: float = Field(default=300.0)
    max_retries: int = Field(default_factory=lambda: int(os.getenv("WORKER_MAX_RETRIES", "3")))
    recovery_poll_interval_sec: float = Field(
        default_factory=lambda: float(os.getenv("WORKER_RECOVERY_POLL_INTERVAL_SEC", "60.0"))
    )


_worker_settings: Optional[WorkerSettings] = None


def get_worker_settings() -> WorkerSettings:
    """Retrieve singleton worker configuration."""
    global _worker_settings
    if _worker_settings is None:
        _worker_settings = WorkerSettings()
    return _worker_settings
