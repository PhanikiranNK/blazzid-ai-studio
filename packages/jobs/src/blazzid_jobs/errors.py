"""Job orchestration domain exceptions and error classifications."""

from __future__ import annotations

from blazzid_core.errors import BlazzidError
from blazzid_jobs.states import InvalidStateTransitionError


class JobError(BlazzidError):
    """Base exception for all job orchestration errors."""


class JobNotFoundError(JobError):
    """Raised when a referenced job cannot be found in persistence."""


class IdempotencyConflictError(JobError):
    """Raised when an idempotency key conflict occurs with mismatched parameters."""


class ConcurrencyConflictError(JobError):
    """Raised when an optimistic lock version conflict occurs during concurrent updates."""


class WorkerLeaseLostError(JobError):
    """Raised when a worker attempts to update a job whose lease has expired or was claimed."""


class PermanentProcessingError(JobError):
    """Raised when processing fails due to unrecoverable errors (e.g. invalid media, corrupt file)."""


class RetryableProcessingError(JobError):
    """Raised when processing fails due to transient infrastructure issues (e.g. network blip, OOM)."""


class JobTimeoutError(JobError):
    """Raised when job processing exceeds the configured maximum execution time."""


class JobCancelledError(JobError):
    """Raised when job execution is interrupted due to cancellation."""


__all__ = [
    "ConcurrencyConflictError",
    "IdempotencyConflictError",
    "InvalidStateTransitionError",
    "JobCancelledError",
    "JobError",
    "JobNotFoundError",
    "JobTimeoutError",
    "PermanentProcessingError",
    "RetryableProcessingError",
    "WorkerLeaseLostError",
]
