"""Hypothesis property-based tests for 64-bit perceptual hash Hamming distance."""

from hypothesis import given
from hypothesis import strategies as st

from blazzid_algorithms.perceptual_hash import UINT64_MAX, UINT64_MIN, hamming_distance

hash_strategy = st.integers(min_value=UINT64_MIN, max_value=UINT64_MAX)


@given(x=hash_strategy)
def test_hamming_distance_identity(x: int) -> None:
    # d(x, x) == 0
    assert hamming_distance(x, x) == 0


@given(x=hash_strategy, y=hash_strategy)
def test_hamming_distance_range_and_symmetry(x: int, y: int) -> None:
    d_xy = hamming_distance(x, y)
    d_yx = hamming_distance(y, x)

    # Invariant 1: Range is bounded in [0, 64]
    assert 0 <= d_xy <= 64

    # Invariant 2: Symmetry d(x, y) == d(y, x)
    assert d_xy == d_yx


@given(x=hash_strategy, y=hash_strategy, z=hash_strategy)
def test_hamming_distance_triangle_inequality(x: int, y: int, z: int) -> None:
    # d(x, z) <= d(x, y) + d(y, z)
    d_xz = hamming_distance(x, z)
    d_xy = hamming_distance(x, y)
    d_yz = hamming_distance(y, z)

    assert d_xz <= d_xy + d_yz
