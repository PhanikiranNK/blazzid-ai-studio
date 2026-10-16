"""Unit tests for rolling statistics and z-score computation."""

import math

import pytest

from blazzid_algorithms.rolling_statistics import (
    StreamingRollingStats,
    compute_rolling_stats,
)


class TestRollingStatistics:
    def test_streaming_basic_accumulation(self) -> None:
        stats = StreamingRollingStats(window_size=3)
        assert not stats.is_warmed_up
        assert stats.mean == 0.0

        # Sample 1
        m, v, z = stats.update(10.0)
        assert m == 10.0
        assert v == 0.0
        assert stats.count == 1
        assert not stats.is_warmed_up

        # Sample 2
        m, v, z = stats.update(20.0)
        assert m == 15.0
        assert (
            pytest.approx(v) == 25.0
        )  # population variance of [10, 20]: ((10-15)^2 + (20-15)^2)/2 = 25
        assert stats.count == 2
        assert not stats.is_warmed_up

        # Sample 3 (now warmed up)
        m, v, z = stats.update(30.0)
        assert m == 20.0
        assert pytest.approx(v) == 66.6666667
        assert stats.count == 3
        assert stats.is_warmed_up

        # Sample 4 (evicts 10.0, window contains [20, 30, 40])
        m, v, z = stats.update(40.0)
        assert m == 30.0
        assert pytest.approx(v) == 66.6666667
        assert stats.count == 3

    def test_constant_series_zero_variance(self) -> None:
        stats = StreamingRollingStats(window_size=5, eps=1e-5)
        for _ in range(10):
            m, v, z = stats.update(42.0)
            assert m == 42.0
            assert v == 0.0
            assert pytest.approx(z) == 0.0

    def test_catastrophic_cancellation_high_magnitude(self) -> None:
        """Tests that large baselines (1e9) with small variations don't produce negative variance."""
        base = 1_000_000_000.0
        values = [base + 1.0, base + 2.0, base + 3.0, base + 2.0, base + 1.0]
        stats = StreamingRollingStats(window_size=3)

        for x in values:
            m, v, z = stats.update(x)
            assert not math.isnan(m)
            assert not math.isnan(v)
            assert v >= 0.0  # Must never be negative!
            assert not math.isnan(z)

    def test_batch_matches_streaming(self) -> None:
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        window = 4
        batch_res = compute_rolling_stats(values, window_size=window)

        stream = StreamingRollingStats(window_size=window)
        for i, val in enumerate(values):
            m, v, z = stream.update(val)
            assert pytest.approx(batch_res.means[i]) == m
            assert pytest.approx(batch_res.variances[i]) == v
            assert pytest.approx(batch_res.z_scores[i]) == z

    def test_empty_batch(self) -> None:
        res = compute_rolling_stats([], window_size=5)
        assert res.means == []
        assert res.variances == []
        assert res.z_scores == []

    def test_reject_invalid_window_or_eps(self) -> None:
        with pytest.raises(ValueError, match="window_size must be >= 1"):
            StreamingRollingStats(window_size=0)
        with pytest.raises(ValueError, match="eps must be a finite positive float"):
            StreamingRollingStats(window_size=5, eps=0.0)

    def test_reject_nan_samples(self) -> None:
        stats = StreamingRollingStats(window_size=3)
        with pytest.raises(ValueError, match="must be a finite float"):
            stats.update(float("nan"))
        with pytest.raises(ValueError, match="must be a finite float"):
            stats.update(float("inf"))
