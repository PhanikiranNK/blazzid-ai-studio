"""Unit tests for media input validation and safe filesystem operations."""

from __future__ import annotations

from pathlib import Path

import pytest

from blazzid_media.errors import MediaInputError
from blazzid_media.validation import (
    ensure_safe_directory,
    validate_input_media_file,
)


def test_validate_missing_file(tmp_path: Path) -> None:
    """Missing file must raise MediaInputError."""
    missing = tmp_path / "nonexistent.mp4"
    with pytest.raises(MediaInputError, match="does not exist"):
        validate_input_media_file(missing)


def test_validate_directory_input(tmp_path: Path) -> None:
    """Directory passed as file must raise MediaInputError."""
    dir_path = tmp_path / "somedir"
    dir_path.mkdir()
    with pytest.raises(MediaInputError, match="not a regular file"):
        validate_input_media_file(dir_path)


def test_validate_empty_file(tmp_path: Path) -> None:
    """Zero-byte file must raise MediaInputError."""
    empty_file = tmp_path / "empty.mp4"
    empty_file.touch()
    with pytest.raises(MediaInputError, match="empty"):
        validate_input_media_file(empty_file)


def test_validate_file_below_min_size(tmp_path: Path) -> None:
    """File smaller than min_size_bytes must be rejected."""
    small = tmp_path / "small.mp4"
    small.write_bytes(b"x" * 100)
    with pytest.raises(MediaInputError, match="below minimum threshold"):
        validate_input_media_file(small, min_size_bytes=500)


def test_validate_file_above_max_size(tmp_path: Path) -> None:
    """File larger than max_size_bytes must be rejected."""
    big = tmp_path / "big.mp4"
    big.write_bytes(b"x" * 2000)
    with pytest.raises(MediaInputError, match="exceeds maximum threshold"):
        validate_input_media_file(big, min_size_bytes=10, max_size_bytes=1000)


def test_validate_valid_file(tmp_path: Path) -> None:
    """Valid regular file within size bounds must succeed and return resolved path."""
    valid = tmp_path / "valid.mp4"
    valid.write_bytes(b"0" * 2048)
    res = validate_input_media_file(valid)
    assert res == valid.resolve()
    assert res.is_file()


def test_symlink_rejection_policy(tmp_path: Path) -> None:
    """Symlinks must be rejected when allow_symlinks=False."""
    target = tmp_path / "real.mp4"
    target.write_bytes(b"1" * 2048)
    symlink = tmp_path / "link.mp4"
    symlink.symlink_to(target)

    # Allowed by default
    res = validate_input_media_file(symlink, allow_symlinks=True)
    assert res == target.resolve()

    # Rejected when disallowed
    with pytest.raises(MediaInputError, match="Symlinks are disallowed"):
        validate_input_media_file(symlink, allow_symlinks=False)


def test_ensure_safe_directory_creation(tmp_path: Path) -> None:
    """ensure_safe_directory creates directory and returns resolved path."""
    new_dir = tmp_path / "nested" / "output_dir"
    res = ensure_safe_directory(new_dir)
    assert res.exists()
    assert res.is_dir()
    assert res == new_dir.resolve()


def test_ensure_safe_directory_rejects_file(tmp_path: Path) -> None:
    """ensure_safe_directory raises MediaInputError if target exists as a file."""
    file_path = tmp_path / "some_file.txt"
    file_path.touch()
    with pytest.raises(MediaInputError, match="Failed to create directory|not a directory"):
        ensure_safe_directory(file_path)
