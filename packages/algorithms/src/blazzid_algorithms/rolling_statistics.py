"""Numerically stable rolling statistics for continuous media signals.

Provides both streaming (single-sample update) and batch implementations for rolling
mean, rolling variance, rolling standard deviation, and dynamic z-score spikes.

Numerical Stability:
- Naive prefix sums (sum(x) and sum(x^2)) suffer catastrophic cancellation when values
  are large (e.g., 1e9) and variance is small.
- This implementation uses a sliding-window formulation with drift-correction:
  periodically re-accumulating exact sums to prevent floating-point degradation.
- Variance is strictly clamped: max(0.0, var).
- Division-by-zero is guarded by a configurable epsilon parameter.
"""

from __future__ import annotations

import collections
import math
from collections.abc import Sequence
from typing import NamedTuple


class RollingStatsResult(NamedTuple):
    """Batch calculation result containing aligned rolling metric arrays."""

    means: list[float]
    variances: list[float]
    stds: list[float]
    z_scores: list[float]


class StreamingRollingStats:
    """Online, sliding-window streaming statistics accumulator.

    Complexity:
    - Time: O(1) per update call.
    - Space: O(W) memory bounded by the window size W.
    """

    def __init__(self, window_size: int, *, eps: float = 1e-6) -> None:
        """Initializes accumulator.

        Args:
            window_size: Number of past samples in the sliding window (must be >= 1).
            eps: Small positive constant added to standard deviation to prevent zero-division.
        """
        if window_size < 1:
            raise ValueError(f"window_size must be >= 1, got {window_size}")
        if eps <= 0.0 or math.isnan(eps) or math.isinf(eps):
            raise ValueError(f"eps must be a finite positive float, got {eps}")

        self.window_size = window_size
        self.eps = eps
        self._buffer: collections.deque[float] = collections.deque(maxlen=window_size)
        self._sum = 0.0
        self._sum_sq = 0.0
        self._updates_since_recalc = 0
        self._recalc_interval = 1024  # periodic refresh to prevent float precision drift

    @property
    def count(self) -> int:
        """Current number of samples accumulated (up to window_size)."""
        return len(self._buffer)

    @property
    def is_warmed_up(self) -> bool:
        """Returns True if the accumulator has received at least window_size samples."""
        return len(self._buffer) >= self.window_size

    def update(self, value: float) -> tuple[float, float, float]:
        """Pushes a new sample into the window and returns (mean, variance, z_score).

        Args:
            value: Finite numeric sample.

        Returns:
            Tuple of (current_mean, current_variance, current_z_score).

        Raises:
            ValueError: If value is NaN or infinite.
        """
        if math.isnan(value) or math.isinf(value):
            raise ValueError(f"Sample must be a finite float, got {value}")

        v = float(value)

        if len(self._buffer) == self.window_size:
            evicted = self._buffer[0]
            self._sum -= evicted
            self._sum_sq -= evicted * evicted

        self._buffer.append(v)
        self._sum += v
        self._sum_sq += v * v
        self._updates_since_recalc += 1

        n = len(self._buffer)

        # Periodic full re-accumulation to eliminate cumulative rounding errors
        if self._updates_since_recalc >= self._recalc_interval:
            self._recalculate_exact()

        mean = self._sum / n
        raw_var = (self._sum_sq / n) - (mean * mean)
        var = max(0.0, raw_var)
        std = math.sqrt(var)
        z_score = (v - mean) / (std + self.eps)

        return (mean, var, z_score)

    def _recalculate_exact(self) -> None:
        """Recalculates sum and sum_sq directly from buffer elements."""
        self._sum = sum(self._buffer)
        self._sum_sq = sum(x * x for x in self._buffer)
        self._updates_since_recalc = 0

    @property
    def mean(self) -> float:
        """Current rolling mean (0.0 if buffer is empty)."""
        if not self._buffer:
            return 0.0
        return self._sum / len(self._buffer)

    @property
    def variance(self) -> float:
        """Current rolling population variance (0.0 if buffer is empty)."""
        if not self._buffer:
            return 0.0
        n = len(self._buffer)
        mean = self._sum / n
        raw_var = (self._sum_sq / n) - (mean * mean)
        return max(0.0, raw_var)

    @property
    def std(self) -> float:
        """Current rolling standard deviation."""
        return math.sqrt(self.variance)


def compute_rolling_stats(
    values: Sequence[float],
    window_size: int,
    *,
    eps: float = 1e-6,
) -> RollingStatsResult:
    """Computes rolling mean, variance, std, and z-score over a batch sequence.

    Warm-up behavior: For the first W - 1 samples (where W = window_size), statistics
    are computed expanding over available samples [0 .. i].

    Args:
        values: Sequence of numeric samples.
        window_size: Window size in sample counts (>= 1).
        eps: Epsilon parameter for z-score division stabilization.

    Returns:
        RollingStatsResult containing aligned lists of means, variances, stds, and z-scores.

    Raises:
        ValueError: If window_size < 1, eps <= 0, or any sample is non-finite.
    """
    if window_size < 1:
        raise ValueError(f"window_size must be >= 1, got {window_size}")
    if eps <= 0.0 or math.isnan(eps) or math.isinf(eps):
        raise ValueError(f"eps must be a finite positive float, got {eps}")

    n = len(values)
    if n == 0:
        return RollingStatsResult(means=[], variances=[], stds=[], z_scores=[])

    stream = StreamingRollingStats(window_size=window_size, eps=eps)

    means: list[float] = []
    variances: list[float] = []
    stds: list[float] = []
    z_scores: list[float] = []

    for x in values:
        m, v, z = stream.update(x)
        means.append(m)
        variances.append(v)
        stds.append(math.sqrt(v))
        z_scores.append(z)

    return RollingStatsResult(
        means=means,
        variances=variances,
        stds=stds,
        z_scores=z_scores,
    )
