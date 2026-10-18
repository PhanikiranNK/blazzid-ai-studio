"""BLAZZID Jobs orchestration, state transitions, persistence, and queueing."""

from blazzid_jobs.database import check_db_ready, create_db_engine, create_session_factory, init_db
from blazzid_jobs.errors import (
    ConcurrencyConflictError,
    IdempotencyConflictError,
    JobCancelledError,
    JobError,
    JobNotFoundError,
    JobTimeoutError,
    PermanentProcessingError,
    RetryableProcessingError,
    WorkerLeaseLostError,
)
from blazzid_jobs.events import JobCancelRequestedEvent, JobEvent, JobQueuedEvent
from blazzid_jobs.models import Base, JobAttemptRecord, JobRecord, OutboxRecord
from blazzid_jobs.queue import (
    InMemoryJobQueue,
    JobQueue,
    OutboxDispatcher,
    QueueMessage,
    RedisJobQueue,
)
from blazzid_jobs.repository import JobRepository
from blazzid_jobs.states import (
    STAGE_PROGRESS_MAP,
    InvalidStateTransitionError,
    JobStage,
    JobState,
    assert_valid_transition,
    can_transition,
)

__all__ = [
    "Base",
    "ConcurrencyConflictError",
    "IdempotencyConflictError",
    "InMemoryJobQueue",
    "InvalidStateTransitionError",
    "JobAttemptRecord",
    "JobCancelRequestedEvent",
    "JobCancelledError",
    "JobError",
    "JobEvent",
    "JobNotFoundError",
    "JobQueue",
    "JobQueuedEvent",
    "JobRecord",
    "JobRepository",
    "JobStage",
    "JobState",
    "JobTimeoutError",
    "OutboxDispatcher",
    "OutboxRecord",
    "PermanentProcessingError",
    "QueueMessage",
    "RedisJobQueue",
    "RetryableProcessingError",
    "STAGE_PROGRESS_MAP",
    "WorkerLeaseLostError",
    "assert_valid_transition",
    "can_transition",
    "check_db_ready",
    "create_db_engine",
    "create_session_factory",
    "init_db",
]
