"""Unit tests for candidate scoring, confidence calibration, and evidence provenance."""

from __future__ import annotations

from blazzid_core.contracts.events import GameplayEventType
from blazzid_core.contracts.observations import Modality
from blazzid_core.contracts.time import TimeInterval
from blazzid_detection.config import DetectionConfig
from blazzid_detection.models import DetectorType, RawEventTrigger
from blazzid_detection.scoring import build_event_candidate, create_detector_observation


def test_create_detector_observation() -> None:
    """RawEventTrigger converts to valid Observation contract with Modality.VISUAL."""
    cfg = DetectionConfig()
    trig = RawEventTrigger(
        detector_type=DetectorType.VISUAL_BURST,
        start_seconds=5.0,
        end_seconds=8.0,
        peak_seconds=6.5,
        peak_intensity=0.88,
        raw_score=2.5,
        confidence=0.75,
        supporting_features={"z_score": 2.5},
    )

    obs = create_detector_observation(trig, cfg)
    assert obs.modality == Modality.VISUAL
    assert obs.confidence == 0.75
    assert obs.interval.start == 5.0
    assert obs.interval.end == 8.0
    assert obs.provenance.detector_name == "VISUAL_BURST"
    assert obs.provenance.raw_features["z_score"] == 2.5


def test_multi_detector_consensus_boosts_confidence() -> None:
    """An event supported by two distinct detectors has higher confidence than single-detector evidence."""
    cfg = DetectionConfig()
    t1 = RawEventTrigger(
        detector_type=DetectorType.VISUAL_BURST,
        start_seconds=10.0,
        end_seconds=15.0,
        peak_seconds=12.0,
        peak_intensity=0.8,
        raw_score=2.0,
        confidence=0.60,
    )
    t2 = RawEventTrigger(
        detector_type=DetectorType.SUSTAINED_COMBAT,
        start_seconds=10.0,
        end_seconds=15.0,
        peak_seconds=12.0,
        peak_intensity=0.8,
        raw_score=2.0,
        confidence=0.60,
    )

    interval = TimeInterval(start=9.0, end=16.0)
    single_cand = build_event_candidate(
        GameplayEventType.VISUAL_BURST,
        interval,
        10.0,
        12.0,
        [t1],
        cfg,
        30.0,
    )
    multi_cand = build_event_candidate(
        GameplayEventType.SUSTAINED_COMBAT,
        interval,
        10.0,
        12.0,
        [t1, t2],
        cfg,
        30.0,
    )

    assert multi_cand.composite_confidence > single_cand.composite_confidence
    assert 0.0 <= multi_cand.composite_confidence <= 1.0


def test_confidence_strictly_bounded() -> None:
    """Extreme confidence values are clamped cleanly to [0.0, 1.0] without validation failure."""
    cfg = DetectionConfig()
    t_high = RawEventTrigger(
        detector_type=DetectorType.VISUAL_BURST,
        start_seconds=5.0,
        end_seconds=10.0,
        peak_seconds=7.0,
        peak_intensity=1.0,
        raw_score=10.0,
        confidence=0.99,
    )
    cand = build_event_candidate(
        GameplayEventType.VISUAL_BURST,
        TimeInterval(start=4.0, end=11.0),
        5.0,
        7.0,
        [t_high],
        cfg,
        20.0,
    )
    assert 0.0 <= cand.composite_confidence <= 0.98
