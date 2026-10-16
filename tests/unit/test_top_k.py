"""Unit tests for Top-K candidate selection algorithm."""

import pytest

from blazzid_algorithms.top_k import select_top_k
from blazzid_core.contracts import HighlightCandidate, TimeInterval


class TestTopKSelection:
    def test_basic_selection(self) -> None:
        numbers = [10.0, 50.0, 20.0, 90.0, 40.0, 80.0, 30.0]
        result = select_top_k(numbers, k=3)
        assert result == [90.0, 80.0, 50.0]

    def test_streaming_generator_input(self) -> None:
        # Verify algorithm works on lazy generators without len()
        gen = (float(i) for i in range(100))
        result = select_top_k(gen, k=4)
        assert result == [99.0, 98.0, 97.0, 96.0]

    def test_empty_input(self) -> None:
        assert select_top_k([], k=5) == []

    def test_k_equals_zero(self) -> None:
        assert select_top_k([1.0, 2.0, 3.0], k=0) == []

    def test_k_negative(self) -> None:
        with pytest.raises(ValueError, match="k must be non-negative"):
            select_top_k([1.0, 2.0], k=-1)

    def test_k_greater_than_input_size(self) -> None:
        items = [15.0, 5.0, 25.0]
        result = select_top_k(items, k=10)
        assert result == [25.0, 15.0, 5.0]

    def test_duplicate_scores_stability(self) -> None:
        items = [10.0, 20.0, 20.0, 15.0, 20.0]
        result = select_top_k(items, k=4)
        assert result == [20.0, 20.0, 20.0, 15.0]

    def test_negative_scores(self) -> None:
        items = [-50.0, -10.0, -30.0, -5.0, -20.0]
        result = select_top_k(items, k=3)
        assert result == [-5.0, -10.0, -20.0]

    def test_nan_score_rejection(self) -> None:
        with pytest.raises(ValueError, match="finite float"):
            select_top_k([10.0, float("nan"), 20.0], k=2)

    def test_inf_score_rejection(self) -> None:
        with pytest.raises(ValueError, match="finite float"):
            select_top_k([10.0, float("inf"), 20.0], k=2)

    def test_candidate_objects_with_custom_tie_breaker(self) -> None:
        c1 = HighlightCandidate(
            candidate_id="c1",
            interval=TimeInterval(start=0.0, end=10.0),
            rank_score=90.0,
            confidence=0.85,
        )
        c2 = HighlightCandidate(
            candidate_id="c2",
            interval=TimeInterval(start=10.0, end=20.0),
            rank_score=90.0,
            confidence=0.95,  # higher confidence should break tie
        )
        c3 = HighlightCandidate(
            candidate_id="c3",
            interval=TimeInterval(start=20.0, end=30.0),
            rank_score=95.0,
            confidence=0.70,
        )

        result = select_top_k([c1, c2, c3], k=2)
        assert len(result) == 2
        assert result[0].candidate_id == "c3"  # rank 95
        assert result[1].candidate_id == "c2"  # rank 90 with higher confidence 0.95
