"""Integration tests for the end-to-end highlight assembly pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from blazzid_assembly.config import AssemblyConfig
from blazzid_assembly.models import AssemblyProfile
from blazzid_assembly.pipeline import HighlightAssemblyPipeline
from blazzid_core.contracts.events import GameplayEventCandidate, GameplayEventType
from blazzid_core.contracts.observations import Modality, Observation, ObservationProvenance
from blazzid_core.contracts.time import TimeInterval
from tests.fixtures.synthetic_media import generate_synthetic_video, is_ffmpeg_available


def _make_candidate(
    cid: str,
    start: float,
    end: float,
    event_type: GameplayEventType = GameplayEventType.SUSTAINED_COMBAT,
    confidence: float = 0.85,
) -> GameplayEventCandidate:
    obs = [
        Observation(
            modality=Modality.VISUAL,
            interval=TimeInterval(start=start, end=end),
            confidence=confidence,
            provenance=ObservationProvenance(detector_name="visual_activity"),
        ),
        Observation(
            modality=Modality.VISUAL,
            interval=TimeInterval(start=start, end=end),
            confidence=confidence,
            provenance=ObservationProvenance(detector_name="visual_burst"),
        ),
    ]
    return GameplayEventCandidate(
        id=cid,
        event_type=event_type,
        trigger_timestamp=start + 0.1,
        interval=TimeInterval(start=start, end=end),
        climax_timestamp=start + (end - start) / 2.0,
        composite_confidence=confidence,
        evidence_sources=obs,
        metadata={"peak_intensity": 0.88},
    )


@pytest.mark.skipif(not is_ffmpeg_available(), reason="FFmpeg not available on PATH")
def test_end_to_end_assembly_landscape_with_audio(tmp_path: Path) -> None:
    source_video = generate_synthetic_video(
        duration_seconds=6.0,
        width=640,
        height=360,
        fps=30,
        has_audio=True,
        output_path=tmp_path / "gameplay.mp4",
    )
    output_video = tmp_path / "montage.mp4"

    # Two highlight candidates (durations 2.0s each >= min_clip_duration_seconds 2.0s)
    cands = [
        _make_candidate("c1", 1.0, 3.0),
        _make_candidate("c2", 3.5, 5.5),
    ]

    cfg = AssemblyConfig(
        profile=AssemblyProfile.DEV_LANDSCAPE,
        target_duration_seconds=5.0,
        lead_in_padding_seconds=0.2,
        lead_out_padding_seconds=0.2,
        work_dir=tmp_path / "work",
    )

    pipeline = HighlightAssemblyPipeline(config=cfg)
    result = pipeline.assemble(source_video, cands, output_video)

    assert result.is_success is True
    assert result.output_video_path is not None
    assert result.output_video_path.is_file()
    assert result.output_video_path.stat().st_size > 0

    # Validation report
    assert result.validation_report is not None
    assert result.validation_report.is_valid is True
    assert result.validation_report.has_video is True
    assert result.validation_report.has_audio is True
    assert result.validation_report.width == 640
    assert result.validation_report.height == 360

    # Manifest file
    assert result.manifest_path is not None
    assert result.manifest_path.is_file()
    manifest_data = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest_data["manifest_version"] == "1.0.0"
    assert len(manifest_data["planned_clips"]) == 2
    assert manifest_data["rendering_profile"]["width"] == 640
    assert manifest_data["rendering_profile"]["height"] == 360


@pytest.mark.skipif(not is_ffmpeg_available(), reason="FFmpeg not available on PATH")
def test_end_to_end_assembly_portrait_profile(tmp_path: Path) -> None:
    source_video = generate_synthetic_video(
        duration_seconds=4.0,
        width=640,
        height=360,
        fps=30,
        has_audio=True,
        output_path=tmp_path / "gameplay_landscape.mp4",
    )
    output_video = tmp_path / "montage_portrait.mp4"

    cands = [_make_candidate("c1", 1.0, 3.0)]

    cfg = AssemblyConfig(
        profile=AssemblyProfile.DEV_PORTRAIT,  # 360x640 vertical target
        target_duration_seconds=3.0,
        lead_in_padding_seconds=0.0,
        lead_out_padding_seconds=0.0,
        work_dir=tmp_path / "work_portrait",
    )

    pipeline = HighlightAssemblyPipeline(config=cfg)
    result = pipeline.assemble(source_video, cands, output_video)

    assert result.is_success is True
    assert result.output_video_path is not None
    assert result.validation_report is not None
    assert result.validation_report.is_valid is True
    assert result.validation_report.width == 360
    assert result.validation_report.height == 640


@pytest.mark.skipif(not is_ffmpeg_available(), reason="FFmpeg not available on PATH")
def test_assembly_video_only_source_without_audio(tmp_path: Path) -> None:
    source_video = generate_synthetic_video(
        duration_seconds=4.0,
        width=640,
        height=360,
        fps=30,
        has_audio=False,
        output_path=tmp_path / "video_only.mp4",
    )
    output_video = tmp_path / "montage_video_only.mp4"

    cands = [_make_candidate("c1", 1.0, 3.0)]

    cfg = AssemblyConfig(
        profile=AssemblyProfile.DEV_LANDSCAPE,
        target_duration_seconds=3.0,
        work_dir=tmp_path / "work_video_only",
    )

    pipeline = HighlightAssemblyPipeline(config=cfg)
    result = pipeline.assemble(source_video, cands, output_video)

    assert result.is_success is True
    assert result.output_video_path is not None
    assert result.validation_report is not None
    assert result.validation_report.is_valid is True
    assert result.validation_report.has_audio is False  # Audio-less policy satisfied


def test_assembly_empty_candidates_handled_gracefully(tmp_path: Path) -> None:
    source_video = tmp_path / "dummy.mp4"
    source_video.write_bytes(b"dummy")
    output_video = tmp_path / "out.mp4"

    pipeline = HighlightAssemblyPipeline()
    result = pipeline.assemble(
        source_video, [], output_video, source_duration_seconds=30.0, source_has_audio=False
    )

    assert result.is_success is False
    assert result.output_video_path is None
    assert "No clips qualified" in str(result.error_message)


def test_assembly_missing_source_file(tmp_path: Path) -> None:
    missing_source = tmp_path / "missing.mp4"
    output_video = tmp_path / "out.mp4"

    pipeline = HighlightAssemblyPipeline()
    result = pipeline.assemble(missing_source, [], output_video)

    assert result.is_success is False
    assert "not found" in str(result.error_message)
