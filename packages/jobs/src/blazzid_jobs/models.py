"""SQLAlchemy 2.0 ORM models for job orchestration, attempts, and outbox."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from blazzid_jobs.states import JobStage, JobState


class Base(DeclarativeBase):
    """Base class for all ORM models."""


# Portable JSON type: JSONB on Postgres, standard JSON on SQLite
JSONType = JSON().with_variant(JSONB, "postgresql")


class JobRecord(Base):
    """Persistent database record representing a video processing job."""

    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(128), default="anonymous", index=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, index=True)
    state: Mapped[str] = mapped_column(
        String(32), default=JobState.QUEUED.value, index=True, nullable=False
    )
    stage: Mapped[str] = mapped_column(
        String(32), default=JobStage.VALIDATING_INPUT.value, nullable=False
    )
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    source_filename: Mapped[str] = mapped_column(String(256), nullable=False)
    source_storage_path: Mapped[str] = mapped_column(String(512), nullable=False)

    target_duration_sec: Mapped[float] = mapped_column(Float, nullable=False)
    assembly_profile: Mapped[str] = mapped_column(String(64), default="youtube_shorts")
    max_clips: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    aspect_ratio: Mapped[str] = mapped_column(String(16), default="9:16")

    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    worker_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    worker_lease_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    result_manifest: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONType, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    attempts: Mapped[list[JobAttemptRecord]] = relationship(
        "JobAttemptRecord",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="JobAttemptRecord.attempt_number",
    )

    __table_args__ = (
        Index("ix_jobs_owner_idempotency_key", "owner_id", "idempotency_key", unique=True),
        Index("ix_jobs_owner_state", "owner_id", "state"),
        Index("ix_jobs_created_state", "created_at", "state"),
    )


class JobAttemptRecord(Base):
    """Audit log of individual execution attempts for a job."""

    __tablename__ = "job_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("jobs.job_id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    error_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    job: Mapped[JobRecord] = relationship("JobRecord", back_populates="attempts")


class OutboxRecord(Base):
    """Transactional outbox table ensuring reliable event publication."""

    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    __table_args__ = (Index("ix_outbox_pending", "published_at", "created_at"),)
