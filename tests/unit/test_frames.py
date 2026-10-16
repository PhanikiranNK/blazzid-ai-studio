"""Unit tests for sparse timestamp-aware frame extraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from blazzid_media.errors import FrameExtractionError
from blazzid_media.frames import extract_sparse_frames
from tests.fixtures.synthetic_media import (
    generate_synthetic_video,
    is_ffmpeg_available,
)

pytestmark = pytest.mark.skipif(not is_ffmpeg_available(), reason="FFmpeg not available on PATH")


def test_extract_sparse_frames_basic(tmp_path: Path) -> None:
    """Sparse extraction at 1.0s interval from a 3.0s video yields ~3 frames."""
    video = generate_synthetic_video(
        duration_seconds=3.0,
        width=320,
        height=240,
        fps=30,
        output_path=tmp_path / "test_3s.mp4",
    )
    frames_dir = tmp_path / "frames"

    res = extract_sparse_frames(video, frames_dir, target_interval_seconds=1.0)
    assert res.total_frames_extracted >= 2
    assert len(res.frames) == res.total_frames_extracted

    # Check timestamps are strictly increasing and within [0, 3.0]
    last_pts = -1.0
    for frame in res.frames:
        assert frame.timestamp_seconds > last_pts
        assert 0.0 <= frame.timestamp_seconds <= 3.5
        assert frame.file_path.exists()
        assert frame.file_path.stat().st_size > 0
        assert frame.file_path.name.startswith("frame_")
        assert frame.width == 320
        assert frame.height == 240
        last_pts = frame.timestamp_seconds


def test_extract_sparse_frames_max_frames_limit(tmp_path: Path) -> None:
    """extract_sparse_frames respects max_frames limit."""
    video = generate_synthetic_video(
        duration_seconds=5.0,
        width=320,
        height=240,
        fps=30,
        output_path=tmp_path / "test_5s.mp4",
    )
    frames_dir = tmp_path / "frames_limited"

    res = extract_sparse_frames(video, frames_dir, target_interval_seconds=0.5, max_frames=3)
    assert res.total_frames_extracted == 3
    assert len(res.frames) == 3


def test_extract_sparse_frames_invalid_interval(tmp_path: Path) -> None:
    """Negative or zero interval raises FrameExtractionError."""
    video = generate_synthetic_video(duration_seconds=1.0, output_path=tmp_path / "test.mp4")
    frames_dir = tmp_path / "frames_err"

    with pytest.raises(FrameExtractionError, match="positive finite float"):
        extract_sparse_frames(video, frames_dir, target_interval_seconds=0.0)


def test_extract_sparse_frames_invalid_video_file(tmp_path: Path) -> None:
    """Non-existent video file raises FrameExtractionError."""
    frames_dir = tmp_path / "frames"
    with pytest.raises(FrameExtractionError):
        extract_sparse_frames(tmp_path / "nonexistent.mp4", frames_dir)
