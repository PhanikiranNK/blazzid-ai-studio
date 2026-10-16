"""Unit tests for Weighted Interval Scheduling with Duration Budget."""

import pytest

from blazzid_algorithms.interval_selection import (
    exhaustive_interval_selection,
    select_highlights_dp,
)
from blazzid_core.contracts import HighlightCandidate, SelectionConstraints, TimeInterval


class TestIntervalSelection:
    def test_dp_beats_greedy_counterexample(self) -> None:
        """Proves that DP finds the optimal subset where greedy by score fails.

        Scenario:
        - Candidate A spans [0, 10) with score 80 (duration 10s).
        - Candidate B spans [0, 5) with score 50 (duration 5s).
        - Candidate C spans [5, 10) with score 50 (duration 5s).
        Total budget: 10s.

        Greedy by score picks A (score 80) and terminates because B and C overlap with A.
        DP evaluates both combinations and selects {B, C} for a total score of 100!
        """
        cand_a = HighlightCandidate(
            candidate_id="A",
            interval=TimeInterval(start=0.0, end=10.0),
            rank_score=80.0,
            confidence=0.9,
        )
        cand_b = HighlightCandidate(
            candidate_id="B",
            interval=TimeInterval(start=0.0, end=5.0),
            rank_score=50.0,
            confidence=0.9,
        )
        cand_c = HighlightCandidate(
            candidate_id="C",
            interval=TimeInterval(start=5.0, end=10.0),
            rank_score=50.0,
            confidence=0.9,
        )

        constraints = SelectionConstraints(
            target_duration_seconds=10.0,
            min_clip_duration_seconds=1.0,
            quantum_bin_seconds=0.5,
        )

        result = select_highlights_dp([cand_a, cand_b, cand_c], constraints)

        selected_ids = [c.candidate_id for c in result.selected_candidates]
        assert selected_ids == ["B", "C"]
        assert result.total_score == 100.0
        assert result.total_duration_seconds == 10.0

    def test_zero_overlap_invariant(self) -> None:
        """Tests that selected clips never have overlapping intervals."""
        candidates = [
            HighlightCandidate(
                candidate_id="c1",
                interval=TimeInterval(start=0.0, end=6.0),
                rank_score=30.0,
                confidence=0.8,
            ),
            HighlightCandidate(
                candidate_id="c2",
                interval=TimeInterval(start=4.0, end=10.0),  # overlaps with c1
                rank_score=70.0,
                confidence=0.8,
            ),
            HighlightCandidate(
                candidate_id="c3",
                interval=TimeInterval(start=10.0, end=16.0),  # touches boundary at 10.0
                rank_score=40.0,
                confidence=0.8,
            ),
        ]
        constraints = SelectionConstraints(target_duration_seconds=30.0)
        result = select_highlights_dp(candidates, constraints)

        # c2 (70.0) + c3 (40.0) = 110.0 is better than c1 (30.0) + c3 (40.0) = 70.0
        selected_ids = [c.candidate_id for c in result.selected_candidates]
        assert selected_ids == ["c2", "c3"]
        assert result.total_score == 110.0

        # Verify no pairwise overlap
        for i in range(len(result.selected_candidates) - 1):
            assert not result.selected_candidates[i].interval.overlaps(
                result.selected_candidates[i + 1].interval
            )

    def test_strict_budget_enforcement(self) -> None:
        candidates = [
            HighlightCandidate(
                candidate_id=f"c{i}",
                interval=TimeInterval(start=float(i * 10), end=float(i * 10 + 5)),
                rank_score=20.0,
                confidence=0.8,
            )
            for i in range(10)
        ]
        # Each clip is 5s, 10 clips total. Budget is 12s -> only 2 clips can fit (10s total).
        constraints = SelectionConstraints(
            target_duration_seconds=12.0,
            quantum_bin_seconds=0.5,
        )
        result = select_highlights_dp(candidates, constraints)

        assert len(result.selected_candidates) == 2
        assert result.total_duration_seconds <= 12.0
        assert result.total_score == 40.0

    def test_empty_candidates_input(self) -> None:
        constraints = SelectionConstraints(target_duration_seconds=60.0)
        result = select_highlights_dp([], constraints)
        assert result.selected_candidates == []
        assert result.total_score == 0.0
        assert result.total_duration_seconds == 0.0

    def test_all_candidates_exceed_budget(self) -> None:
        cand = HighlightCandidate(
            candidate_id="huge",
            interval=TimeInterval(start=0.0, end=100.0),
            rank_score=99.0,
            confidence=0.9,
        )
        constraints = SelectionConstraints(target_duration_seconds=50.0)
        result = select_highlights_dp([cand], constraints)
        assert result.selected_candidates == []
        assert result.discarded_count == 1

    def test_exhaustive_oracle_agreement(self) -> None:
        """Verifies DP solution matches the exact exhaustive search on small problem."""
        candidates = [
            HighlightCandidate(
                candidate_id="c1",
                interval=TimeInterval(start=2.0, end=8.0),
                rank_score=25.0,
                confidence=0.8,
            ),
            HighlightCandidate(
                candidate_id="c2",
                interval=TimeInterval(start=5.0, end=12.0),
                rank_score=45.0,
                confidence=0.8,
            ),
            HighlightCandidate(
                candidate_id="c3",
                interval=TimeInterval(start=11.0, end=18.0),
                rank_score=30.0,
                confidence=0.8,
            ),
            HighlightCandidate(
                candidate_id="c4",
                interval=TimeInterval(start=14.0, end=20.0),
                rank_score=35.0,
                confidence=0.8,
            ),
        ]
        constraints = SelectionConstraints(
            target_duration_seconds=15.0,
            quantum_bin_seconds=0.1,  # Fine quantum to match exact durations
        )

        dp_result = select_highlights_dp(candidates, constraints)
        oracle_subset = exhaustive_interval_selection(candidates, constraints)

        oracle_score = sum(c.rank_score for c in oracle_subset)
        assert pytest.approx(dp_result.total_score) == oracle_score
        assert [c.candidate_id for c in dp_result.selected_candidates] == [
            c.candidate_id for c in oracle_subset
        ]
