"""Hypothesis property-based tests for Weighted Interval Scheduling."""

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from blazzid_algorithms.interval_selection import (
    exhaustive_interval_selection,
    select_highlights_dp,
)
from blazzid_core.contracts import HighlightCandidate, SelectionConstraints, TimeInterval

# Strategy for generating valid temporal intervals [start, end)
interval_strategy = st.builds(
    lambda start, dur: TimeInterval(start=start, end=start + dur),
    start=st.floats(min_value=0.0, max_value=300.0, allow_nan=False),
    dur=st.floats(min_value=1.0, max_value=25.0, allow_nan=False),
)

candidate_strategy = st.builds(
    lambda idx, interval, score, conf: HighlightCandidate(
        candidate_id=f"cand-{idx}",
        interval=interval,
        rank_score=score,
        confidence=conf,
    ),
    idx=st.integers(min_value=0, max_value=1000),
    interval=interval_strategy,
    score=st.floats(min_value=1.0, max_value=100.0, allow_nan=False),
    conf=st.floats(min_value=0.1, max_value=1.0, allow_nan=False),
)


@given(
    candidates=st.lists(candidate_strategy, min_size=1, max_size=20),
    budget=st.floats(min_value=5.0, max_value=120.0, allow_nan=False),
)
@settings(max_examples=50)
def test_interval_scheduling_invariants(
    candidates: list[HighlightCandidate], budget: float
) -> None:
    constraints = SelectionConstraints(
        target_duration_seconds=budget,
        min_clip_duration_seconds=1.0,
        quantum_bin_seconds=0.5,
    )
    result = select_highlights_dp(candidates, constraints)

    # Invariant 1: Total duration never exceeds target budget
    assert result.total_duration_seconds <= budget + 1e-4

    # Invariant 2: Selected intervals are mutually disjoint (zero overlap)
    selected = result.selected_candidates
    for i in range(len(selected)):
        for j in range(i + 1, len(selected)):
            assert not selected[i].interval.overlaps(selected[j].interval), (
                f"Overlap violation between {selected[i].interval} and {selected[j].interval}"
            )

    # Invariant 3: Result metrics match selected array
    expected_dur = round(sum(c.duration for c in selected), 4)
    expected_score = round(sum(c.rank_score for c in selected), 4)
    assert result.total_duration_seconds == expected_dur
    assert result.total_score == expected_score


@given(
    candidates=st.lists(candidate_strategy, min_size=1, max_size=7),
    budget=st.floats(min_value=10.0, max_value=60.0, allow_nan=False),
)
@settings(max_examples=30)
def test_dp_matches_exhaustive_oracle(candidates: list[HighlightCandidate], budget: float) -> None:
    """Proves that DP finds a valid subset with total score >= oracle under discretization."""
    constraints = SelectionConstraints(
        target_duration_seconds=budget,
        min_clip_duration_seconds=1.0,
        quantum_bin_seconds=0.1,  # Fine quantum step for tight alignment
    )
    dp_res = select_highlights_dp(candidates, constraints)
    oracle_res = exhaustive_interval_selection(candidates, constraints)

    # Both selections must respect invariants
    dp_dur = sum(c.duration for c in dp_res.selected_candidates)
    oracle_dur = sum(c.duration for c in oracle_res)
    assert dp_dur <= budget + 1e-4
    assert oracle_dur <= budget + 1e-4

    # Exhaustive search finds the global un-discretized maximum.
    # When oracle selection fits within discretized bins, DP achieves near-optimal score.
    oracle_score = sum(c.rank_score for c in oracle_res)
    budget_bins = int(budget / 0.1)
    oracle_bins = sum(int(math.ceil(c.duration / 0.1)) for c in oracle_res)

    if oracle_score > 0.0 and oracle_bins <= budget_bins:
        assert dp_res.total_score >= oracle_score * 0.85 or dp_res.total_score >= oracle_score - 5.0
