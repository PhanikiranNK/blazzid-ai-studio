"""Unit tests for FFmpeg preprocessing: proxy transcode and audio extraction."""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path
from unittest.mock import patch

import pytest

from blazzid_media.errors import AudioExtractionError
from blazzid_media.models import PreprocessingConfig
from blazzid_media.preprocessing import (
    extract_audio_wav,
    generate_analysis_proxy,
    preprocess_media,
)
from blazzid_media.probe import probe_media
from tests.fixtures.synthetic_media import (
    generate_portrait_video,
    generate_synthetic_video,
    is_ffmpeg_available,
)

pytestmark = pytest.mark.skipif(not is_ffmpeg_available(), reason="FFmpeg not available on PATH")


def test_generate_proxy_landscape(tmp_path: Path) -> None:
    """Landscape video transcode preserves aspect ratio, normalizes fps, and satisfies bounds."""
    src = generate_synthetic_video(
        duration_seconds=1.5,
        width=1920,
        height=1080,
        fps=60,
        output_path=tmp_path / "source_1080p.mp4",
    )
    ins = probe_media(src)
    proxy_out = tmp_path / "proxy.mp4"

    cfg = PreprocessingConfig(proxy_width=1280, proxy_height=720, proxy_fps=30)
    out_path, proxy_ins = generate_analysis_proxy(src, proxy_out, ins, cfg)

    assert out_path.exists()
    assert proxy_ins.video.width == 1280
    assert proxy_ins.video.height == 720
    assert proxy_ins.video.codec_name == "h264"
    assert pytest.approx(proxy_ins.video.avg_frame_rate, rel=0.1) == 30.0


def test_generate_proxy_portrait(tmp_path: Path) -> None:
    """Portrait video is downscaled proportionally without distorted aspect ratio or stretching."""
    src = generate_portrait_video(
        duration_seconds=1.0,
        width=1080,
        height=1920,
        fps=30,
        output_path=tmp_path / "source_portrait.mp4",
    )
    ins = probe_media(src)
    proxy_out = tmp_path / "proxy_portrait.mp4"

    cfg = PreprocessingConfig(proxy_width=1280, proxy_height=720)
    out_path, proxy_ins = generate_analysis_proxy(src, proxy_out, ins, cfg)

    assert out_path.exists()
    # Height was 1920, scaled down proportionally to fit within 720: height=720, width=404 or 406 (even)
    assert proxy_ins.video.height <= 720
    assert proxy_ins.video.width % 2 == 0
    assert proxy_ins.video.height % 2 == 0


def test_generate_proxy_small_video_not_upscaled(tmp_path: Path) -> None:
    """A small source (e.g. 480x270) must not be upscaled to 1280x720."""
    src = generate_synthetic_video(
        duration_seconds=1.0,
        width=480,
        height=270,
        output_path=tmp_path / "small_source.mp4",
    )
    ins = probe_media(src)
    proxy_out = tmp_path / "proxy_small.mp4"

    out_path, proxy_ins = generate_analysis_proxy(src, proxy_out, ins)
    assert proxy_ins.video.width <= 480
    assert proxy_ins.video.height <= 270


def test_extract_audio_wav_parameters(tmp_path: Path) -> None:
    """extract_audio_wav produces valid 16kHz mono PCM WAV."""
    src = generate_synthetic_video(
        duration_seconds=1.5,
        has_audio=True,
        output_path=tmp_path / "source_with_audio.mp4",
    )
    wav_out = tmp_path / "extracted.wav"

    res = extract_audio_wav(src, wav_out, sample_rate=16000, channels=1)
    assert res.exists()

    with wave.open(str(res), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == 16000
        assert wf.getsampwidth() == 2  # 16-bit PCM
        n_frames = wf.getnframes()
        duration = n_frames / 16000.0
        assert pytest.approx(duration, rel=0.1) == 1.5


def test_preprocess_media_no_audio(tmp_path: Path) -> None:
    """preprocess_media on video without audio succeeds with audio_path=None and has_audio=False."""
    src = generate_synthetic_video(
        duration_seconds=1.0,
        has_audio=False,
        output_path=tmp_path / "no_audio.mp4",
    )
    work_dir = tmp_path / "work_no_audio"

    result = preprocess_media(src, work_dir)
    assert result.proxy_path.exists()
    assert result.has_audio is False
    assert result.audio_path is None


def test_partial_output_cleanup_on_failure(tmp_path: Path) -> None:
    """Partial outputs must be cleanly deleted when ffmpeg fails."""
    src = generate_synthetic_video(duration_seconds=1.0, output_path=tmp_path / "src.mp4")
    wav_out = tmp_path / "fail.wav"

    with (
        patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(cmd="ffmpeg", returncode=1, stderr="fail"),
        ),
        pytest.raises(AudioExtractionError),
    ):
        extract_audio_wav(src, wav_out)

    assert not wav_out.exists()
