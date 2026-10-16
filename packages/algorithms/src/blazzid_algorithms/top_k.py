"""Top-K candidate selection algorithm using a bounded min-heap.

Complexity:
- Time: O(M log K) worst-case, O(M + K log K) average, where M is the number
  of streamed items and K is the requested capacity.
- Space: O(K) auxiliary memory. Does not materialize the full stream in memory.
"""

from __future__ import annotations

import heapq
import math
from collections.abc import Iterable
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def _default_score_extractor(item: Any) -> float:
    """Extracts score from objects with a 'rank_score' attribute, or treats item as float."""
    if hasattr(item, "rank_score"):
        return float(item.rank_score)
    if isinstance(item, (int, float)):
        return float(item)
    raise TypeError(
        f"Item of type {type(item).__name__} does not have 'rank_score'. "
        "A custom 'key' callable must be provided."
    )


def _default_tie_breaker(item: Any) -> tuple[Any, ...]:
    """Default secondary tie-breaker extracting (confidence, -start, id) if available."""
    conf = getattr(item, "confidence", 0.0)
    start = 0.0
    if hasattr(item, "interval"):
        start = -getattr(item.interval, "start", 0.0)
    item_id = getattr(item, "candidate_id", getattr(item, "id", ""))
    return (conf, start, str(item_id))


def select_top_k(
    stream: Iterable[T],
    k: int,
    *,
    key: Callable[[T], float] | None = None,
    tie_breaker: Callable[[T], Any] | None = None,
) -> list[T]:
    """Selects the top K items from a stream in descending order of utility.

    Args:
        stream: Iterable of items. Streamed lazily without full materialization.
        k: Maximum number of items to retain. Must be >= 0.
        key: Function to extract numeric score from an item. Defaults to extracting
            item.rank_score or casting numeric types.
        tie_breaker: Function returning a comparable secondary key for items with equal
            scores. Higher tie-breaker values are prioritized over lower ones.

    Returns:
        A list of up to K items sorted in descending order of score (and tie-breaker).

    Raises:
        ValueError: If k < 0 or an item has a NaN/infinite score.
    """
    if k < 0:
        raise ValueError(f"k must be non-negative, got {k}")
    if k == 0:
        return []

    score_fn = key or _default_score_extractor
    tie_fn = tie_breaker or _default_tie_breaker

    # Heap contains tuples: (score, tie_key, seq, item)
    # Python heapq is a min-heap, so the smallest element is at index 0.
    heap: list[tuple[float, Any, int, T]] = []

    for seq, item in enumerate(stream):
        raw_score = score_fn(item)
        if math.isnan(raw_score) or math.isinf(raw_score):
            raise ValueError(f"Item score must be a finite float, got {raw_score}")
        score = float(raw_score)
        tie_key = tie_fn(item)

        entry = (score, tie_key, seq, item)

        if len(heap) < k:
            heapq.heappush(heap, entry)
        else:
            # Compare against current minimum in the top-K heap
            min_score, min_tie, _, _ = heap[0]
            if (score, tie_key) > (min_score, min_tie):
                heapq.heapreplace(heap, entry)

    # Extract all elements from heap and sort descending
    # Sorting at most K elements takes O(K log K)
    heap.sort(key=lambda e: (e[0], e[1]), reverse=True)
    return [entry[3] for entry in heap]
