"""Hypothesis property-based tests for Top-K candidate selection."""

from hypothesis import given
from hypothesis import strategies as st

from blazzid_algorithms.top_k import select_top_k


@given(
    items=st.lists(
        st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False),
        min_size=0,
        max_size=100,
    ),
    k=st.integers(min_value=0, max_value=150),
)
def test_top_k_invariants(items: list[float], k: int) -> None:
    result = select_top_k(items, k=k)

    # Invariant 1: Result length is at most k and at most len(items)
    expected_len = min(k, len(items))
    assert len(result) == expected_len

    # Invariant 2: Sorted in descending order
    for i in range(len(result) - 1):
        assert result[i] >= result[i + 1]

    # Invariant 3: Result elements are drawn from input items (multiset subset)
    remaining_items = list(items)
    for x in result:
        assert x in remaining_items
        remaining_items.remove(x)

    # Invariant 4: If k >= len(items), result is a full descending sort of items
    if k >= len(items):
        assert result == sorted(items, reverse=True)


@given(
    items=st.lists(
        st.floats(min_value=0.0, max_value=100.0, allow_nan=False),
        min_size=1,
        max_size=50,
    ),
    k=st.integers(min_value=1, max_value=30),
)
def test_top_k_determinism(items: list[float], k: int) -> None:
    res1 = select_top_k(items, k=k)
    res2 = select_top_k(items, k=k)
    assert res1 == res2
