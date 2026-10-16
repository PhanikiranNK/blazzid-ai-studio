"""Integration tests and ground-truth evaluation for GameplayEventDetector."""

from __future__ import annotations

from pathlib import Path

import pytest

from blazzid_core.contracts.events import GameplayEventType
from blazzid_detection.config import DetectionConfig
from blazzid_detection.detector import GameplayEventDetector
from blazzid_media.pipeline import MediaPipeline
from tests.fixtures.synthetic_gameplay import (
    create_solid_frame,
    generate_synthetic_gameplay_sequence,
)
from tests.fixtures.synthetic_media import (
    generate_synthetic_video,
    is_ffmpeg_available,
)


def test_detector_empty_input() -> None:
    """Empty frame list returns zero candidates with valid diagnostics."""
    detector = GameplayEventDetector()
    res = detector.detect([], source_duration_seconds=30.0)

    assert res.is_success is True
    assert len(res.candidates) == 0
    assert res.diagnostics.total_frames_analyzed == 0
    assert res.diagnostics.temporal_coverage_ratio == 0.0


def test_detector_static_footage_zero_candidates() -> None:
    """Completely static 30-second menu footage produces zero false-positive event candidates."""
    detector = GameplayEventDetector()
    entries = [(create_solid_frame(color=(50, 50, 50)), float(t)) for t in range(30)]

    res = detector.detect(entries, source_duration_seconds=30.0)
    assert res.is_success is True
    assert len(res.candidates) == 0
    assert res.diagnostics.total_frames_analyzed == 30
    assert res.diagnostics.valid_frames_count == 30


def test_detector_ground_truth_combat_and_cuts() -> None:
    """Evaluates detector against synthetic gameplay with known ground-truth intervals.

    Ground truth:
    - Combat episode 1: [10.0, 16.0]
    - Scene cut: t=22.0
    """
    entries, gt_intervals = generate_synthetic_gameplay_sequence(
        duration_seconds=30.0,
        fps=1.0,
        combat_intervals=[(10.0, 16.0)],
        cut_timestamps=[22.0],
    )

    detector = GameplayEventDetector(
        config=DetectionConfig(
            min_event_duration_seconds=2.0,
            lead_in_seconds=1.0,
            lead_out_seconds=1.0,
        )
    )
    res = detector.detect(entries, source_duration_seconds=30.0)

    assert res.is_success is True
    assert len(res.candidates) >= 1

    # Check that combat interval was detected and overlaps ground truth
    gt = gt_intervals[0]
    matched = False
    for cand in res.candidates:
        iou = cand.interval.intersection_over_union(gt)
        if iou >= 0.50:
            matched = True
            # Verify boundary error is bounded (< 2.0s with narrative padding)
            start_error = abs(cand.interval.start - (gt.start - 1.0))
            assert start_error <= 1.5
            assert cand.event_type in (
                GameplayEventType.SUSTAINED_COMBAT,
                GameplayEventType.VISUAL_BURST,
                GameplayEventType.GENERIC_HIGHLIGHT,
            )
            assert cand.composite_confidence >= 0.30
            break

    assert matched, (
        f"Failed to match ground truth {gt} among candidates {[c.interval for c in res.candidates]}"
    )


@pytest.mark.skipif(not is_ffmpeg_available(), reason="FFmpeg not available on PATH")
def test_detector_integrates_with_stage2_pipeline_result(tmp_path: Path) -> None:
    """End-to-end integration: Stage 2 MediaPipeline output consumed directly by Stage 3 GameplayEventDetector."""
    src = generate_synthetic_video(
        duration_seconds=4.0,
        width=640,
        height=360,
        fps=30,
        has_audio=True,
        output_path=tmp_path / "gameplay.mp4",
    )
    work_dir = tmp_path / "pipeline_out"

    # Stage 2 Media Processing
    pipeline = MediaPipeline(frame_interval_seconds=1.0)
    pipeline_res = pipeline.process(src, work_dir)
    assert pipeline_res.is_success is True
    assert pipeline_res.frames.total_frames_extracted >= 3

    # Stage 3 Event Detection directly consuming PipelineResult
    detector = GameplayEventDetector()
    detect_res = detector.detect(pipeline_res)

    assert detect_res.is_success is True
    assert detect_res.diagnostics.total_frames_analyzed >= 3
    assert detect_res.diagnostics.valid_frames_count == detect_res.diagnostics.total_frames_analyzed
    assert detect_res.diagnostics.corrupt_or_missing_frames_count == 0
    assert detect_res.diagnostics.source_duration_seconds >= 3.5


def test_detector_corrupt_frames_handled_gracefully(tmp_path: Path) -> None:
    """A sequence containing unreadable or corrupted frame paths does not raise exceptions."""
    valid_img = tmp_path / "valid.jpg"
    corrupt_img = tmp_path / "corrupt.jpg"

    f = create_solid_frame()
    import cv2

    cv2.imwrite(str(valid_img), f)
    corrupt_img.write_bytes(b"garbage_not_an_image")

    entries: list[tuple[Path, float]] = [
        (valid_img, 0.0),
        (corrupt_img, 1.0),
        (valid_img, 2.0),
    ]

    detector = GameplayEventDetector()
    res = detector.detect(entries, source_duration_seconds=5.0)

    assert res.is_success is True
    assert res.diagnostics.total_frames_analyzed == 3
    assert res.diagnostics.valid_frames_count == 2
    assert res.diagnostics.corrupt_or_missing_frames_count == 1
