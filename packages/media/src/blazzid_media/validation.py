"""Media input validation and safe filesystem path handling.

Enforces least-privilege path traversal protection, size constraints, and file integrity checks.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from blazzid_media.errors import MediaInputError

# Default file size boundaries: 1 KB minimum, 25 GB maximum
DEFAULT_MIN_FILE_SIZE_BYTES: int = 1024
DEFAULT_MAX_FILE_SIZE_BYTES: int = 25 * 1024 * 1024 * 1024  # 25 GiB


def validate_input_media_file(
    file_path: Path | str,
    *,
    min_size_bytes: int = DEFAULT_MIN_FILE_SIZE_BYTES,
    max_size_bytes: int = DEFAULT_MAX_FILE_SIZE_BYTES,
    allow_symlinks: bool = True,
) -> Path:
    """Validates that an input media file exists, is readable, and satisfies size bounds.

    Args:
        file_path: Path to the target media file.
        min_size_bytes: Minimum permissible file size (default 1024 bytes).
        max_size_bytes: Maximum permissible file size (default 25 GB).
        allow_symlinks: Whether to resolve and accept symlinks to regular files.

    Returns:
        Resolved absolute Path object.

    Raises:
        MediaInputError: If file is missing, a directory, unreadable, or outside size limits.
    """
    path = Path(file_path)

    # 1. Existence check
    if not path.exists():
        raise MediaInputError(f"Input media file does not exist: '{path.name}'")

    # 2. Symlink policy
    if path.is_symlink() and not allow_symlinks:
        raise MediaInputError(f"Symlinks are disallowed by policy: '{path.name}'")

    resolved = path.resolve()

    # 3. Regular file check (reject directories, character devices, FIFOs, etc.)
    if not resolved.is_file():
        raise MediaInputError(f"Input path is not a regular file: '{path.name}'")

    # 4. Read permission check
    if not os.access(resolved, os.R_OK):
        raise MediaInputError(
            f"Input media file is not readable (permission denied): '{path.name}'"
        )

    # 5. File size checks
    try:
        size = resolved.stat().st_size
    except OSError as err:
        raise MediaInputError(f"Failed to inspect file size: {err}") from err

    if size == 0:
        raise MediaInputError(f"Input media file is empty (0 bytes): '{path.name}'")

    if size < min_size_bytes:
        raise MediaInputError(
            f"Input file size ({size} bytes) is below minimum threshold ({min_size_bytes} bytes): '{path.name}'"
        )

    if size > max_size_bytes:
        raise MediaInputError(
            f"Input file size ({size} bytes) exceeds maximum threshold ({max_size_bytes} bytes): '{path.name}'"
        )

    return resolved


def ensure_safe_directory(
    dir_path: Path | str,
    *,
    create: bool = True,
    base_dir: Optional[Path | str] = None,
) -> Path:
    """Validates and optionally creates a directory, guarding against path traversal.

    Args:
        dir_path: Target directory path.
        create: If True, creates directory tree if not present.
        base_dir: If specified, enforces that dir_path resolves within base_dir.

    Returns:
        Resolved absolute Path to directory.

    Raises:
        MediaInputError: If directory escapes base_dir or cannot be created.
    """
    path = Path(dir_path).resolve()

    if base_dir is not None:
        base = Path(base_dir).resolve()
        try:
            path.relative_to(base)
        except ValueError as err:
            raise MediaInputError(
                f"Path traversal detected: target directory '{path.name}' escapes base '{base.name}'"
            ) from err

    if create:
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as err:
            raise MediaInputError(f"Failed to create directory '{path.name}': {err}") from err

    if not path.is_dir():
        raise MediaInputError(f"Path is not a directory: '{path.name}'")

    if not os.access(path, os.W_OK):
        raise MediaInputError(f"Directory is not writable: '{path.name}'")

    return path
