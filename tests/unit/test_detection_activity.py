"""Unit tests for visual activity, burst, and sustained combat detectors."""

from __future__ import annotations

from blazzid_detection.activity import (
    compute_frame_activity_metric,
    detect_sustained_combat,
    detect_visual_activity,
    detect_visual_bursts,
)
from blazzid_detection.config import DetectionConfig
from blazzid_detection.features import extract_sequence_features
from blazzid_detection.models import DetectorType
from tests.fixtures.synthetic_gameplay import create_action_frame, create_solid_frame


def test_static_footage_produces_no_activity_triggers() -> None:
    """Completely static footage produces near-zero activity metric and zero triggers."""
    cfg = DetectionConfig()
    entries = [(create_solid_frame(), float(t)) for t in range(10)]
    features = extract_sequence_features(entries)

    for f in features:
        assert compute_frame_activity_metric(f) == 0.0

    triggers = detect_visual_activity(features, cfg)
    assert len(triggers) == 0


def test_intense_combat_produces_activity_trigger() -> None:
    """Sequence with 5 seconds of intense combat produces an activity trigger spanning the action."""
    cfg = DetectionConfig(min_event_duration_seconds=2.0)
    entries = []
    # 0 to 4: calm
    for t in range(5):
        entries.append((create_solid_frame(color=(30, 30, 30)), float(t)))
    # 5 to 11: combat
    for t in range(5, 12):
        entries.append((create_action_frame(intensity=0.8, seed=t), float(t)))
    # 12 to 15: calm
    for t in range(12, 16):
        entries.append((create_solid_frame(color=(30, 30, 30)), float(t)))

    features = extract_sequence_features(entries)
    triggers = detect_visual_activity(features, cfg)

    assert len(triggers) >= 1
    trig = triggers[0]
    assert trig.detector_type == DetectorType.VISUAL_ACTIVITY
    assert trig.start_seconds >= 4.0
    assert trig.end_seconds <= 12.0
    assert trig.peak_intensity > 0.10


def test_visual_burst_detector_spike() -> None:
    """Sudden isolated spike produces a VISUAL_BURST trigger."""
    cfg = DetectionConfig(activity_z_score_threshold=1.5, rolling_window_seconds=10.0)
    entries = []
    # 0 to 10: calm
    for t in range(10):
        entries.append((create_solid_frame(), float(t)))
    # 10: huge spike
    entries.append((create_action_frame(intensity=1.0, seed=999), 10.0))
    # 11 to 20: calm
    for t in range(11, 21):
        entries.append((create_solid_frame(), float(t)))

    features = extract_sequence_features(entries)
    bursts = detect_visual_bursts(features, cfg)

    assert len(bursts) == 1
    assert bursts[0].detector_type == DetectorType.VISUAL_BURST
    assert bursts[0].peak_seconds == 10.0


def test_sustained_combat_requires_minimum_duration() -> None:
    """Brief 1-second spike does not trigger SUSTAINED_COMBAT, while 5s action does."""
    cfg = DetectionConfig(min_event_duration_seconds=3.0, sustained_activity_ratio=0.08)

    # 1. Brief spike sequence
    brief_entries = [(create_solid_frame(), float(t)) for t in range(5)]
    brief_entries.append((create_action_frame(), 5.0))
    brief_entries.extend([(create_solid_frame(), float(t)) for t in range(6, 11)])
    brief_features = extract_sequence_features(brief_entries)
    assert len(detect_sustained_combat(brief_features, cfg)) == 0

    # 2. Prolonged combat sequence (5s)
    combat_entries = [(create_solid_frame(), float(t)) for t in range(5)]
    for t in range(5, 11):
        combat_entries.append((create_action_frame(intensity=0.8, seed=t), float(t)))
    combat_entries.extend([(create_solid_frame(), float(t)) for t in range(11, 16)])
    combat_features = extract_sequence_features(combat_entries)

    combat_triggers = detect_sustained_combat(combat_features, cfg)
    assert len(combat_triggers) >= 1
    assert combat_triggers[0].detector_type == DetectorType.SUSTAINED_COMBAT
    assert combat_triggers[0].end_seconds - combat_triggers[0].start_seconds >= 3.0
