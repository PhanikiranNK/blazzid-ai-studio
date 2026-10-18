"""Unit tests for job state transitions and monotonic progress."""

from __future__ import annotations

import pytest

from blazzid_jobs.states import (
    STAGE_PROGRESS_MAP,
    InvalidStateTransitionError,
    JobStage,
    JobState,
    assert_valid_transition,
    can_transition,
)


def test_permitted_normal_transitions() -> None:
    # QUEUED -> PROCESSING -> SUCCEEDED
    assert can_transition(JobState.QUEUED, JobState.PROCESSING)
    assert can_transition(JobState.PROCESSING, JobState.SUCCEEDED)

    # QUEUED -> PROCESSING -> FAILED
    assert can_transition(JobState.PROCESSING, JobState.FAILED)

    # QUEUED -> PROCESSING -> CANCEL_REQUESTED -> CANCELLED
    assert can_transition(JobState.PROCESSING, JobState.CANCEL_REQUESTED)
    assert can_transition(JobState.CANCEL_REQUESTED, JobState.CANCELLED)

    # Immediate cancellation of QUEUED job
    assert can_transition(JobState.QUEUED, JobState.CANCELLED)

    # Idempotent self-transitions
    for state in JobState:
        assert can_transition(state, state)


def test_prohibited_transitions_raise() -> None:
    # Terminal states cannot transition to processing or queued
    assert not can_transition(JobState.SUCCEEDED, JobState.PROCESSING)
    assert not can_transition(JobState.SUCCEEDED, JobState.QUEUED)
    assert not can_transition(JobState.CANCELLED, JobState.PROCESSING)
    assert not can_transition(JobState.CANCELLED, JobState.QUEUED)

    with pytest.raises(InvalidStateTransitionError):
        assert_valid_transition(JobState.SUCCEEDED, JobState.PROCESSING)

    with pytest.raises(InvalidStateTransitionError):
        assert_valid_transition(JobState.CANCELLED, JobState.QUEUED)

    # Cannot skip straight from QUEUED to SUCCEEDED
    assert not can_transition(JobState.QUEUED, JobState.SUCCEEDED)
    with pytest.raises(InvalidStateTransitionError):
        assert_valid_transition(JobState.QUEUED, JobState.SUCCEEDED)


def test_failed_retry_transition() -> None:
    # FAILED can transition back to QUEUED via explicit retry
    assert can_transition(JobState.FAILED, JobState.QUEUED)
    assert_valid_transition(JobState.FAILED, JobState.QUEUED)


def test_stage_progress_mapping_monotonicity() -> None:
    ordered_stages = [
        JobStage.VALIDATING_INPUT,
        JobStage.PROBING_MEDIA,
        JobStage.PREPROCESSING,
        JobStage.DETECTING_EVENTS,
        JobStage.RANKING_HIGHLIGHTS,
        JobStage.PLANNING_EDIT,
        JobStage.RENDERING,
        JobStage.VALIDATING_OUTPUT,
        JobStage.FINALIZING,
    ]

    last_val = 0.0
    for stage in ordered_stages:
        val = STAGE_PROGRESS_MAP[stage]
        assert val >= last_val, f"Progress for stage {stage} must not decrease"
        assert 0.0 <= val <= 100.0
        last_val = val

    assert STAGE_PROGRESS_MAP[JobStage.FINALIZING] == 100.0
