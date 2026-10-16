"""Unit tests for bounded-memory waveform peak and RMS generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from blazzid_media.errors import WaveformError
from blazzid_media.waveform import generate_waveform_peaks, save_waveform_json
from tests.fixtures.synthetic_media import (
    generate_synthetic_audio,
    is_ffmpeg_available,
)

pytestmark = pytest.mark.skipif(not is_ffmpeg_available(), reason="FFmpeg not available on PATH")


def test_generate_waveform_peaks_sine_wave(tmp_path: Path) -> None:
    """Waveform generation on 16kHz sine tone yields non-zero normalized peaks and RMS."""
    audio_path = generate_synthetic_audio(
        duration_seconds=2.0,
        sample_rate=16000,
        frequency=440,
        output_path=tmp_path / "sine.wav",
    )

    bucket_sec = 0.1
    res = generate_waveform_peaks(
        audio_path,
        bucket_duration_seconds=bucket_sec,
        audio_start_seconds=0.5,
    )

    assert res.sample_rate == 16000
    assert res.channels == 1
    assert res.bucket_duration_seconds == bucket_sec
    assert res.audio_start_seconds == 0.5
    # 2.0s / 0.1s = 20 buckets (approx)
    assert 19 <= res.total_buckets <= 21
    assert len(res.peaks) == res.total_buckets
    assert res.rms is not None
    assert len(res.rms) == res.total_buckets

    for p, r in zip(res.peaks, res.rms):
        assert 0.0 <= p <= 1.0
        assert 0.0 <= r <= 1.0
        assert p >= r  # Peak is always >= RMS


def test_generate_waveform_deterministic(tmp_path: Path) -> None:
    """Repeated runs on the same audio produce identical peaks and RMS."""
    audio_path = generate_synthetic_audio(
        duration_seconds=1.0,
        output_path=tmp_path / "det.wav",
    )

    res1 = generate_waveform_peaks(audio_path, bucket_duration_seconds=0.2)
    res2 = generate_waveform_peaks(audio_path, bucket_duration_seconds=0.2)

    assert res1.peaks == res2.peaks
    assert res1.rms == res2.rms


def test_save_waveform_json(tmp_path: Path) -> None:
    """save_waveform_json creates a valid JSON artifact matching the WaveformResult schema."""
    audio_path = generate_synthetic_audio(duration_seconds=1.0, output_path=tmp_path / "test.wav")
    res = generate_waveform_peaks(audio_path, bucket_duration_seconds=0.2)

    json_path = tmp_path / "waveform.json"
    saved = save_waveform_json(res, json_path)
    assert saved.exists()

    with json_path.open() as f:
        data = json.load(f)

    assert data["sample_rate"] == 16000
    assert data["bucket_duration_seconds"] == 0.2
    assert "peaks" in data
    assert "rms" in data
    assert len(data["peaks"]) == res.total_buckets


def test_waveform_nonexistent_file(tmp_path: Path) -> None:
    """Nonexistent WAV file raises WaveformError."""
    with pytest.raises(WaveformError, match="Audio file not found"):
        generate_waveform_peaks(tmp_path / "nonexistent.wav")


def test_waveform_invalid_bucket_duration(tmp_path: Path) -> None:
    """Zero or negative bucket duration raises WaveformError."""
    audio_path = generate_synthetic_audio(duration_seconds=1.0, output_path=tmp_path / "test.wav")
    with pytest.raises(WaveformError, match="positive finite float"):
        generate_waveform_peaks(audio_path, bucket_duration_seconds=-0.5)
