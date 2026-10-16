"""Repeatable performance benchmarks for Stage 3 gameplay event detection.

Measures throughput and execution latency for:
- Frame visual feature extraction (mean luminance, histogram, Sobel edges)
- Activity and burst detection
- Trigger grouping and candidate deduplication
- End-to-end detection over a 60-second gameplay recording
"""

from __future__ import annotations

from typing import Any

from blazzid_detection.activity import detect_visual_activity, detect_visual_bursts
from blazzid_detection.config import DetectionConfig
from blazzid_detection.detector import GameplayEventDetector
from blazzid_detection.features import compute_single_frame_features, extract_sequence_features
from blazzid_detection.grouping import group_triggers_into_candidates
from blazzid_detection.models import DetectorType, RawEventTrigger
from tests.fixtures.synthetic_gameplay import (
    create_action_frame,
    create_solid_frame,
    generate_synthetic_gameplay_sequence,
)


def test_benchmark_feature_extraction_single_frame(benchmark: Any) -> None:
    """Measures visual feature extraction latency for a single 720p action frame."""
    frame = create_action_frame(width=1280, height=720, intensity=0.8)
    prev = create_solid_frame(width=1280, height=720)
    _, prev_gray, prev_hist = compute_single_frame_features(prev, 0, 0.0)

    def run_extract() -> bool:
        rec, _, _ = compute_single_frame_features(
            frame,
            frame_index=1,
            timestamp_seconds=1.0,
            previous_gray=prev_gray,
            previous_hist=prev_hist,
        )
        return rec.is_valid

    valid = benchmark(run_extract)
    assert valid is True


def test_benchmark_activity_and_burst_detection(benchmark: Any) -> None:
    """Measures activity and rolling z-score burst detection over 100 frame records."""
    entries, _ = generate_synthetic_gameplay_sequence(duration_seconds=100.0, fps=1.0)
    features = extract_sequence_features(entries)
    cfg = DetectionConfig()

    def run_detectors() -> int:
        act_trigs = detect_visual_activity(features, cfg)
        burst_trigs = detect_visual_bursts(features, cfg)
        return len(act_trigs) + len(burst_trigs)

    count = benchmark(run_detectors)
    assert count >= 1


def test_benchmark_trigger_grouping_and_deduplication(benchmark: Any) -> None:
    """Measures sweep-line grouping and deduplication across 100 raw triggers."""
    cfg = DetectionConfig()
    triggers: list[RawEventTrigger] = []
    for i in range(100):
        t_start = float(i * 2)
        triggers.append(
            RawEventTrigger(
                detector_type=DetectorType.VISUAL_BURST
                if i % 2 == 0
                else DetectorType.VISUAL_ACTIVITY,
                start_seconds=t_start,
                end_seconds=t_start + 3.0,
                peak_seconds=t_start + 1.5,
                peak_intensity=0.8,
                raw_score=2.0,
                confidence=0.75,
            )
        )

    def run_grouping() -> int:
        cands = group_triggers_into_candidates(triggers, source_duration_seconds=250.0, config=cfg)
        return len(cands)

    cand_count = benchmark(run_grouping)
    assert cand_count > 0


def test_benchmark_end_to_end_detection(benchmark: Any) -> None:
    """Measures end-to-end detection runtime over a 60-second synthetic gameplay recording."""
    entries, _ = generate_synthetic_gameplay_sequence(
        duration_seconds=60.0,
        fps=1.0,
        combat_intervals=[(10.0, 20.0), (35.0, 48.0)],
    )
    detector = GameplayEventDetector()

    def run_pipeline() -> int:
        res = detector.detect(entries, source_duration_seconds=60.0)
        return len(res.candidates)

    count = benchmark(run_pipeline)
    assert count >= 2
