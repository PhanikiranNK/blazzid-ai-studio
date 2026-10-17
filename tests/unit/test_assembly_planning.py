"""Unit tests for clip boundary planning and montage timeline mapping."""

from __future__ import annotations

from blazzid_assembly.config import AssemblyConfig
from blazzid_assembly.planning import plan_edit_decision_list
from blazzid_core.contracts.candidates import HighlightCandidate
from blazzid_core.contracts.time import TimeInterval


def _make_candidate(cid: str, start: float, end: float, score: float = 0.8) -> HighlightCandidate:
    return HighlightCandidate(
        candidate_id=cid,
        interval=TimeInterval(start=start, end=end),
        rank_score=score,
        confidence=0.8,
        category="SUSTAINED_COMBAT",
    )


def test_planning_empty_candidates() -> None:
    cfg = AssemblyConfig(target_duration_seconds=20.0)
    plan = plan_edit_decision_list([], [], source_duration_seconds=60.0, config=cfg)

    assert len(plan.clips) == 0
    assert plan.total_duration_seconds == 0.0
    assert plan.budget_shortfall_seconds == 20.0


def test_planning_applies_context_padding_and_clamps() -> None:
    c1 = _make_candidate(
        "c1", 0.2, 5.0
    )  # Starts at 0.2s, padding lead_in=1.0s should clamp to 0.0s
    c2 = _make_candidate(
        "c2", 25.0, 29.8
    )  # Ends at 29.8s, source_duration=30.0s should clamp to 30.0s

    cfg = AssemblyConfig(
        target_duration_seconds=30.0,
        lead_in_padding_seconds=1.0,
        lead_out_padding_seconds=1.0,
    )
    plan = plan_edit_decision_list([c1, c2], [], source_duration_seconds=30.0, config=cfg)

    assert len(plan.clips) == 2

    # Clip 1 clamped to 0.0 at start
    assert plan.clips[0].source_interval.start == 0.0
    assert plan.clips[0].source_interval.end == 6.0

    # Clip 2 clamped to 30.0 at end
    assert plan.clips[1].source_interval.start == 24.0
    assert plan.clips[1].source_interval.end == 30.0


def test_planning_resolves_adjacent_padded_overlaps() -> None:
    # c1 [10.0, 15.0) and c2 [16.0, 20.0)
    # With 1.5s lead-in and lead-out:
    # c1 would extend to 16.5, c2 would start at 14.5 (2.0s overlap)
    c1 = _make_candidate("c1", 10.0, 15.0)
    c2 = _make_candidate("c2", 16.0, 20.0)

    cfg = AssemblyConfig(
        target_duration_seconds=30.0,
        lead_in_padding_seconds=1.5,
        lead_out_padding_seconds=1.5,
    )
    plan = plan_edit_decision_list([c1, c2], [], source_duration_seconds=60.0, config=cfg)

    assert len(plan.clips) == 2
    # Ensure no overlap: clip 0 end <= clip 1 start
    assert plan.clips[0].source_interval.end <= plan.clips[1].source_interval.start


def test_planning_montage_timeline_offsets_are_contiguous() -> None:
    c1 = _make_candidate("c1", 5.0, 10.0)
    c2 = _make_candidate("c2", 20.0, 26.0)

    cfg = AssemblyConfig(lead_in_padding_seconds=0.0, lead_out_padding_seconds=0.0)
    plan = plan_edit_decision_list([c1, c2], [], source_duration_seconds=60.0, config=cfg)

    assert len(plan.clips) == 2
    # Clip 0: [0.0, 5.0)
    assert plan.clips[0].montage_interval.start == 0.0
    assert plan.clips[0].montage_interval.end == 5.0

    # Clip 1: [5.0, 11.0)
    assert plan.clips[1].montage_interval.start == 5.0
    assert plan.clips[1].montage_interval.end == 11.0

    assert plan.total_duration_seconds == 11.0
