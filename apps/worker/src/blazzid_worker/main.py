"""Entry point for the BLAZZID media worker process."""

from __future__ import annotations

import logging
import signal
import sys
from typing import Any

import redis

from blazzid_jobs.database import (
    check_db_ready,
    create_db_engine,
    create_session_factory,
    init_db,
)
from blazzid_jobs.queue import InMemoryJobQueue, JobQueue, RedisJobQueue
from blazzid_jobs.repository import JobRepository
from blazzid_storage.local import LocalStorageBackend
from blazzid_worker.config import get_worker_settings
from blazzid_worker.consumer import WorkerConsumer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("blazzid.worker")


def main() -> None:
    """Launch the BLAZZID media worker daemon."""
    settings = get_worker_settings()
    logger.info("Initializing BLAZZID media worker (ID: %s)...", settings.worker_id)

    engine = create_db_engine(settings.database_url)
    if engine.dialect.name == "sqlite":
        init_db(engine)
    else:
        import time

        for attempt in range(1, 31):
            if check_db_ready(engine):
                break
            logger.info("Waiting for database to become ready (attempt %d/30)...", attempt)
            time.sleep(1)
    session_factory = create_session_factory(engine)
    repository = JobRepository(session_factory)
    storage = LocalStorageBackend(root_dir=settings.storage_root)

    queue: JobQueue
    if settings.redis_url.startswith("redis://"):
        try:
            r = redis.Redis.from_url(settings.redis_url, socket_timeout=3.0)
            r.ping()
            queue = RedisJobQueue(redis_client=r, consumer_name=settings.worker_id)
            logger.info("Connected to Redis Streams queue at %s", settings.redis_url)
        except Exception as err:
            logger.warning("Could not connect to Redis (%s), using in-memory queue", err)
            queue = InMemoryJobQueue()
    else:
        queue = InMemoryJobQueue()

    consumer = WorkerConsumer(
        storage=storage,
        repository=repository,
        queue=queue,
        settings=settings,
    )

    def handle_signal(sig: int, frame: Any) -> None:
        logger.info("Received signal %d; shutting down worker...", sig)
        consumer.request_shutdown()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        consumer.run_forever()
    except Exception as err:
        logger.exception("Fatal error in worker: %s", err)
        sys.exit(1)


if __name__ == "__main__":
    main()
