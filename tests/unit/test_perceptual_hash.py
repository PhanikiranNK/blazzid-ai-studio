"""Unit tests for 64-bit perceptual hash Hamming distance."""

import pytest

from blazzid_algorithms.perceptual_hash import (
    UINT64_MAX,
    UINT64_MIN,
    are_visually_similar,
    hamming_distance,
    validate_and_normalize_hash,
)


class TestPerceptualHash:
    def test_identical_hashes_zero_distance(self) -> None:
        assert hamming_distance(0, 0) == 0
        assert hamming_distance(UINT64_MAX, UINT64_MAX) == 0
        assert hamming_distance(1234567890123456789, 1234567890123456789) == 0

    def test_all_bits_different_distance_64(self) -> None:
        # 0 vs all 1s (2^64 - 1)
        assert hamming_distance(UINT64_MIN, UINT64_MAX) == 64
        # Alternating bits 0xAAAAAAAAAAAAAAAA vs 0x5555555555555555
        h1 = 0xAAAAAAAAAAAAAAAA
        h2 = 0x5555555555555555
        assert hamming_distance(h1, h2) == 64

    def test_single_bit_flip(self) -> None:
        base = 0x123456789ABCDEF0
        for bit in range(64):
            flipped = base ^ (1 << bit)
            assert hamming_distance(base, flipped) == 1

    def test_hex_string_inputs(self) -> None:
        h_int = 0x1122334455667788
        h_str = "1122334455667788"
        h_str_prefix = "0x1122334455667788"
        h_str_upper = "0X1122334455667788"

        assert hamming_distance(h_int, h_str) == 0
        assert hamming_distance(h_str, h_str_prefix) == 0
        assert hamming_distance(h_str_upper, h_int) == 0

    def test_raw_bytes_inputs(self) -> None:
        b1 = b"\x00\x00\x00\x00\x00\x00\x00\x01"  # 1
        b2 = b"\x00\x00\x00\x00\x00\x00\x00\x03"  # 3 (differs by 1 bit: bit 1)
        assert hamming_distance(b1, b2) == 1

    def test_visual_similarity_threshold(self) -> None:
        h1 = 0x0000000000000000
        # 4 bits flipped -> distance 4 <= default threshold 5
        h_similar = 0x000000000000000F
        # 6 bits flipped -> distance 6 > default threshold 5
        h_different = 0x000000000000003F

        assert are_visually_similar(h1, h_similar, threshold=5)
        assert not are_visually_similar(h1, h_different, threshold=5)

    def test_reject_out_of_bounds_integers(self) -> None:
        with pytest.raises(ValueError, match="out of range"):
            validate_and_normalize_hash(-1)
        with pytest.raises(ValueError, match="out of range"):
            validate_and_normalize_hash(UINT64_MAX + 1)

    def test_reject_invalid_hex_string(self) -> None:
        # Wrong length
        with pytest.raises(ValueError, match="must be exactly 16 hex characters"):
            validate_and_normalize_hash("12345")
        # Invalid hex characters
        with pytest.raises(ValueError, match="Invalid hexadecimal string"):
            validate_and_normalize_hash("0123456789ABCDEG")  # 'G' is invalid

    def test_reject_invalid_bytes_length(self) -> None:
        with pytest.raises(ValueError, match="must be exactly 8 bytes"):
            validate_and_normalize_hash(b"\x01\x02\x03")

    def test_reject_unsupported_types(self) -> None:
        with pytest.raises(TypeError, match="Hash must be int, 16-char hex str"):
            validate_and_normalize_hash(123.45)  # type: ignore[arg-type]
