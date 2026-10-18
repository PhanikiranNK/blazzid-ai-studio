"""Integration tests for background media worker orchestration and full pipeline lifecycle."""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from blazzid_jobs.database import create_db_engine, create_session_factory, init_db
from blazzid_jobs.queue import InMemoryJobQueue
from blazzid_jobs.repository import JobRepository
from blazzid_jobs.states import JobStage, JobState
from blazzid_storage.interfaces import ArtifactType
from blazzid_storage.local import LocalStorageBackend
from blazzid_worker.config import WorkerSettings
from blazzid_worker.consumer import WorkerConsumer
from tests.fixtures.synthetic_media import generate_synthetic_video, is_ffmpeg_available


@pytest.fixture
def test_env(tmp_path: Path) -> dict[str, Any]:
    db_file = tmp_path / "test_orchestration.db"
    engine = create_db_engine(f"sqlite:///{db_file}")
    init_db(engine)
    session_factory = create_session_factory(engine)
    repository = JobRepository(session_factory)

    storage = LocalStorageBackend(root_dir=tmp_path / "storage")
    queue = InMemoryJobQueue()

    settings = WorkerSettings(
        worker_id="test-worker-01",
        database_url=f"sqlite:///{db_file}",
        storage_root=tmp_path / "storage",
        lease_seconds=60,
    )

    consumer = WorkerConsumer(
        storage=storage,
        repository=repository,
        queue=queue,
        settings=settings,
    )

    return {
        "engine": engine,
        "repository": repository,
        "storage": storage,
        "queue": queue,
        "consumer": consumer,
        "settings": settings,
        "tmp_path": tmp_path,
    }


@pytest.mark.skipif(
    not is_ffmpeg_available(), reason="FFmpeg is required for end-to-end worker tests"
)
def test_worker_end_to_end_pipeline_success(test_env: dict[str, Any]) -> None:
    repository: JobRepository = test_env["repository"]
    storage: LocalStorageBackend = test_env["storage"]
    queue: InMemoryJobQueue = test_env["queue"]
    consumer: WorkerConsumer = test_env["consumer"]
    tmp_path: Path = test_env["tmp_path"]

    # 1. Generate small real synthetic video
    raw_video = generate_synthetic_video(
        duration_seconds=5.0,
        width=320,
        height=240,
        fps=15,
        output_path=tmp_path / "sample.mp4",
    )

    job_id = "job-e2e-001"
    with open(raw_video, "rb") as f:
        storage.store_stream(
            job_id=job_id,
            filename="sample.mp4",
            stream=f,
            max_bytes=50 * 1024 * 1024,
        )

    # 2. Create job in repository
    job = repository.create_job(
        job_id=job_id,
        source_filename="sample.mp4",
        source_storage_path=f"jobs/{job_id}/source/sample.mp4",
        target_duration_sec=10.0,
        assembly_profile="youtube_shorts",
    )
    assert job.state == JobState.QUEUED.value

    # 3. Publish message to queue
    queue.publish(job_id=job_id, event_type="job.queued", payload={"job_id": job_id})

    # 4. Consumer processes the message
    processed = consumer.run_once()
    assert processed is True

    # 5. Verify final job state and artifacts
    completed_job = repository.get_by_id(job_id)
    assert completed_job is not None
    assert completed_job.state == JobState.SUCCEEDED.value
    assert completed_job.stage == JobStage.FINALIZING.value
    assert completed_job.progress_percent == 100.0
    assert completed_job.result_manifest is not None
    assert completed_job.completed_at is not None

    # Check rendered montage artifact exists
    montage_path = storage.get_artifact_path(job_id, ArtifactType.RENDERED_MONTAGE)
    assert montage_path is not None
    assert montage_path.exists()
    assert montage_path.stat().st_size > 0

    # Check edit manifest artifact exists
    manifest_path = storage.get_artifact_path(job_id, ArtifactType.EDIT_MANIFEST_JSON)
    assert manifest_path is not None
    assert manifest_path.exists()

    # Verify scratch directory was cleaned up deterministically
    scratch_dir = storage.get_job_scratch_dir(job_id)
    assert not scratch_dir.exists()


def test_worker_corrupt_media_fails_permanently(test_env: dict[str, Any]) -> None:
    repository: JobRepository = test_env["repository"]
    storage: LocalStorageBackend = test_env["storage"]
    queue: InMemoryJobQueue = test_env["queue"]
    consumer: WorkerConsumer = test_env["consumer"]

    job_id = "job-corrupt-002"
    corrupt_stream = io.BytesIO(b"this is completely invalid non-video header garbage")
    storage.store_stream(
        job_id=job_id,
        filename="corrupt.mp4",
        stream=corrupt_stream,
        max_bytes=1024 * 1024,
    )

    repository.create_job(
        job_id=job_id,
        source_filename="corrupt.mp4",
        source_storage_path=f"jobs/{job_id}/source/corrupt.mp4",
        target_duration_sec=15.0,
    )

    queue.publish(job_id=job_id, event_type="job.queued", payload={"job_id": job_id})

    processed = consumer.run_once()
    assert processed is True

    failed_job = repository.get_by_id(job_id)
    assert failed_job is not None
    assert failed_job.state == JobState.FAILED.value
    assert failed_job.progress_percent < 100.0
    assert failed_job.error_code == "PERMANENT_ERROR"
    # Permanent failure should not trigger endless retries
    assert failed_job.retry_count == 0


def test_worker_duplicate_delivery_safe(test_env: dict[str, Any]) -> None:
    repository: JobRepository = test_env["repository"]
    storage: LocalStorageBackend = test_env["storage"]
    queue: InMemoryJobQueue = test_env["queue"]
    consumer: WorkerConsumer = test_env["consumer"]

    job_id = "job-dup-003"
    storage.store_stream(
        job_id=job_id,
        filename="v.mp4",
        stream=io.BytesIO(b"test"),
        max_bytes=1024,
    )

    repository.create_job(
        job_id=job_id,
        source_filename="v.mp4",
        source_storage_path=f"jobs/{job_id}/source/v.mp4",
        target_duration_sec=15.0,
    )

    # First delivery - claim it
    claimed = repository.claim_job(job_id, worker_id="worker-primary")
    assert claimed is True

    # Second delivery via queue
    queue.publish(job_id=job_id, event_type="job.queued", payload={"job_id": job_id})

    # Consumer tries to process duplicate message
    second_processed = consumer.run_once()
    # Cannot claim because already claimed, skips safely
    assert second_processed is False


def test_worker_cancellation_before_execution(test_env: dict[str, Any]) -> None:
    repository: JobRepository = test_env["repository"]
    storage: LocalStorageBackend = test_env["storage"]
    queue: InMemoryJobQueue = test_env["queue"]
    consumer: WorkerConsumer = test_env["consumer"]

    job_id = "job-cancel-004"
    storage.store_stream(
        job_id=job_id,
        filename="v.mp4",
        stream=io.BytesIO(b"test"),
        max_bytes=1024,
    )

    repository.create_job(
        job_id=job_id,
        source_filename="v.mp4",
        source_storage_path=f"jobs/{job_id}/source/v.mp4",
        target_duration_sec=15.0,
    )

    # Cancel while still queued
    repository.request_cancellation(job_id)

    queue.publish(job_id=job_id, event_type="job.queued", payload={"job_id": job_id})

    processed = consumer.run_once()
    # Cannot claim cancelled job
    assert processed is False

    job = repository.get_by_id(job_id)
    assert job is not None
    assert job.state == JobState.CANCELLED.value


def test_stale_worker_cannot_overwrite_newer_worker(test_env: dict[str, Any]) -> None:
    """Verify that a worker that lost its lease cannot update progress or mark completion."""
    repository: JobRepository = test_env["repository"]
    from blazzid_jobs.errors import WorkerLeaseLostError

    job_id = "job-stale-005"
    repository.create_job(
        job_id=job_id,
        source_filename="test.mp4",
        source_storage_path="path/test.mp4",
        target_duration_sec=30.0,
    )

    # Worker 1 claims job
    assert repository.claim_job(job_id, worker_id="worker-old", lease_seconds=1) is True

    # Expire Worker 1's lease
    with repository.session_factory() as session, session.begin():
        from blazzid_jobs.models import JobRecord

        j = session.get(JobRecord, job_id)
        assert j is not None
        j.worker_lease_until = datetime.now(timezone.utc) - timedelta(seconds=10)

    # Worker 2 re-claims the expired job
    assert repository.claim_job(job_id, worker_id="worker-new", lease_seconds=300) is True

    # Stale Worker 1 attempts to update progress -> must be rejected
    with pytest.raises(WorkerLeaseLostError):
        repository.update_progress(job_id, worker_id="worker-old", stage=JobStage.RENDERING)

    # Stale Worker 1 attempts to mark succeeded -> must be rejected
    with pytest.raises(WorkerLeaseLostError):
        repository.mark_succeeded(job_id, worker_id="worker-old", result_manifest={})

    # Stale Worker 1 attempts to mark failed -> must be rejected
    with pytest.raises(WorkerLeaseLostError):
        repository.mark_failed(
            job_id, worker_id="worker-old", error_code="ERR", error_message="msg", retryable=False
        )

    # Verify job remains owned by worker-new in PROCESSING state
    current_job = repository.get_by_id(job_id)
    assert current_job is not None
    assert current_job.worker_id == "worker-new"
    assert current_job.state == JobState.PROCESSING.value


def test_cancellation_racing_with_finalizing(test_env: dict[str, Any]) -> None:
    """If user requests cancellation while worker is finalizing, mark_succeeded marks CANCELLED."""
    repository: JobRepository = test_env["repository"]

    job_id = "job-cancel-race-006"
    repository.create_job(
        job_id=job_id,
        source_filename="test.mp4",
        source_storage_path="path/test.mp4",
        target_duration_sec=30.0,
    )
    assert repository.claim_job(job_id, worker_id="worker-racing", lease_seconds=300) is True

    # User requests cancellation while worker is processing
    cancelled_job = repository.request_cancellation(job_id, reason="User cancelled")
    assert cancelled_job.state == JobState.CANCEL_REQUESTED.value

    # Worker finishes rendering and attempts mark_succeeded
    repository.mark_succeeded(job_id, worker_id="worker-racing", result_manifest={"status": "done"})

    # State must be CANCELLED, not SUCCEEDED
    final_job = repository.get_by_id(job_id)
    assert final_job is not None
    assert final_job.state == JobState.CANCELLED.value
    assert final_job.cancelled_at is not None


def test_abandoned_cancel_requested_job_recovered_to_cancelled(test_env: dict[str, Any]) -> None:
    """An abandoned job in CANCEL_REQUESTED state whose worker crashed is finalized to CANCELLED."""
    repository: JobRepository = test_env["repository"]
    from blazzid_jobs.models import JobRecord

    job_id = "job-abandoned-cancel-007"
    repository.create_job(
        job_id=job_id,
        source_filename="test.mp4",
        source_storage_path="path/test.mp4",
        target_duration_sec=30.0,
    )
    assert repository.claim_job(job_id, worker_id="crashed-worker", lease_seconds=10) is True

    # User requested cancellation, then worker crashed
    repository.request_cancellation(job_id)

    # Fast forward past lease expiry
    with repository.session_factory() as session, session.begin():
        j = session.get(JobRecord, job_id)
        assert j is not None
        j.worker_lease_until = datetime.now(timezone.utc) - timedelta(seconds=60)

    # Recovery service runs
    recovered = repository.recover_abandoned_jobs(lease_expired_before=datetime.now(timezone.utc))
    assert job_id in recovered

    job = repository.get_by_id(job_id)
    assert job is not None
    assert job.state == JobState.CANCELLED.value
