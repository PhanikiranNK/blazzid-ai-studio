"""Hypothesis property-based tests for rolling feature statistics."""

import math

from hypothesis import given
from hypothesis import strategies as st

from blazzid_algorithms.rolling_statistics import (
    StreamingRollingStats,
    compute_rolling_stats,
)


@given(
    values=st.lists(
        st.floats(min_value=-1e4, max_value=1e4, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=100,
    ),
    window_size=st.integers(min_value=1, max_value=20),
)
def test_rolling_statistics_invariants(values: list[float], window_size: int) -> None:
    result = compute_rolling_stats(values, window_size=window_size)

    assert len(result.means) == len(values)
    assert len(result.variances) == len(values)
    assert len(result.stds) == len(values)
    assert len(result.z_scores) == len(values)

    for i in range(len(values)):
        w_start = max(0, i - window_size + 1)
        window_slice = values[w_start : i + 1]

        # Invariant 1: Mean is bounded by the min and max of current window
        min_w = min(window_slice)
        max_w = max(window_slice)
        assert min_w - 1e-4 <= result.means[i] <= max_w + 1e-4

        # Invariant 2: Variance and std are non-negative
        assert result.variances[i] >= 0.0
        assert result.stds[i] >= 0.0
        assert math.isclose(result.stds[i], math.sqrt(result.variances[i]), abs_tol=1e-5)

        # Invariant 3: Z-scores are finite
        assert not math.isnan(result.z_scores[i])
        assert not math.isinf(result.z_scores[i])


@given(
    values=st.lists(
        st.floats(min_value=0.0, max_value=500.0, allow_nan=False),
        min_size=1,
        max_size=50,
    ),
    window_size=st.integers(min_value=1, max_value=15),
)
def test_streaming_matches_batch_exactly(values: list[float], window_size: int) -> None:
    batch_res = compute_rolling_stats(values, window_size=window_size)

    stream = StreamingRollingStats(window_size=window_size)
    for i, x in enumerate(values):
        m, v, z = stream.update(x)
        assert math.isclose(m, batch_res.means[i], abs_tol=1e-5)
        assert math.isclose(v, batch_res.variances[i], abs_tol=1e-5)
        assert math.isclose(z, batch_res.z_scores[i], abs_tol=1e-5)
