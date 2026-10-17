"""Unit tests for duration-budgeted highlight selection and oracle optimality."""

from __future__ import annotations

from blazzid_algorithms.interval_selection import exhaustive_interval_selection
from blazzid_assembly.config import AssemblyConfig
from blazzid_assembly.models import ExclusionReason
from blazzid_assembly.selection import select_budgeted_highlights
from blazzid_core.contracts.candidates import HighlightCandidate
from blazzid_core.contracts.selection import SelectionConstraints
from blazzid_core.contracts.time import TimeInterval


def _make_highlight(
    cid: str,
    start: float,
    end: float,
    score: float,
    confidence: float = 0.8,
) -> HighlightCandidate:
    return HighlightCandidate(
        candidate_id=cid,
        interval=TimeInterval(start=start, end=end),
        rank_score=score,
        confidence=confidence,
        category="SUSTAINED_COMBAT",
    )


def test_selection_respects_duration_budget() -> None:
    # 3 non-overlapping candidates of length 5s, 6s, 8s (total = 19s), budget = 12s
    c1 = _make_highlight("c1", 0.0, 5.0, score=0.6)
    c2 = _make_highlight("c2", 10.0, 16.0, score=0.9)
    c3 = _make_highlight("c3", 20.0, 28.0, score=0.7)

    cfg = AssemblyConfig(target_duration_seconds=12.0)
    selected, exclusions, shortfall = select_budgeted_highlights([c1, c2, c3], cfg)

    # c2 (6s, 0.9) + c1 (5s, 0.6) = 11s <= 12s with score = 1.5
    assert len(selected) == 2
    selected_ids = {c.candidate_id for c in selected}
    assert "c2" in selected_ids
    assert "c1" in selected_ids
    assert "c3" not in selected_ids

    total_dur = sum(c.duration for c in selected)
    assert total_dur <= 12.0
    assert shortfall == 1.0  # 12.0 - 11.0 = 1.0s

    # Verify exclusion record
    c3_excl = next(e for e in exclusions if e.candidate_id == "c3")
    assert c3_excl.reason == ExclusionReason.BUDGET_EXHAUSTED


def test_selection_excludes_too_short_or_too_long_clips() -> None:
    too_short = _make_highlight("short", 0.0, 1.0, score=0.5)  # 1.0s < min 2.0s
    too_long = _make_highlight("long", 10.0, 25.0, score=0.8)  # 15.0s > max 10.0s
    valid = _make_highlight("valid", 30.0, 35.0, score=0.7)  # 5.0s

    cfg = AssemblyConfig(
        target_duration_seconds=30.0,
        min_clip_duration_seconds=2.0,
        max_clip_duration_seconds=10.0,
    )
    selected, exclusions, _ = select_budgeted_highlights([too_short, too_long, valid], cfg)

    assert len(selected) == 1
    assert selected[0].candidate_id == "valid"

    short_excl = next(e for e in exclusions if e.candidate_id == "short")
    assert short_excl.reason == ExclusionReason.DURATION_TOO_SHORT

    long_excl = next(e for e in exclusions if e.candidate_id == "long")
    assert long_excl.reason == ExclusionReason.DURATION_EXCEEDS_BUDGET


def test_selection_excludes_overlapping_inferior_candidate() -> None:
    # c1 [10, 18) score 0.9, overlaps with c2 [14, 20) score 0.5
    c1 = _make_highlight("c1", 10.0, 18.0, score=0.9)
    c2 = _make_highlight("c2", 14.0, 20.0, score=0.5)

    cfg = AssemblyConfig(target_duration_seconds=20.0)
    selected, exclusions, _ = select_budgeted_highlights([c1, c2], cfg)

    assert len(selected) == 1
    assert selected[0].candidate_id == "c1"

    c2_excl = next(e for e in exclusions if e.candidate_id == "c2")
    assert c2_excl.reason == ExclusionReason.OVERLAPS_SUPERIOR_CANDIDATE


def test_selection_enforces_max_clips_limit() -> None:
    # 4 non-overlapping candidates, but max_clips_count = 2
    c1 = _make_highlight("c1", 0.0, 4.0, score=0.4)
    c2 = _make_highlight("c2", 5.0, 9.0, score=0.9)
    c3 = _make_highlight("c3", 10.0, 14.0, score=0.8)
    c4 = _make_highlight("c4", 15.0, 19.0, score=0.3)

    cfg = AssemblyConfig(target_duration_seconds=30.0, max_clips_count=2)
    selected, exclusions, _ = select_budgeted_highlights([c1, c2, c3, c4], cfg)

    assert len(selected) == 2
    selected_ids = {c.candidate_id for c in selected}
    assert selected_ids == {"c2", "c3"}

    max_excls = [e for e in exclusions if e.reason == ExclusionReason.MAX_CLIPS_REACHED]
    assert len(max_excls) == 2


def test_selection_matches_brute_force_oracle() -> None:
    """Verifies that select_budgeted_highlights achieves the exact same optimal subset as the brute-force oracle."""
    cands = [
        _make_highlight("c1", 1.0, 5.0, score=0.4),
        _make_highlight("c2", 4.0, 8.0, score=0.7),
        _make_highlight("c3", 7.0, 12.0, score=0.9),
        _make_highlight("c4", 11.0, 15.0, score=0.5),
        _make_highlight("c5", 14.0, 19.0, score=0.8),
    ]

    budget = 14.0
    cfg = AssemblyConfig(target_duration_seconds=budget, quantum_bin_seconds=0.5)
    selected, _, _ = select_budgeted_highlights(cands, cfg)

    # Run exhaustive oracle
    constraints = SelectionConstraints(
        target_duration_seconds=budget,
        quantum_bin_seconds=0.5,
        min_clip_duration_seconds=cfg.min_clip_duration_seconds,
    )
    oracle_selected = exhaustive_interval_selection(cands, constraints)

    dp_score = sum(c.rank_score for c in selected)
    oracle_score = sum(c.rank_score for c in oracle_selected)

    assert abs(dp_score - oracle_score) < 1e-4
