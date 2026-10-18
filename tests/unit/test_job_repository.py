"""Unit tests for JobRepository persistence, concurrency, and outbox."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from blazzid_jobs.database import create_session_factory, init_db
from blazzid_jobs.errors import (
    IdempotencyConflictError,
)
from blazzid_jobs.queue import InMemoryJobQueue, OutboxDispatcher
from blazzid_jobs.repository import JobRepository
from blazzid_jobs.states import JobStage, JobState


@pytest.fixture
def repo(tmp_path: Path) -> JobRepository:
    db_file = tmp_path / "test_repo.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    init_db(engine)
    session_factory = create_session_factory(engine)
    return JobRepository(session_factory=session_factory)


def test_create_job_and_outbox_atomicity(repo: JobRepository) -> None:
    job = repo.create_job(
        job_id="job-atom-1",
        source_filename="input.mp4",
        source_storage_path="jobs/job-atom-1/source/input.mp4",
        target_duration_sec=30.0,
        assembly_profile="youtube_shorts",
        idempotency_key="key-12345",
    )

    assert job.job_id == "job-atom-1"
    assert job.state == JobState.QUEUED.value
    assert job.progress_percent == 0.0

    # Verify pending outbox record was created
    pending = repo.get_pending_outbox_events()
    assert len(pending) == 1
    assert pending[0].job_id == "job-atom-1"
    assert pending[0].event_type == "job.queued"


def test_idempotency_key_behavior(repo: JobRepository) -> None:
    # First creation
    job1 = repo.create_job(
        job_id="job-idemp-1",
        source_filename="video.mp4",
        source_storage_path="path/video.mp4",
        target_duration_sec=30.0,
        assembly_profile="youtube_shorts",
        idempotency_key="same-key",
    )

    # Identical replay returns existing job
    job2 = repo.create_job(
        job_id="different-job-id",
        source_filename="video.mp4",
        source_storage_path="path/video.mp4",
        target_duration_sec=30.0,
        assembly_profile="youtube_shorts",
        idempotency_key="same-key",
    )
    assert job2.job_id == job1.job_id

    # Conflict with differing parameters
    with pytest.raises(IdempotencyConflictError):
        repo.create_job(
            job_id="job-mismatch",
            source_filename="video.mp4",
            source_storage_path="path/video.mp4",
            target_duration_sec=60.0,  # Different duration
            assembly_profile="youtube_shorts",
            idempotency_key="same-key",
        )


def test_claim_job_concurrency_and_lease(repo: JobRepository) -> None:
    job_id = "job-claim-1"
    repo.create_job(
        job_id=job_id,
        source_filename="input.mp4",
        source_storage_path="path/input.mp4",
        target_duration_sec=30.0,
    )

    # Worker 1 claims
    claimed_w1 = repo.claim_job(job_id=job_id, worker_id="worker-1", lease_seconds=100)
    assert claimed_w1 is True

    # Worker 2 attempts to claim active job -> fails
    claimed_w2 = repo.claim_job(job_id=job_id, worker_id="worker-2", lease_seconds=100)
    assert claimed_w2 is False

    # Check updated state in persistence
    updated = repo.get_by_id(job_id)
    assert updated is not None
    assert updated.state == JobState.PROCESSING.value
    assert updated.worker_id == "worker-1"
    assert updated.worker_lease_until is not None


def test_progress_monotonicity(repo: JobRepository) -> None:
    job_id = "job-prog-1"
    repo.create_job(
        job_id=job_id,
        source_filename="input.mp4",
        source_storage_path="path/input.mp4",
        target_duration_sec=30.0,
    )
    repo.claim_job(job_id=job_id, worker_id="worker-1")

    # Update to 25%
    repo.update_progress(job_id, "worker-1", JobStage.PREPROCESSING, progress_percent=25.0)
    j = repo.get_by_id(job_id)
    assert j is not None
    assert j.stage == JobStage.PREPROCESSING.value
    assert j.progress_percent == 25.0

    # Attempt to decrease to 10% -> ignored, stays at 25%
    repo.update_progress(job_id, "worker-1", JobStage.PROBING_MEDIA, progress_percent=10.0)
    j = repo.get_by_id(job_id)
    assert j is not None
    assert j.progress_percent == 25.0


def test_request_cancellation(repo: JobRepository) -> None:
    # 1. Cancel queued job
    q_job_id = "job-cancel-q"
    repo.create_job(
        job_id=q_job_id,
        source_filename="in.mp4",
        source_storage_path="path/in.mp4",
        target_duration_sec=15.0,
    )
    cancelled = repo.request_cancellation(q_job_id)
    assert cancelled.state == JobState.CANCELLED.value

    # 2. Cancel processing job
    p_job_id = "job-cancel-p"
    repo.create_job(
        job_id=p_job_id,
        source_filename="in.mp4",
        source_storage_path="path/in.mp4",
        target_duration_sec=15.0,
    )
    repo.claim_job(p_job_id, worker_id="worker-1")
    req = repo.request_cancellation(p_job_id)
    assert req.state == JobState.CANCEL_REQUESTED.value
    assert repo.check_cancellation(p_job_id) is True


def test_outbox_dispatcher(repo: JobRepository) -> None:
    queue = InMemoryJobQueue()
    dispatcher = OutboxDispatcher(repository=repo, queue=queue)

    repo.create_job(
        job_id="job-disp-1",
        source_filename="v.mp4",
        source_storage_path="p.mp4",
        target_duration_sec=30.0,
    )

    dispatched = dispatcher.dispatch_pending()
    assert dispatched == 1

    # Queue should now have 1 message
    msg = queue.consume()
    assert msg is not None
    assert msg.job_id == "job-disp-1"
    assert msg.event_type == "job.queued"

    # Outbox should have 0 pending
    assert len(repo.get_pending_outbox_events()) == 0


def test_abandoned_job_recovery(repo: JobRepository) -> None:
    job_id = "job-abandoned-1"
    repo.create_job(
        job_id=job_id,
        source_filename="v.mp4",
        source_storage_path="p.mp4",
        target_duration_sec=30.0,
        max_retries=2,
    )
    repo.claim_job(job_id, worker_id="worker-dead", lease_seconds=10)

    # Simulate time passing beyond lease expiry
    expired_time = datetime.now(timezone.utc) + timedelta(seconds=60)
    recovered = repo.recover_abandoned_jobs(lease_expired_before=expired_time)
    assert job_id in recovered

    # Verify job is back in QUEUED state with retry count 1
    job = repo.get_by_id(job_id)
    assert job is not None
    assert job.state == JobState.QUEUED.value
    assert job.retry_count == 1
