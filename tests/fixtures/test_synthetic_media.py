"""Tests for synthetic media fixture generator."""

import os

import pytest

from tests.fixtures.synthetic_media import (
    generate_synthetic_audio,
    generate_synthetic_video,
    is_ffmpeg_available,
)

pytestmark = pytest.mark.skipif(
    not is_ffmpeg_available(), reason="FFmpeg executable is not available on PATH"
)


class TestSyntheticMediaFixtures:
    def test_generate_synthetic_video(self) -> None:
        video_path = generate_synthetic_video(duration_seconds=1.0, width=320, height=240, fps=15)
        try:
            assert video_path.exists()
            assert video_path.stat().st_size > 0
        finally:
            if video_path.exists():
                os.remove(video_path)

    def test_generate_synthetic_audio(self) -> None:
        audio_path = generate_synthetic_audio(duration_seconds=1.0, sample_rate=16000)
        try:
            assert audio_path.exists()
            assert audio_path.stat().st_size > 0
        finally:
            if audio_path.exists():
                os.remove(audio_path)
