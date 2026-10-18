"""Queue consumer daemon with heartbeat lease renewal and error handling."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from blazzid_jobs.errors import (
    JobCancelledError,
    PermanentProcessingError,
    RetryableProcessingError,
    WorkerLeaseLostError,
)
from blazzid_jobs.queue import JobQueue, OutboxDispatcher
from blazzid_jobs.repository import JobRepository
from blazzid_storage.interfaces import StorageBackend
from blazzid_worker.config import WorkerSettings
from blazzid_worker.processor import MediaJobProcessor
from blazzid_worker.recovery import JobRecoveryService

logger = logging.getLogger("blazzid.worker.consumer")


class WorkerConsumer:
    """Consumes job events, manages lease heartbeats, and drives pipeline processing."""

    def __init__(
        self,
        storage: StorageBackend,
        repository: JobRepository,
        queue: JobQueue,
        settings: WorkerSettings,
    ) -> None:
        self.storage = storage
        self.repository = repository
        self.queue = queue
        self.settings = settings
        self.processor = MediaJobProcessor(storage=storage, repository=repository)
        self.recovery_service = JobRecoveryService(repository=repository)
        self.outbox_dispatcher = OutboxDispatcher(repository=repository, queue=queue)

        self._shutdown_event = threading.Event()
        self._active_job_id: Optional[str] = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._last_maintenance_time: float = 0.0

    def request_shutdown(self) -> None:
        """Signal consumer to stop processing new jobs and shut down cleanly."""
        logger.info("Shutdown requested for worker %s", self.settings.worker_id)
        self._shutdown_event.set()

    def _start_heartbeat(self, job_id: str) -> threading.Event:
        stop_heartbeat = threading.Event()

        def _heartbeat_loop() -> None:
            while not stop_heartbeat.wait(timeout=self.settings.lease_heartbeat_interval_sec):
                if self._shutdown_event.is_set():
                    break
                try:
                    extended = self.repository.extend_lease(
                        job_id=job_id,
                        worker_id=self.settings.worker_id,
                        lease_seconds=self.settings.lease_seconds,
                    )
                    if not extended:
                        logger.warning("Heartbeat failed to extend lease for job %s", job_id)
                        break
                except Exception as err:
                    logger.warning("Error during lease heartbeat for %s: %s", job_id, err)

        t = threading.Thread(target=_heartbeat_loop, daemon=True, name=f"heartbeat-{job_id}")
        t.start()
        return stop_heartbeat

    def _run_maintenance_if_due(self) -> None:
        """Run periodic lease recovery and outbox dispatch."""
        now_ts = time.time()
        if now_ts - self._last_maintenance_time >= 15.0:
            self._last_maintenance_time = now_ts
            try:
                self.recovery_service.recover(datetime.now(timezone.utc))
            except Exception as err:
                logger.warning("Recovery maintenance error: %s", err)
            try:
                self.outbox_dispatcher.dispatch_pending(batch_size=50)
            except Exception as err:
                logger.warning("Outbox maintenance error: %s", err)

    def run_once(self, timeout_ms: int = 1000) -> bool:
        """Process a single queue message if available. Returns True if work was processed."""
        if self._shutdown_event.is_set():
            return False

        self._run_maintenance_if_due()

        message = self.queue.consume(timeout_ms=timeout_ms)
        if message is None:
            return False

        job_id = message.job_id
        if not job_id:
            self.queue.ack(message.message_id)
            return False

        logger.info("Worker %s received message for job %s", self.settings.worker_id, job_id)

        # Attempt to claim job atomically
        claimed = self.repository.claim_job(
            job_id=job_id,
            worker_id=self.settings.worker_id,
            lease_seconds=self.settings.lease_seconds,
        )

        if not claimed:
            logger.info("Job %s could not be claimed (already processing or cancelled)", job_id)
            self.queue.ack(message.message_id)
            return False

        job = self.repository.get_by_id(job_id)
        if job is None:
            self.queue.ack(message.message_id)
            return False

        self._active_job_id = job_id
        stop_heartbeat = self._start_heartbeat(job_id)

        try:
            result_manifest = self.processor.process(
                job=job,
                worker_id=self.settings.worker_id,
                is_cancelled_fn=lambda: (
                    self._shutdown_event.is_set() or self.repository.check_cancellation(job_id)
                ),
            )
            self.repository.mark_succeeded(
                job_id=job_id,
                worker_id=self.settings.worker_id,
                result_manifest=result_manifest,
            )
            logger.info("Job %s marked SUCCEEDED", job_id)
        except WorkerLeaseLostError as err:
            logger.warning(
                "Worker %s abandoned updates for job %s because lease was lost: %s",
                self.settings.worker_id,
                job_id,
                err,
            )
        except JobCancelledError as err:
            logger.info("Job %s cancelled during processing: %s", job_id, err)
            self.repository.mark_cancelled(job_id=job_id, worker_id=self.settings.worker_id)
        except PermanentProcessingError as err:
            logger.error("Job %s permanent error: %s", job_id, err)
            self.repository.mark_failed(
                job_id=job_id,
                worker_id=self.settings.worker_id,
                error_code="PERMANENT_ERROR",
                error_message=str(err),
                retryable=False,
            )
        except RetryableProcessingError as err:
            logger.warning("Job %s retryable error: %s", job_id, err)
            self.repository.mark_failed(
                job_id=job_id,
                worker_id=self.settings.worker_id,
                error_code="RETRYABLE_ERROR",
                error_message=str(err),
                retryable=True,
            )
        except Exception as err:
            logger.exception("Job %s encountered unexpected failure: %s", job_id, err)
            self.repository.mark_failed(
                job_id=job_id,
                worker_id=self.settings.worker_id,
                error_code="UNEXPECTED_FAILURE",
                error_message=str(err),
                retryable=True,
            )
        finally:
            stop_heartbeat.set()
            self._active_job_id = None
            self.queue.ack(message.message_id)

        return True

    def run_forever(self) -> None:
        """Run consumer loop until shutdown is signaled."""
        logger.info("Starting worker loop for %s...", self.settings.worker_id)
        while not self._shutdown_event.is_set():
            try:
                self.run_once(timeout_ms=1000)
            except Exception as err:
                logger.error("Error in consumer loop: %s", err)
                time.sleep(1.0)
        logger.info("Worker %s loop terminated.", self.settings.worker_id)
