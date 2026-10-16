"""Unit tests for ffprobe metadata inspection and frame rate classification."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from blazzid_media.errors import MissingVideoStreamError, ProbeError
from blazzid_media.models import FrameRateMode
from blazzid_media.probe import _find_ffprobe_executable, probe_media
from tests.fixtures.synthetic_media import (
    generate_corrupt_media,
    generate_synthetic_audio,
    generate_synthetic_video,
    generate_vfr_video,
    is_ffmpeg_available,
)

pytestmark = pytest.mark.skipif(
    not is_ffmpeg_available(), reason="FFmpeg/ffprobe not available on PATH"
)


def test_probe_valid_video_with_audio(tmp_path: Path) -> None:
    """Probing a valid video with audio extracts container, video, and audio metadata."""
    video_path = generate_synthetic_video(
        duration_seconds=1.5,
        width=320,
        height=240,
        fps=30,
        has_audio=True,
        output_path=tmp_path / "valid_av.mp4",
    )

    meta = probe_media(video_path)
    assert meta.source_path == video_path.resolve()
    assert meta.container.format_name.startswith("mov,mp4") or "mp4" in meta.container.format_name
    assert meta.container.duration_seconds is not None
    assert meta.container.duration_seconds >= 1.0

    # Video stream assertions
    assert meta.video.width == 320
    assert meta.video.height == 240
    assert meta.video.codec_name == "h264"
    assert meta.video.avg_frame_rate is not None
    assert pytest.approx(meta.video.avg_frame_rate, rel=0.1) == 30.0
    assert meta.video.frame_rate_mode in (FrameRateMode.CFR, FrameRateMode.UNKNOWN)

    # Audio stream assertions
    assert meta.has_audio is True
    assert meta.audio is not None
    assert meta.audio.codec_name == "aac"
    assert meta.audio.channels >= 1


def test_probe_video_without_audio(tmp_path: Path) -> None:
    """Probing a video without audio succeeds with has_audio=False and audio=None."""
    video_path = generate_synthetic_video(
        duration_seconds=1.0,
        width=320,
        height=240,
        fps=30,
        has_audio=False,
        output_path=tmp_path / "video_no_audio.mp4",
    )

    meta = probe_media(video_path)
    assert meta.has_audio is False
    assert meta.audio is None
    assert meta.video.width == 320
    assert meta.video.height == 240


def test_probe_audio_only_raises_missing_video_stream(tmp_path: Path) -> None:
    """Probing an audio-only file raises MissingVideoStreamError."""
    audio_path = generate_synthetic_audio(
        duration_seconds=1.0,
        output_path=tmp_path / "audio_only.wav",
    )

    with pytest.raises(MissingVideoStreamError, match="No video stream found"):
        probe_media(audio_path)


def test_probe_corrupt_media_raises_probe_error(tmp_path: Path) -> None:
    """Probing a corrupt or invalid media file raises ProbeError."""
    corrupt_path = generate_corrupt_media(tmp_path / "corrupt.mp4")

    with pytest.raises(ProbeError):
        probe_media(corrupt_path)


def test_probe_vfr_video_classification(tmp_path: Path) -> None:
    """VFR video with jittered timestamps is classified as VFR."""
    vfr_path = generate_vfr_video(
        duration_seconds=3.0,
        width=320,
        height=240,
        output_path=tmp_path / "vfr_test.mp4",
    )

    meta = probe_media(vfr_path)
    assert meta.video.frame_rate_mode == FrameRateMode.VFR


def test_probe_missing_ffprobe_executable() -> None:
    """If ffprobe executable is missing on PATH, ProbeError is raised."""
    with (
        patch("shutil.which", return_value=None),
        pytest.raises(ProbeError, match="ffprobe executable not found"),
    ):
        _find_ffprobe_executable()


def test_probe_timeout(tmp_path: Path) -> None:
    """Subprocess timeout raises ProbeError."""
    dummy_file = tmp_path / "dummy.mp4"
    dummy_file.write_bytes(b"0" * 2048)

    with (
        patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ffprobe", timeout=0.01)),
        pytest.raises(ProbeError, match="timed out"),
    ):
        probe_media(dummy_file, check_file_exists=False)


def test_probe_invalid_json_output(tmp_path: Path) -> None:
    """Malformed non-JSON output from ffprobe raises ProbeError."""
    dummy_file = tmp_path / "dummy.mp4"
    dummy_file.write_bytes(b"0" * 2048)

    fake_res = subprocess.CompletedProcess(
        args=["ffprobe"], returncode=0, stdout="NOT_VALID_JSON", stderr=""
    )
    with (
        patch("subprocess.run", return_value=fake_res),
        pytest.raises(ProbeError, match="Failed to parse ffprobe JSON"),
    ):
        probe_media(dummy_file, check_file_exists=False)
