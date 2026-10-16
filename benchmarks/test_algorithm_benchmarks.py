"""Repeatable performance benchmarks for BLAZZID pure algorithms.

These benchmarks provide empirical measurement of algorithm execution times on host hardware.
"""

import random
from typing import Any

from blazzid_algorithms.interval_selection import select_highlights_dp
from blazzid_algorithms.perceptual_hash import UINT64_MAX, hamming_distance
from blazzid_algorithms.rolling_statistics import compute_rolling_stats
from blazzid_algorithms.top_k import select_top_k
from blazzid_core.contracts import HighlightCandidate, SelectionConstraints, TimeInterval


def test_benchmark_top_k(benchmark: Any) -> None:
    """Measures Top-K min-heap selection on 10,000 streaming candidates with K=50."""
    rng = random.Random(42)
    stream_data = [rng.uniform(0.0, 100.0) for _ in range(10_000)]

    def run_top_k() -> list[float]:
        return select_top_k(stream_data, k=50)

    result = benchmark(run_top_k)
    assert len(result) == 50


def test_benchmark_interval_selection_dp(benchmark: Any) -> None:
    """Measures Weighted Interval Scheduling DP on 100 candidates with 360 budget bins."""
    rng = random.Random(42)
    candidates: list[HighlightCandidate] = []
    current_time = 0.0

    for i in range(100):
        start = current_time + rng.uniform(0.0, 5.0)
        dur = rng.uniform(4.0, 18.0)
        candidates.append(
            HighlightCandidate(
                candidate_id=f"bench-{i}",
                interval=TimeInterval(start=start, end=start + dur),
                rank_score=rng.uniform(10.0, 100.0),
                confidence=rng.uniform(0.5, 0.99),
            )
        )
        current_time = start + dur * 0.4  # generate controlled overlapping intervals

    constraints = SelectionConstraints(
        target_duration_seconds=180.0,
        min_clip_duration_seconds=3.0,
        quantum_bin_seconds=0.5,  # 360 capacity bins
    )

    def run_dp() -> int:
        res = select_highlights_dp(candidates, constraints)
        return len(res.selected_candidates)

    count = benchmark(run_dp)
    assert count > 0


def test_benchmark_rolling_statistics(benchmark: Any) -> None:
    """Measures rolling statistics throughput across 50,000 float samples."""
    rng = random.Random(42)
    signal = [rng.gauss(0.0, 1.0) for _ in range(50_000)]

    def run_stats() -> int:
        res = compute_rolling_stats(signal, window_size=100)
        return len(res.means)

    count = benchmark(run_stats)
    assert count == 50_000


def test_benchmark_hamming_distance(benchmark: Any) -> None:
    """Measures 64-bit Hamming distance throughput on 10,000 hash comparisons."""
    rng = random.Random(42)
    pairs = [(rng.randint(0, UINT64_MAX), rng.randint(0, UINT64_MAX)) for _ in range(10_000)]

    def run_hamming() -> int:
        total = 0
        for h1, h2 in pairs:
            total += hamming_distance(h1, h2)
        return total

    total_dist = benchmark(run_hamming)
    assert total_dist > 0
