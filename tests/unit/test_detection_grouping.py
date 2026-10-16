"""Unit tests for trigger grouping, narrative padding, and deduplication."""

from __future__ import annotations

from blazzid_core.contracts.events import GameplayEventType
from blazzid_detection.config import DetectionConfig
from blazzid_detection.grouping import group_triggers_into_candidates
from blazzid_detection.models import DetectorType, RawEventTrigger


def test_empty_triggers_returns_empty_candidates() -> None:
    """Empty trigger list produces an empty candidate list."""
    cfg = DetectionConfig()
    res = group_triggers_into_candidates([], source_duration_seconds=60.0, config=cfg)
    assert res == []


def test_merge_proximate_triggers() -> None:
    """Triggers separated by less than merge_gap_seconds are merged into a single candidate."""
    cfg = DetectionConfig(merge_gap_seconds=2.0, lead_in_seconds=1.0, lead_out_seconds=1.0)
    t1 = RawEventTrigger(
        detector_type=DetectorType.VISUAL_BURST,
        start_seconds=10.0,
        end_seconds=12.0,
        peak_seconds=11.0,
        peak_intensity=0.8,
        raw_score=2.0,
        confidence=0.7,
    )
    t2 = RawEventTrigger(
        detector_type=DetectorType.SUSTAINED_COMBAT,
        start_seconds=13.0,
        end_seconds=16.0,
        peak_seconds=14.0,
        peak_intensity=0.75,
        raw_score=3.0,
        confidence=0.8,
    )

    candidates = group_triggers_into_candidates([t1, t2], source_duration_seconds=30.0, config=cfg)
    assert len(candidates) == 1
    c = candidates[0]
    # start = 10.0 - 1.0 (lead-in) = 9.0
    assert c.interval.start == 9.0
    # end = 16.0 + 1.0 (lead-out) = 17.0
    assert c.interval.end == 17.0
    assert c.event_type == GameplayEventType.SUSTAINED_COMBAT
    assert len(c.evidence_sources) == 2


def test_clamping_to_source_duration() -> None:
    """Candidate intervals are strictly clamped to [0.0, source_duration_seconds]."""
    cfg = DetectionConfig(lead_in_seconds=3.0, lead_out_seconds=3.0)
    # Event near start
    t_start = RawEventTrigger(
        detector_type=DetectorType.VISUAL_BURST,
        start_seconds=1.0,
        end_seconds=3.0,
        peak_seconds=2.0,
        peak_intensity=0.8,
        raw_score=2.0,
        confidence=0.7,
    )
    # Event near end
    t_end = RawEventTrigger(
        detector_type=DetectorType.VISUAL_BURST,
        start_seconds=18.0,
        end_seconds=19.5,
        peak_seconds=19.0,
        peak_intensity=0.8,
        raw_score=2.0,
        confidence=0.7,
    )

    candidates = group_triggers_into_candidates(
        [t_start, t_end], source_duration_seconds=20.0, config=cfg
    )
    assert len(candidates) == 2
    assert candidates[0].interval.start >= 0.0
    assert candidates[1].interval.end <= 20.0


def test_deduplicate_high_iou_candidates() -> None:
    """Candidates overlapping by >= 70% IoU are suppressed into a single higher-confidence candidate."""
    cfg = DetectionConfig(lead_in_seconds=0.0, lead_out_seconds=0.0)
    t1 = RawEventTrigger(
        detector_type=DetectorType.VISUAL_BURST,
        start_seconds=10.0,
        end_seconds=15.0,
        peak_seconds=12.0,
        peak_intensity=0.9,
        raw_score=3.0,
        confidence=0.85,
    )
    t2 = RawEventTrigger(
        detector_type=DetectorType.VISUAL_ACTIVITY,
        start_seconds=10.5,
        end_seconds=15.0,
        peak_seconds=12.0,
        peak_intensity=0.7,
        raw_score=1.5,
        confidence=0.50,
    )

    candidates = group_triggers_into_candidates([t1, t2], source_duration_seconds=30.0, config=cfg)
    assert len(candidates) == 1
    assert candidates[0].composite_confidence >= 0.85
