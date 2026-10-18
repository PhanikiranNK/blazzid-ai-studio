"""Job lifecycle states, pipeline stages, and transition validation rules."""

from __future__ import annotations

from enum import Enum

from blazzid_core.errors import BlazzidError


class InvalidStateTransitionError(BlazzidError):
    """Raised when an illegal lifecycle transition is requested."""


class JobState(str, Enum):
    """Lifecycle states for asynchronous video processing jobs."""

    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        """Return True if this state is a terminal final state."""
        return self in (JobState.SUCCEEDED, JobState.CANCELLED)


class JobStage(str, Enum):
    """Named pipeline stages exposing monotonic progress."""

    VALIDATING_INPUT = "VALIDATING_INPUT"
    PROBING_MEDIA = "PROBING_MEDIA"
    PREPROCESSING = "PREPROCESSING"
    DETECTING_EVENTS = "DETECTING_EVENTS"
    RANKING_HIGHLIGHTS = "RANKING_HIGHLIGHTS"
    PLANNING_EDIT = "PLANNING_EDIT"
    RENDERING = "RENDERING"
    VALIDATING_OUTPUT = "VALIDATING_OUTPUT"
    FINALIZING = "FINALIZING"


# Stage weights / default progress percentages (0-100)
STAGE_PROGRESS_MAP: dict[JobStage, float] = {
    JobStage.VALIDATING_INPUT: 5.0,
    JobStage.PROBING_MEDIA: 10.0,
    JobStage.PREPROCESSING: 25.0,
    JobStage.DETECTING_EVENTS: 50.0,
    JobStage.RANKING_HIGHLIGHTS: 65.0,
    JobStage.PLANNING_EDIT: 75.0,
    JobStage.RENDERING: 90.0,
    JobStage.VALIDATING_OUTPUT: 95.0,
    JobStage.FINALIZING: 100.0,
}

# Permitted state transition map
_PERMITTED_TRANSITIONS: dict[JobState, set[JobState]] = {
    JobState.QUEUED: {
        JobState.PROCESSING,
        JobState.CANCELLED,
        JobState.FAILED,
    },
    JobState.PROCESSING: {
        JobState.SUCCEEDED,
        JobState.FAILED,
        JobState.CANCEL_REQUESTED,
        JobState.CANCELLED,
    },
    JobState.CANCEL_REQUESTED: {
        JobState.CANCELLED,
        JobState.FAILED,
        JobState.SUCCEEDED,  # In case processing finalized immediately before cancellation took effect
    },
    JobState.FAILED: {
        JobState.QUEUED,  # Allowed only via explicit retry / administrative recovery
    },
    JobState.SUCCEEDED: set(),  # Terminal
    JobState.CANCELLED: set(),  # Terminal
}


def can_transition(from_state: JobState, to_state: JobState) -> bool:
    """Return whether transitioning from from_state to to_state is valid."""
    if from_state == to_state:
        return True  # Idempotent self-transitions
    return to_state in _PERMITTED_TRANSITIONS.get(from_state, set())


def assert_valid_transition(from_state: JobState, to_state: JobState) -> None:
    """Assert transition is valid; raise InvalidStateTransitionError otherwise."""
    if not can_transition(from_state, to_state):
        raise InvalidStateTransitionError(
            f"Illegal state transition from {from_state.value} to {to_state.value}"
        )
