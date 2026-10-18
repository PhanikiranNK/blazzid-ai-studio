"""Pydantic request and response schemas for BLAZZID HTTP REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from blazzid_jobs.states import JobStage, JobState


class JobCreateRequest(BaseModel):
    """Parameters for submitting a new video processing job."""

    model_config = ConfigDict(extra="forbid")

    target_duration_sec: float = Field(
        default=30.0,
        ge=5.0,
        le=300.0,
        description="Target duration in seconds for the output montage",
    )
    assembly_profile: str = Field(
        default="youtube_shorts",
        description="Target assembly profile (e.g. youtube_shorts, landscape_16_9, dynamic)",
    )
    max_clips: Optional[int] = Field(
        default=None,
        ge=1,
        le=20,
        description="Optional maximum number of clips to select and assemble",
    )
    aspect_ratio: str = Field(
        default="9:16",
        description="Desired output aspect ratio (e.g. 9:16, 16:9)",
    )
    storage_ref: Optional[str] = Field(
        default=None,
        description="Pre-existing storage artifact path or reference if not uploading via multipart",
    )


class JobResponse(BaseModel):
    """Full representation of a video processing job."""

    model_config = ConfigDict(from_attributes=True)

    job_id: str
    owner_id: str
    state: JobState
    stage: JobStage
    progress_percent: float
    source_filename: str
    target_duration_sec: float
    assembly_profile: str
    aspect_ratio: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    status_url: str
    result_url: Optional[str] = None


class JobListResponse(BaseModel):
    """Paginated list of jobs."""

    items: list[JobResponse]
    total: int
    limit: int
    offset: int


class JobCancelResponse(BaseModel):
    """Response returned upon job cancellation request."""

    job_id: str
    state: JobState
    message: str
    cancelled_at: Optional[datetime] = None


class JobResultResponse(BaseModel):
    """Result manifest and output artifacts for a successfully completed job."""

    job_id: str
    state: JobState
    completed_at: Optional[datetime] = None
    manifest: Optional[dict[str, Any]] = None
    artifacts: list[dict[str, Any]] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Service health response."""

    status: str
    database_ready: bool
    redis_ready: bool
    timestamp: datetime
