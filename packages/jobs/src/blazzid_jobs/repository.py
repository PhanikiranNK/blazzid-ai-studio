"""Job persistence repository with concurrency control and transactional outbox."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from blazzid_jobs.errors import (
    IdempotencyConflictError,
    InvalidStateTransitionError,
    JobNotFoundError,
    WorkerLeaseLostError,
)
from blazzid_jobs.models import JobAttemptRecord, JobRecord, OutboxRecord
from blazzid_jobs.states import (
    STAGE_PROGRESS_MAP,
    JobStage,
    JobState,
    assert_valid_transition,
)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class JobRepository:
    """Repository handling durable CRUD, optimistic concurrency, and transactional outbox."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def create_job(
        self,
        job_id: str,
        source_filename: str,
        source_storage_path: str,
        target_duration_sec: float,
        assembly_profile: str = "youtube_shorts",
        max_clips: Optional[int] = None,
        aspect_ratio: str = "9:16",
        owner_id: str = "anonymous",
        idempotency_key: Optional[str] = None,
        max_retries: int = 3,
    ) -> JobRecord:
        """Atomically create a job record and enqueue an outbox event."""
        with self.session_factory() as session, session.begin():
            # Check idempotency key if provided
            if idempotency_key is not None:
                stmt = select(JobRecord).where(
                    JobRecord.owner_id == owner_id,
                    JobRecord.idempotency_key == idempotency_key,
                )
                existing = session.execute(stmt).scalar_one_or_none()
                if existing is not None:
                    # Verify parameters match
                    matches = (
                        existing.owner_id == owner_id
                        and existing.source_filename == source_filename
                        and abs(existing.target_duration_sec - target_duration_sec) < 1e-4
                        and existing.assembly_profile == assembly_profile
                        and existing.aspect_ratio == aspect_ratio
                    )
                    if not matches:
                        raise IdempotencyConflictError(
                            f"Idempotency key {idempotency_key!r} conflict with differing job parameters"
                        )
                    return existing

            now = datetime.now(timezone.utc)
            job = JobRecord(
                job_id=job_id,
                owner_id=owner_id,
                idempotency_key=idempotency_key,
                state=JobState.QUEUED.value,
                stage=JobStage.VALIDATING_INPUT.value,
                progress_percent=0.0,
                source_filename=source_filename,
                source_storage_path=source_storage_path,
                target_duration_sec=target_duration_sec,
                assembly_profile=assembly_profile,
                max_clips=max_clips,
                aspect_ratio=aspect_ratio,
                max_retries=max_retries,
                retry_count=0,
                created_at=now,
                updated_at=now,
                version=1,
            )
            session.add(job)

            event_id = f"evt-{uuid.uuid4().hex[:12]}"
            outbox_event = OutboxRecord(
                event_id=event_id,
                job_id=job_id,
                event_type="job.queued",
                payload={
                    "event_id": event_id,
                    "job_id": job_id,
                    "event_type": "job.queued",
                    "timestamp": now.isoformat(),
                },
                created_at=now,
            )
            session.add(outbox_event)
            session.flush()
            session.expunge(job)
            return job

    def get_by_id(self, job_id: str) -> Optional[JobRecord]:
        """Fetch job by ID."""
        with self.session_factory() as session:
            stmt = select(JobRecord).where(JobRecord.job_id == job_id)
            job = session.execute(stmt).scalar_one_or_none()
            if job is not None:
                session.expunge(job)
            return job

    def get_by_idempotency_key(
        self, idempotency_key: str, owner_id: Optional[str] = None
    ) -> Optional[JobRecord]:
        """Fetch job by idempotency key and optional owner."""
        with self.session_factory() as session:
            stmt = select(JobRecord).where(JobRecord.idempotency_key == idempotency_key)
            if owner_id is not None:
                stmt = stmt.where(JobRecord.owner_id == owner_id)
            job = session.execute(stmt).scalar_one_or_none()
            if job is not None:
                session.expunge(job)
            return job

    def list_jobs(
        self,
        owner_id: Optional[str] = None,
        state: Optional[JobState] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[JobRecord], int]:
        """List jobs with pagination and optional filtering."""
        with self.session_factory() as session:
            query = select(JobRecord)
            count_query = select(func.count(JobRecord.job_id))

            if owner_id is not None:
                query = query.where(JobRecord.owner_id == owner_id)
                count_query = count_query.where(JobRecord.owner_id == owner_id)

            if state is not None:
                query = query.where(JobRecord.state == state.value)
                count_query = count_query.where(JobRecord.state == state.value)

            total = session.execute(count_query).scalar_one()
            query = query.order_by(JobRecord.created_at.desc()).offset(offset).limit(limit)
            jobs = list(session.execute(query).scalars().all())
            for j in jobs:
                session.expunge(j)
            return jobs, total

    def claim_job(self, job_id: str, worker_id: str, lease_seconds: int = 300) -> bool:
        """Atomically claim a queued or expired job for execution by worker."""
        with self.session_factory() as session, session.begin():
            job = session.get(JobRecord, job_id, with_for_update=True)
            if job is None:
                return False

            current_state = JobState(job.state)
            now = datetime.now(timezone.utc)

            is_queued = current_state == JobState.QUEUED
            lease_until = _as_utc(job.worker_lease_until)
            is_expired = (
                current_state == JobState.PROCESSING
                and lease_until is not None
                and lease_until < now
            )

            if not (is_queued or is_expired):
                return False

            assert_valid_transition(current_state, JobState.PROCESSING)

            job.state = JobState.PROCESSING.value
            job.worker_id = worker_id
            job.worker_lease_until = now + timedelta(seconds=lease_seconds)
            job.started_at = job.started_at or now
            job.updated_at = now
            job.version += 1

            # Record attempt
            attempt_num = (
                session.execute(
                    select(func.coalesce(func.max(JobAttemptRecord.attempt_number), 0)).where(
                        JobAttemptRecord.job_id == job_id
                    )
                ).scalar_one()
                + 1
            )

            attempt = JobAttemptRecord(
                job_id=job_id,
                attempt_number=attempt_num,
                worker_id=worker_id,
                state=JobState.PROCESSING.value,
                stage=job.stage,
                started_at=now,
            )
            session.add(attempt)
            return True

    def extend_lease(self, job_id: str, worker_id: str, lease_seconds: int = 300) -> bool:
        """Heartbeat to extend worker lease for an ongoing processing job."""
        with self.session_factory() as session, session.begin():
            job = session.get(JobRecord, job_id, with_for_update=True)
            if job is None or job.worker_id != worker_id or job.state != JobState.PROCESSING.value:
                return False
            now = datetime.now(timezone.utc)
            job.worker_lease_until = now + timedelta(seconds=lease_seconds)
            job.updated_at = now
            return True

    def update_progress(
        self,
        job_id: str,
        worker_id: str,
        stage: JobStage,
        progress_percent: Optional[float] = None,
    ) -> None:
        """Update processing stage and monotonic progress percentage."""
        with self.session_factory() as session, session.begin():
            job = session.get(JobRecord, job_id, with_for_update=True)
            if job is None:
                raise JobNotFoundError(f"Job not found: {job_id}")

            if job.worker_id != worker_id or job.state != JobState.PROCESSING.value:
                raise WorkerLeaseLostError(
                    f"Worker {worker_id} does not own active lease for job {job_id} (current worker: {job.worker_id}, state: {job.state})"
                )

            now = datetime.now(timezone.utc)
            lease_until = _as_utc(job.worker_lease_until)
            if lease_until is not None and lease_until < now:
                raise WorkerLeaseLostError(
                    f"Worker {worker_id} lease for job {job_id} expired at {lease_until.isoformat()}"
                )

            # Determine progress
            calculated_pct = (
                progress_percent
                if progress_percent is not None
                else STAGE_PROGRESS_MAP.get(stage, job.progress_percent)
            )
            # Monotonic nondecreasing guarantee within 0.0 - 100.0
            safe_pct = min(100.0, max(job.progress_percent, calculated_pct))

            now = datetime.now(timezone.utc)
            job.stage = stage.value
            job.progress_percent = safe_pct
            job.updated_at = now

    def check_cancellation(self, job_id: str) -> bool:
        """Check if job has received a cancellation request or is cancelled."""
        with self.session_factory() as session:
            stmt = select(JobRecord.state).where(JobRecord.job_id == job_id)
            state = session.execute(stmt).scalar_one_or_none()
            if state is None:
                return False
            return state in (JobState.CANCEL_REQUESTED.value, JobState.CANCELLED.value)

    def request_cancellation(self, job_id: str, reason: Optional[str] = None) -> JobRecord:
        """Request job cancellation, immediately cancelling queued jobs or signaling processing jobs."""
        with self.session_factory() as session, session.begin():
            job = session.get(JobRecord, job_id, with_for_update=True)
            if job is None:
                raise JobNotFoundError(f"Job not found: {job_id}")

            current_state = JobState(job.state)
            now = datetime.now(timezone.utc)

            if current_state == JobState.QUEUED:
                job.state = JobState.CANCELLED.value
                job.cancelled_at = now
                job.updated_at = now
                job.version += 1
            elif current_state == JobState.PROCESSING:
                job.state = JobState.CANCEL_REQUESTED.value
                job.cancelled_at = now
                job.updated_at = now
                job.version += 1

                # Outbox event for worker notification
                event_id = f"evt-{uuid.uuid4().hex[:12]}"
                session.add(
                    OutboxRecord(
                        event_id=event_id,
                        job_id=job_id,
                        event_type="job.cancel_requested",
                        payload={
                            "event_id": event_id,
                            "job_id": job_id,
                            "reason": reason,
                            "timestamp": now.isoformat(),
                        },
                        created_at=now,
                    )
                )
            elif current_state in (JobState.CANCEL_REQUESTED, JobState.CANCELLED):
                # Idempotent
                pass
            else:
                raise InvalidStateTransitionError(
                    f"Cannot cancel job {job_id} in terminal state {current_state.value}"
                )

            session.flush()
            session.expunge(job)
            return job

    def mark_cancelled(self, job_id: str, worker_id: str) -> None:
        """Mark a job as CANCELLED by the worker after process cleanup."""
        with self.session_factory() as session, session.begin():
            job = session.get(JobRecord, job_id, with_for_update=True)
            if job is None:
                return
            if job.worker_id != worker_id and job.worker_id is not None:
                return
            now = datetime.now(timezone.utc)
            job.state = JobState.CANCELLED.value
            job.cancelled_at = job.cancelled_at or now
            job.updated_at = now
            job.worker_id = None
            job.worker_lease_until = None
            job.version += 1

            # Update latest attempt
            attempt = session.execute(
                select(JobAttemptRecord)
                .where(JobAttemptRecord.job_id == job_id)
                .order_by(JobAttemptRecord.attempt_number.desc())
                .limit(1)
            ).scalar_one_or_none()
            if attempt is not None:
                attempt.state = JobState.CANCELLED.value
                attempt.finished_at = now

    def mark_succeeded(
        self,
        job_id: str,
        worker_id: str,
        result_manifest: dict[str, Any],
    ) -> None:
        """Mark job as SUCCEEDED, saving verified result manifest and 100% progress."""
        with self.session_factory() as session, session.begin():
            job = session.get(JobRecord, job_id, with_for_update=True)
            if job is None:
                raise JobNotFoundError(f"Job not found: {job_id}")

            if job.worker_id != worker_id:
                raise WorkerLeaseLostError(
                    f"Worker {worker_id} does not own lease for job {job_id} (current worker: {job.worker_id})"
                )

            now = datetime.now(timezone.utc)

            # If cancellation was requested before finalizing, mark cancelled
            if job.state == JobState.CANCEL_REQUESTED.value:
                job.state = JobState.CANCELLED.value
                job.cancelled_at = job.cancelled_at or now
                job.updated_at = now
                job.worker_id = None
                job.worker_lease_until = None
                job.version += 1
                return

            if job.state != JobState.PROCESSING.value:
                raise WorkerLeaseLostError(f"Job {job_id} is in state {job.state}, not PROCESSING")

            lease_until = _as_utc(job.worker_lease_until)
            if lease_until is not None and lease_until < now:
                raise WorkerLeaseLostError(
                    f"Worker {worker_id} lease for job {job_id} expired at {lease_until.isoformat()}"
                )

            assert_valid_transition(JobState(job.state), JobState.SUCCEEDED)

            job.state = JobState.SUCCEEDED.value
            job.stage = JobStage.FINALIZING.value
            job.progress_percent = 100.0
            job.result_manifest = result_manifest
            job.completed_at = now
            job.updated_at = now
            job.worker_id = None
            job.worker_lease_until = None
            job.version += 1

            # Update attempt
            attempt = session.execute(
                select(JobAttemptRecord)
                .where(JobAttemptRecord.job_id == job_id)
                .order_by(JobAttemptRecord.attempt_number.desc())
                .limit(1)
            ).scalar_one_or_none()
            if attempt is not None:
                attempt.state = JobState.SUCCEEDED.value
                attempt.stage = JobStage.FINALIZING.value
                attempt.finished_at = now

    def mark_failed(
        self,
        job_id: str,
        worker_id: str,
        error_code: str,
        error_message: str,
        retryable: bool,
    ) -> JobRecord:
        """Record job failure, triggering retry to QUEUED or final FAILED state."""
        with self.session_factory() as session, session.begin():
            job = session.get(JobRecord, job_id, with_for_update=True)
            if job is None:
                raise JobNotFoundError(f"Job not found: {job_id}")

            if job.worker_id != worker_id:
                raise WorkerLeaseLostError(
                    f"Worker {worker_id} does not own lease for job {job_id} (current worker: {job.worker_id})"
                )

            now = datetime.now(timezone.utc)

            # If cancellation was requested, transition to CANCELLED instead of FAILED
            if job.state == JobState.CANCEL_REQUESTED.value:
                job.state = JobState.CANCELLED.value
                job.cancelled_at = job.cancelled_at or now
                job.updated_at = now
                job.worker_id = None
                job.worker_lease_until = None
                job.version += 1
                session.flush()
                session.expunge(job)
                return job

            should_retry = retryable and (job.retry_count < job.max_retries)

            # Update current attempt
            attempt = session.execute(
                select(JobAttemptRecord)
                .where(JobAttemptRecord.job_id == job_id)
                .order_by(JobAttemptRecord.attempt_number.desc())
                .limit(1)
            ).scalar_one_or_none()
            if attempt is not None:
                attempt.state = JobState.FAILED.value
                attempt.error_code = error_code
                attempt.error_message = error_message[:1024]
                attempt.finished_at = now

            if should_retry:
                job.retry_count += 1
                job.state = JobState.QUEUED.value
                job.stage = JobStage.VALIDATING_INPUT.value
                job.progress_percent = 0.0
                job.error_code = error_code
                job.error_message = f"[Attempt {job.retry_count} failed] {error_message[:900]}"
                job.worker_id = None
                job.worker_lease_until = None
                job.updated_at = now
                job.version += 1

                # Re-enqueue in outbox
                event_id = f"evt-{uuid.uuid4().hex[:12]}"
                session.add(
                    OutboxRecord(
                        event_id=event_id,
                        job_id=job_id,
                        event_type="job.queued",
                        payload={
                            "event_id": event_id,
                            "job_id": job_id,
                            "event_type": "job.queued",
                            "timestamp": now.isoformat(),
                            "retry_attempt": job.retry_count,
                        },
                        created_at=now,
                    )
                )
            else:
                job.state = JobState.FAILED.value
                job.error_code = error_code
                job.error_message = error_message[:1024]
                job.completed_at = now
                job.updated_at = now
                job.worker_id = None
                job.worker_lease_until = None
                job.version += 1

            session.flush()
            session.expunge(job)
            return job

    def get_pending_outbox_events(self, limit: int = 50) -> list[OutboxRecord]:
        """Fetch unpublished outbox events ordered chronologically."""
        with self.session_factory() as session:
            stmt = (
                select(OutboxRecord)
                .where(OutboxRecord.published_at.is_(None))
                .order_by(OutboxRecord.created_at.asc())
                .limit(limit)
            )
            records = list(session.execute(stmt).scalars().all())
            for r in records:
                session.expunge(r)
            return records

    def mark_outbox_published(self, event_id: str) -> None:
        """Mark an outbox event as successfully delivered to the queue."""
        with self.session_factory() as session, session.begin():
            now = datetime.now(timezone.utc)
            stmt = (
                update(OutboxRecord)
                .where(OutboxRecord.event_id == event_id)
                .values(published_at=now)
            )
            session.execute(stmt)

    def recover_abandoned_jobs(self, lease_expired_before: datetime) -> list[str]:
        """Find processing jobs whose leases expired, incrementing retry or failing them."""
        recovered_job_ids: list[str] = []
        with self.session_factory() as session, session.begin():
            stmt = (
                select(JobRecord)
                .where(
                    JobRecord.state.in_(
                        [JobState.PROCESSING.value, JobState.CANCEL_REQUESTED.value]
                    )
                )
                .with_for_update()
            )
            candidates = list(session.execute(stmt).scalars().all())
            now = datetime.now(timezone.utc)
            cutoff = _as_utc(lease_expired_before) or now

            for job in candidates:
                lease_until = _as_utc(job.worker_lease_until)
                if lease_until is None or lease_until >= cutoff:
                    continue
                recovered_job_ids.append(job.job_id)

                if job.state == JobState.CANCEL_REQUESTED.value:
                    # Finalize abandoned cancellation request
                    job.state = JobState.CANCELLED.value
                    job.cancelled_at = job.cancelled_at or now
                    job.updated_at = now
                    job.worker_id = None
                    job.worker_lease_until = None
                    job.version += 1
                    continue

                if job.retry_count < job.max_retries:
                    job.retry_count += 1
                    job.state = JobState.QUEUED.value
                    job.stage = JobStage.VALIDATING_INPUT.value
                    job.progress_percent = 0.0
                    job.error_code = "WORKER_LEASE_EXPIRED"
                    job.error_message = (
                        f"Worker lease expired; re-queued for attempt {job.retry_count + 1}"
                    )
                    job.worker_id = None
                    job.worker_lease_until = None
                    job.updated_at = now
                    job.version += 1

                    event_id = f"evt-{uuid.uuid4().hex[:12]}"
                    session.add(
                        OutboxRecord(
                            event_id=event_id,
                            job_id=job.job_id,
                            event_type="job.queued",
                            payload={
                                "event_id": event_id,
                                "job_id": job.job_id,
                                "event_type": "job.queued",
                                "timestamp": now.isoformat(),
                                "retry_attempt": job.retry_count,
                            },
                            created_at=now,
                        )
                    )
                else:
                    job.state = JobState.FAILED.value
                    job.error_code = "MAX_RETRIES_EXCEEDED"
                    job.error_message = "Worker lease expired and retry limit reached."
                    job.completed_at = now
                    job.updated_at = now
                    job.worker_id = None
                    job.worker_lease_until = None
                    job.version += 1

        return recovered_job_ids
