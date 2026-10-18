"""Event schemas for outbox publishing and worker consumption."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class JobEvent(BaseModel):
    """Base event payload model."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(default_factory=lambda: f"evt-{uuid.uuid4().hex[:12]}")
    job_id: str
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobQueuedEvent(JobEvent):
    """Event emitted when a job is created and queued for processing."""

    event_type: str = "job.queued"


class JobCancelRequestedEvent(JobEvent):
    """Event emitted when a job cancellation is requested."""

    event_type: str = "job.cancel_requested"
    reason: Optional[str] = None
