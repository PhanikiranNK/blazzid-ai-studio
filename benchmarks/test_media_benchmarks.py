"""Repeatable performance benchmarks for BLAZZID media ingestion & preprocessing pipeline.

Empirically measures throughput and latency for:
- ffprobe metadata inspection
- H.264 analysis proxy generation
- 16kHz PCM WAV audio extraction
- Sparse keyframe extraction via OpenCV
- Bounded-buffer waveform peak generation
- End-to-end MediaPipeline execution
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from blazzid_media.frames import extract_sparse_frames
from blazzid_media.models import PreprocessingConfig
from blazzid_media.pipeline import MediaPipeline
from blazzid_media.preprocessing import extract_audio_wav, generate_analysis_proxy
from blazzid_media.probe import probe_media
from blazzid_media.waveform import generate_waveform_peaks
from tests.fixtures.synthetic_media import (
    generate_synthetic_audio,
    generate_synthetic_video,
    is_ffmpeg_available,
)

pytestmark = pytest.mark.skipif(not is_ffmpeg_available(), reason="FFmpeg not available on PATH")


@pytest.fixture(scope="module")
def benchmark_video_fixture() -> Iterator[Path]:
    """Pre-generates a 3-second synthetic gameplay fixture for benchmark runs."""
    temp_dir = Path(tempfile.mkdtemp(prefix="blazzid_bench_media_"))
    video_path = generate_synthetic_video(
        duration_seconds=3.0,
        width=1280,
        height=720,
        fps=30,
        has_audio=True,
        output_path=temp_dir / "bench_fixture_720p.mp4",
    )
    yield video_path
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="module")
def benchmark_audio_fixture() -> Iterator[Path]:
    """Pre-generates a 10-second 16kHz audio fixture for waveform benchmarks."""
    temp_dir = Path(tempfile.mkdtemp(prefix="blazzid_bench_audio_"))
    audio_path = generate_synthetic_audio(
        duration_seconds=10.0,
        sample_rate=16000,
        frequency=440,
        output_path=temp_dir / "bench_fixture_10s.wav",
    )
    yield audio_path
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_benchmark_probe_media(benchmark: Any, benchmark_video_fixture: Path) -> None:
    """Measures ffprobe inspection latency and frame-rate classification."""

    def run_probe() -> str:
        res = probe_media(benchmark_video_fixture)
        return res.video.codec_name

    codec = benchmark(run_probe)
    assert codec == "h264"


def test_benchmark_proxy_transcode(
    benchmark: Any, benchmark_video_fixture: Path, tmp_path: Path
) -> None:
    """Measures 720p 30fps H.264 proxy transcode speed."""
    ins = probe_media(benchmark_video_fixture)
    cfg = PreprocessingConfig(proxy_width=1280, proxy_height=720, proxy_fps=30, proxy_crf=26)
    out_file = tmp_path / "bench_proxy.mp4"

    def run_proxy() -> int:
        if out_file.exists():
            out_file.unlink()
        path, _ = generate_analysis_proxy(benchmark_video_fixture, out_file, ins, cfg)
        return path.stat().st_size

    size = benchmark(run_proxy)
    assert size > 0


def test_benchmark_audio_extraction(
    benchmark: Any, benchmark_video_fixture: Path, tmp_path: Path
) -> None:
    """Measures 16kHz mono WAV extraction throughput."""
    wav_out = tmp_path / "bench_audio.wav"

    def run_audio() -> int:
        if wav_out.exists():
            wav_out.unlink()
        path = extract_audio_wav(benchmark_video_fixture, wav_out)
        return path.stat().st_size

    size = benchmark(run_audio)
    assert size > 0


def test_benchmark_sparse_frame_extraction(
    benchmark: Any, benchmark_video_fixture: Path, tmp_path: Path
) -> None:
    """Measures OpenCV sparse keyframe extraction throughput at 1 fps."""
    frames_dir = tmp_path / "bench_frames"

    def run_frames() -> int:
        shutil.rmtree(frames_dir, ignore_errors=True)
        res = extract_sparse_frames(
            benchmark_video_fixture, frames_dir, target_interval_seconds=1.0
        )
        return res.total_frames_extracted

    count = benchmark(run_frames)
    assert count >= 2


def test_benchmark_waveform_generation(benchmark: Any, benchmark_audio_fixture: Path) -> None:
    """Measures chunk-based waveform peak generation throughput on 10s audio."""

    def run_waveform() -> int:
        res = generate_waveform_peaks(benchmark_audio_fixture, bucket_duration_seconds=0.1)
        return res.total_buckets

    buckets = benchmark(run_waveform)
    assert buckets >= 90


def test_benchmark_end_to_end_pipeline(
    benchmark: Any, benchmark_video_fixture: Path, tmp_path: Path
) -> None:
    """Measures complete end-to-end MediaPipeline execution time."""
    pipeline = MediaPipeline(frame_interval_seconds=1.0, waveform_bucket_seconds=0.1)
    work_dir = tmp_path / "bench_pipeline_run"

    def run_pipeline() -> bool:
        shutil.rmtree(work_dir, ignore_errors=True)
        res = pipeline.process(benchmark_video_fixture, work_dir)
        return res.is_success

    success = benchmark(run_pipeline)
    assert success is True
