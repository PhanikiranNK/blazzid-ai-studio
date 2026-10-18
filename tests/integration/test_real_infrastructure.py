"""Integration tests against real PostgreSQL and Redis infrastructure."""

from __future__ import annotations

import io
import os
import uuid
from pathlib import Path
from typing import Any

import pytest
import redis
from sqlalchemy import text

from blazzid_jobs.database import create_db_engine, create_session_factory, init_db
from blazzid_jobs.queue import OutboxDispatcher, RedisJobQueue
from blazzid_jobs.repository import JobRepository
from blazzid_jobs.states import JobState
from blazzid_media.probe import probe_media
from blazzid_storage.interfaces import ArtifactType
from blazzid_storage.local import LocalStorageBackend
from blazzid_worker.config import WorkerSettings
from blazzid_worker.consumer import WorkerConsumer
from tests.fixtures.synthetic_media import generate_synthetic_video, is_ffmpeg_available

POSTGRES_URL = os.getenv(
    "TEST_POSTGRES_URL", "postgresql+psycopg://phanikirannk@localhost:5432/blazzid_test_db"
)
REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/0")


def is_postgres_available() -> bool:
    try:
        engine = create_db_engine(POSTGRES_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


def is_redis_available() -> bool:
    try:
        r = redis.Redis.from_url(REDIS_URL, socket_timeout=1.0)
        res = bool(r.ping())
        r.close()
        return res
    except Exception:
        return False


pytestmark = [
    pytest.mark.skipif(not is_ffmpeg_available(), reason="FFmpeg is required"),
    pytest.mark.skipif(not is_postgres_available(), reason="PostgreSQL 16+ required"),
    pytest.mark.skipif(not is_redis_available(), reason="Redis 7+ required"),
]


@pytest.fixture
def real_infra(tmp_path: Path) -> dict[str, Any]:
    engine = create_db_engine(POSTGRES_URL)
    init_db(engine)
    session_factory = create_session_factory(engine)
    repository = JobRepository(session_factory)

    r_client = redis.Redis.from_url(REDIS_URL)
    stream_key = f"blazzid:jobs:test:{uuid.uuid4().hex[:8]}"
    group_name = "test-workers"
    queue = RedisJobQueue(
        redis_client=r_client,
        stream_key=stream_key,
        group_name=group_name,
        consumer_name="worker-real-01",
        min_idle_time_ms=500,  # low idle time for test reclaim
    )

    storage = LocalStorageBackend(root_dir=tmp_path / "storage")

    settings = WorkerSettings(
        worker_id="worker-real-01",
        database_url=POSTGRES_URL,
        redis_url=REDIS_URL,
        storage_root=tmp_path / "storage",
        lease_seconds=60,
    )

    consumer = WorkerConsumer(
        storage=storage,
        repository=repository,
        queue=queue,
        settings=settings,
    )

    yield {
        "engine": engine,
        "repository": repository,
        "queue": queue,
        "storage": storage,
        "consumer": consumer,
        "redis_client": r_client,
        "stream_key": stream_key,
        "group_name": group_name,
        "tmp_path": tmp_path,
    }

    engine.dispose()
    r_client.close()


def test_real_postgres_locking_and_outbox_atomicity(real_infra: dict[str, Any]) -> None:
    """Verify PostgreSQL transactions, locking, and outbox behavior."""
    repo: JobRepository = real_infra["repository"]
    queue: RedisJobQueue = real_infra["queue"]

    job_id = f"job-pg-{uuid.uuid4().hex[:8]}"
    job = repo.create_job(
        job_id=job_id,
        source_filename="video.mp4",
        source_storage_path=f"jobs/{job_id}/source/video.mp4",
        target_duration_sec=20.0,
        owner_id="user:alice",
        idempotency_key=f"idemp-{job_id}",
    )
    assert job.job_id == job_id
    assert job.owner_id == "user:alice"

    # Verify pending outbox record
    pending = repo.get_pending_outbox_events()
    assert any(p.job_id == job_id for p in pending)

    # Dispatch to Redis Streams
    dispatcher = OutboxDispatcher(repository=repo, queue=queue)
    dispatched = dispatcher.dispatch_pending()
    assert dispatched >= 1

    # Concurrent claim verification in PostgreSQL using SELECT FOR UPDATE
    claimed_1 = repo.claim_job(job_id, worker_id="worker-A")
    claimed_2 = repo.claim_job(job_id, worker_id="worker-B")
    assert claimed_1 is True
    assert claimed_2 is False  # Row lock prevented duplicate claim


def test_real_pipeline_execution_end_to_end(real_infra: dict[str, Any]) -> None:
    """Submit a real synthetic recording and process end-to-end through Postgres and Redis."""
    repo: JobRepository = real_infra["repository"]
    storage: LocalStorageBackend = real_infra["storage"]
    queue: RedisJobQueue = real_infra["queue"]
    consumer: WorkerConsumer = real_infra["consumer"]
    tmp_path: Path = real_infra["tmp_path"]

    # 1. Generate real synthetic video
    video_path = generate_synthetic_video(
        duration_seconds=4.0,
        width=320,
        height=240,
        fps=15,
        output_path=tmp_path / "real_sample.mp4",
    )

    job_id = f"job-real-{uuid.uuid4().hex[:8]}"
    with open(video_path, "rb") as f:
        storage.store_stream(
            job_id=job_id,
            filename="real_sample.mp4",
            stream=f,
            max_bytes=50 * 1024 * 1024,
        )

    # 2. Create job in PostgreSQL
    repo.create_job(
        job_id=job_id,
        source_filename="real_sample.mp4",
        source_storage_path=f"jobs/{job_id}/source/real_sample.mp4",
        target_duration_sec=10.0,
        assembly_profile="youtube_shorts",
    )

    # 3. Dispatch outbox to Redis Streams
    dispatcher = OutboxDispatcher(repository=repo, queue=queue)
    dispatcher.dispatch_pending()

    # 4. Worker executes pipeline
    processed = consumer.run_once(timeout_ms=2000)
    assert processed is True

    # 5. Verify PostgreSQL job state
    job = repo.get_by_id(job_id)
    assert job is not None
    assert job.state == JobState.SUCCEEDED.value
    assert job.progress_percent == 100.0

    # 6. Verify rendered montage artifact with ffprobe
    montage_path = storage.get_artifact_path(job_id, ArtifactType.RENDERED_MONTAGE)
    assert montage_path is not None
    assert montage_path.exists()
    assert montage_path.stat().st_size > 0

    inspection = probe_media(montage_path)
    assert inspection.container.duration_seconds > 0.5
    assert inspection.video is not None
    assert inspection.video.width == 1080  # Normalized to 9:16 Shorts canvas
    assert inspection.video.height == 1920


def test_real_redis_xautoclaim_recovery(real_infra: dict[str, Any]) -> None:
    """Verify XAUTOCLAIM recovers pending messages from a crashed consumer."""
    r_client: redis.Redis = real_infra["redis_client"]
    stream_key: str = real_infra["stream_key"]
    group_name: str = real_infra["group_name"]
    repo: JobRepository = real_infra["repository"]

    # Dead worker queue setup
    dead_queue = RedisJobQueue(
        redis_client=r_client,
        stream_key=stream_key,
        group_name=group_name,
        consumer_name="dead-worker-99",
    )

    job_id = f"job-xclaim-{uuid.uuid4().hex[:8]}"
    repo.create_job(
        job_id=job_id,
        source_filename="input.mp4",
        source_storage_path=f"jobs/{job_id}/source/input.mp4",
        target_duration_sec=15.0,
    )

    # Publish message
    dead_queue.publish(job_id, "job.queued", {"job_id": job_id})

    # Dead worker consumes message but crashes before acking
    consumed_msg = dead_queue.consume(timeout_ms=1000)
    assert consumed_msg is not None
    assert consumed_msg.job_id == job_id
    # Dead worker crashes without calling dead_queue.ack()

    # Wait for min_idle_time_ms threshold
    import time

    time.sleep(0.6)

    # Alive worker consumes with XAUTOCLAIM
    alive_queue = RedisJobQueue(
        redis_client=r_client,
        stream_key=stream_key,
        group_name=group_name,
        consumer_name="alive-worker-01",
        min_idle_time_ms=500,
    )
    reclaimed_msg = alive_queue.consume(timeout_ms=1000)
    assert reclaimed_msg is not None
    assert reclaimed_msg.job_id == job_id

    # Alive worker can acknowledge the reclaimed message
    alive_queue.ack(reclaimed_msg.message_id)


def test_real_postgres_corrupt_media_handling(real_infra: dict[str, Any]) -> None:
    """Verify real pipeline corrupt media handling does not produce false success."""
    repo: JobRepository = real_infra["repository"]
    storage: LocalStorageBackend = real_infra["storage"]
    queue: RedisJobQueue = real_infra["queue"]
    consumer: WorkerConsumer = real_infra["consumer"]

    job_id = f"job-corrupt-pg-{uuid.uuid4().hex[:8]}"
    storage.store_stream(
        job_id=job_id,
        filename="corrupt.mp4",
        stream=io.BytesIO(b"totally corrupted file bytes"),
        max_bytes=1024 * 1024,
    )
    repo.create_job(
        job_id=job_id,
        source_filename="corrupt.mp4",
        source_storage_path=f"jobs/{job_id}/source/corrupt.mp4",
        target_duration_sec=15.0,
    )

    queue.publish(job_id, "job.queued", {"job_id": job_id})
    processed = consumer.run_once(timeout_ms=2000)
    assert processed is True

    job = repo.get_by_id(job_id)
    assert job is not None
    assert job.state == JobState.FAILED.value
    assert job.error_code == "PERMANENT_ERROR"
