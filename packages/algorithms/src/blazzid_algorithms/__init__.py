"""BLAZZID pure algorithms package."""

from blazzid_algorithms.interval_selection import (
    exhaustive_interval_selection,
    select_highlights_dp,
)
from blazzid_algorithms.perceptual_hash import (
    UINT64_MAX,
    UINT64_MIN,
    are_visually_similar,
    hamming_distance,
    validate_and_normalize_hash,
)
from blazzid_algorithms.rolling_statistics import (
    RollingStatsResult,
    StreamingRollingStats,
    compute_rolling_stats,
)
from blazzid_algorithms.top_k import select_top_k

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "select_top_k",
    "select_highlights_dp",
    "exhaustive_interval_selection",
    "StreamingRollingStats",
    "compute_rolling_stats",
    "RollingStatsResult",
    "hamming_distance",
    "are_visually_similar",
    "validate_and_normalize_hash",
    "UINT64_MIN",
    "UINT64_MAX",
]
