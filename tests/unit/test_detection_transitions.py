"""Unit tests for visual transitions and scene cut detection."""

from __future__ import annotations

from blazzid_detection.config import DetectionConfig
from blazzid_detection.features import extract_sequence_features
from blazzid_detection.models import DetectorType
from blazzid_detection.transitions import detect_transitions
from tests.fixtures.synthetic_gameplay import create_solid_frame


def test_abrupt_scene_cut_detected() -> None:
    """Sudden cut from black to white frame triggers a SCENE_TRANSITION event."""
    cfg = DetectionConfig(
        transition_difference_threshold=0.30, transition_hist_distance_threshold=0.30
    )
    entries = []
    # Black screen
    for t in range(5):
        entries.append((create_solid_frame(color=(0, 0, 0)), float(t)))
    # White screen cut at t=5
    for t in range(5, 10):
        entries.append((create_solid_frame(color=(255, 255, 255)), float(t)))

    features = extract_sequence_features(entries)
    transitions = detect_transitions(features, cfg)

    assert len(transitions) == 1
    trig = transitions[0]
    assert trig.detector_type == DetectorType.SCENE_TRANSITION
    assert trig.peak_seconds == 5.0
    assert trig.start_seconds <= 5.0 <= trig.end_seconds


def test_gradual_color_shift_not_detected_as_cut() -> None:
    """Gradual color change (small delta per frame) does not trigger scene cut."""
    cfg = DetectionConfig(
        transition_difference_threshold=0.35, transition_hist_distance_threshold=0.45
    )
    entries = []
    # Subtle gradient drift (5 units per second)
    for t in range(20):
        c = int(50 + t * 5)
        entries.append((create_solid_frame(color=(c, c, c)), float(t)))

    features = extract_sequence_features(entries)
    transitions = detect_transitions(features, cfg)
    assert len(transitions) == 0
