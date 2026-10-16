"""Integration tests for the complete MediaPipeline on synthetic gameplay fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from blazzid_media.errors import ProbeError
from blazzid_media.models import PipelineStageStatus
from blazzid_media.pipeline import MediaPipeline
from tests.fixtures.synthetic_media import (
    generate_corrupt_media,
    generate_portrait_video,
    generate_synthetic_video,
    is_ffmpeg_available,
)

pytestmark = pytest.mark.skipif(
    not is_ffmpeg_available(), reason="FFmpeg/ffprobe not available on PATH"
)


def test_pipeline_landscape_with_audio(tmp_path: Path) -> None:
    """Full pipeline execution on landscape video with audio."""
    src = generate_synthetic_video(
        duration_seconds=2.5,
        width=1280,
        height=720,
        fps=30,
        has_audio=True,
        output_path=tmp_path / "gameplay_landscape.mp4",
    )
    work_dir = tmp_path / "work_landscape"

    pipeline = MediaPipeline(frame_interval_seconds=1.0, waveform_bucket_seconds=0.1)
    result = pipeline.process(src, work_dir)

    assert result.is_success is True
    assert result.has_audio is True
    assert result.source_path == src.resolve()
    assert result.work_dir == work_dir.resolve()

    # Preprocessing artifacts
    assert result.preprocessing.proxy_path.exists()
    assert result.preprocessing.audio_path is not None
    assert result.preprocessing.audio_path.exists()

    # Sparse frames
    assert result.frames.total_frames_extracted >= 2
    for frame in result.frames.frames:
        assert frame.file_path.exists()
        assert frame.width <= 1280
        assert frame.height <= 720

    # Waveform
    assert result.waveform is not None
    assert result.waveform.total_buckets > 0
    assert (work_dir / "waveform.json").exists()

    # Audit stages
    assert len(result.stages) == 5
    for stage in result.stages:
        assert stage.status == PipelineStageStatus.SUCCESS
        assert stage.elapsed_seconds >= 0.0


def test_pipeline_portrait_with_audio(tmp_path: Path) -> None:
    """Full pipeline execution on portrait/vertical video."""
    src = generate_portrait_video(
        duration_seconds=2.0,
        width=720,
        height=1280,
        fps=30,
        has_audio=True,
        output_path=tmp_path / "gameplay_portrait.mp4",
    )
    work_dir = tmp_path / "work_portrait"

    pipeline = MediaPipeline(frame_interval_seconds=1.0)
    result = pipeline.process(src, work_dir)

    assert result.is_success is True
    assert result.preprocessing.proxy_path.exists()
    assert result.preprocessing.proxy_metadata.video.height <= 720
    assert result.preprocessing.proxy_metadata.video.width % 2 == 0
    assert result.frames.total_frames_extracted >= 1


def test_pipeline_video_without_audio(tmp_path: Path) -> None:
    """Full pipeline execution on video without audio (waveform skipped, video succeeds)."""
    src = generate_synthetic_video(
        duration_seconds=2.0,
        width=640,
        height=360,
        fps=30,
        has_audio=False,
        output_path=tmp_path / "no_audio.mp4",
    )
    work_dir = tmp_path / "work_no_audio"

    pipeline = MediaPipeline(frame_interval_seconds=1.0)
    result = pipeline.process(src, work_dir)

    assert result.is_success is True
    assert result.has_audio is False
    assert result.preprocessing.audio_path is None
    assert result.waveform is None

    # Check stages: WAVEFORM_GENERATION should be SKIPPED
    stage_statuses = {s.stage_name: s.status for s in result.stages}
    assert stage_statuses["VALIDATION"] == PipelineStageStatus.SUCCESS
    assert stage_statuses["INSPECTION"] == PipelineStageStatus.SUCCESS
    assert stage_statuses["PREPROCESSING"] == PipelineStageStatus.SUCCESS
    assert stage_statuses["FRAME_EXTRACTION"] == PipelineStageStatus.SUCCESS
    assert stage_statuses["WAVEFORM_GENERATION"] == PipelineStageStatus.SKIPPED


def test_pipeline_very_short_video(tmp_path: Path) -> None:
    """Very short video (0.4s) processes without failure or index bounds errors."""
    src = generate_synthetic_video(
        duration_seconds=0.4,
        width=320,
        height=240,
        fps=30,
        has_audio=True,
        output_path=tmp_path / "short.mp4",
    )
    work_dir = tmp_path / "work_short"

    pipeline = MediaPipeline(frame_interval_seconds=0.2)
    result = pipeline.process(src, work_dir)

    assert result.is_success is True
    assert result.frames.total_frames_extracted >= 1


def test_pipeline_corrupt_media_fails_gracefully(tmp_path: Path) -> None:
    """Corrupt media file fails at inspection stage with structured ProbeError."""
    src = generate_corrupt_media(tmp_path / "corrupt.mp4")
    work_dir = tmp_path / "work_corrupt"

    pipeline = MediaPipeline()
    with pytest.raises(ProbeError):
        pipeline.process(src, work_dir)
