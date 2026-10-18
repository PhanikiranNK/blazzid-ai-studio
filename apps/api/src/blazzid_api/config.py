"""Configuration settings for the BLAZZID Studio HTTP API service."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class ApiSettings(BaseModel):
    """Runtime configuration for BLAZZID API service."""

    database_url: str = Field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./blazzid_dev.db")
    )
    redis_url: str = Field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )
    storage_root: Path = Field(
        default_factory=lambda: Path(os.getenv("STORAGE_ROOT", "./data/storage"))
    )
    max_upload_size_bytes: int = Field(
        default_factory=lambda: int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(500 * 1024 * 1024)))
    )
    allowed_media_types: list[str] = Field(
        default=[
            "video/mp4",
            "video/quicktime",
            "video/x-matroska",
            "video/webm",
            "application/octet-stream",
        ]
    )
    default_assembly_profile: str = "youtube_shorts"
    max_job_duration_sec: float = 300.0
    min_job_duration_sec: float = 5.0
    auth_secret_token: Optional[str] = Field(
        default_factory=lambda: os.getenv("BLAZZID_AUTH_SECRET", None)
    )
    environment: str = Field(
        default_factory=lambda: os.getenv("BLAZZID_ENV", "development").lower()
    )
    allow_anonymous_dev: bool = Field(
        default_factory=lambda: (
            os.getenv("BLAZZID_ALLOW_ANONYMOUS_DEV", "false").lower() in ("true", "1", "yes")
        )
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()
        ]
    )


_settings: Optional[ApiSettings] = None


def get_api_settings() -> ApiSettings:
    """Retrieve singleton configuration instance."""
    global _settings
    if _settings is None:
        _settings = ApiSettings()
    return _settings
