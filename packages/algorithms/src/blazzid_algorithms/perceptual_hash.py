"""64-bit perceptual hash Hamming distance primitive.

Computes exact Hamming distance between two 64-bit perceptual hashes (e.g., dHash, pHash)
using bitwise XOR and population count.

Complexity:
- Time: O(1) single-cycle bitwise operation.
- Space: O(1) auxiliary space.
"""

from __future__ import annotations

from typing import Union

# Maximum unsigned 64-bit integer
UINT64_MAX: int = (1 << 64) - 1
UINT64_MIN: int = 0

HashLike = Union[int, str, bytes, bytearray]


def validate_and_normalize_hash(h: HashLike) -> int:
    """Validates and normalizes a hash representation into an unsigned 64-bit integer.

    Accepted input types:
    - int: Must satisfy 0 <= h <= 2^64 - 1.
    - str: Exactly 16 hex characters (optional '0x' or '0X' prefix allowed).
    - bytes / bytearray: Exactly 8 bytes in big-endian or native order.

    Returns:
        int: Unsigned 64-bit integer in [0, 2^64 - 1].

    Raises:
        TypeError: If h is not int, str, bytes, or bytearray.
        ValueError: If value is out of bounds, wrong length, or contains invalid hex characters.
    """
    if isinstance(h, int):
        if h < UINT64_MIN or h > UINT64_MAX:
            raise ValueError(
                f"64-bit hash integer out of range: must be between {UINT64_MIN} and "
                f"{UINT64_MAX}, got {h}"
            )
        return h

    if isinstance(h, str):
        clean_hex = h.strip()
        if clean_hex.startswith(("0x", "0X")):
            clean_hex = clean_hex[2:]
        if len(clean_hex) != 16:
            raise ValueError(
                f"Hexadecimal hash string must be exactly 16 hex characters (64 bits), "
                f"got length {len(clean_hex)} ('{h}')"
            )
        try:
            val = int(clean_hex, 16)
        except ValueError as err:
            raise ValueError(f"Invalid hexadecimal string: '{h}'") from err
        return val

    if isinstance(h, (bytes, bytearray)):
        if len(h) != 8:
            raise ValueError(
                f"Raw hash bytes must be exactly 8 bytes (64 bits), got length {len(h)}"
            )
        return int.from_bytes(h, byteorder="big", signed=False)

    raise TypeError(
        f"Hash must be int, 16-char hex str, or 8-byte bytes/bytearray, got {type(h).__name__}"
    )


def hamming_distance(h1: HashLike, h2: HashLike) -> int:
    """Computes the Hamming distance (number of differing bits) between two 64-bit hashes.

    Formula: popcount(h1 ^ h2)

    Properties:
    1. Identity: hamming_distance(x, x) == 0
    2. Non-negativity: 0 <= hamming_distance(x, y) <= 64
    3. Symmetry: hamming_distance(x, y) == hamming_distance(y, x)
    4. Triangle Inequality: hamming_distance(x, z) <= hamming_distance(x, y) + hamming_distance(y, z)

    Args:
        h1: First hash (int, hex str, or 8 bytes).
        h2: Second hash (int, hex str, or 8 bytes).

    Returns:
        Integer bit distance in [0, 64].
    """
    val1 = validate_and_normalize_hash(h1)
    val2 = validate_and_normalize_hash(h2)

    xor_diff = val1 ^ val2

    # In Python 3.10+, int.bit_count() provides native hardware popcount
    bit_count_fn = getattr(xor_diff, "bit_count", None)
    if bit_count_fn is not None:
        return int(bit_count_fn())

    # Portable fallback for Python 3.9
    return bin(xor_diff).count("1")


def are_visually_similar(h1: HashLike, h2: HashLike, threshold: int = 5) -> bool:
    """Determines whether two frame perceptual hashes are visually near-identical.

    Args:
        h1: First hash.
        h2: Second hash.
        threshold: Maximum allowable Hamming distance (default 5 bits out of 64).

    Returns:
        True if Hamming distance <= threshold, False otherwise.
    """
    if threshold < 0 or threshold > 64:
        raise ValueError(f"threshold must be in [0, 64], got {threshold}")
    return hamming_distance(h1, h2) <= threshold
