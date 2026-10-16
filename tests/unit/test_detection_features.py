"""Unit tests for visual feature extraction across frames."""

from __future__ import annotations

from pathlib import Path

import pytest

from blazzid_detection.features import (
    compute_single_frame_features,
    extract_features_from_path,
    extract_sequence_features,
)
from tests.fixtures.synthetic_gameplay import create_action_frame, create_solid_frame


def test_compute_single_frame_features_solid() -> None:
    """Solid color frame has uniform luminance, zero edge density, and valid status."""
    frame = create_solid_frame(width=320, height=240, color=(100, 100, 100))
    rec, gray, hist = compute_single_frame_features(frame, frame_index=0, timestamp_seconds=0.0)

    assert rec.is_valid is True
    assert rec.width == 320
    assert rec.height == 240
    assert pytest.approx(rec.mean_luminance, abs=1.0) == 100.0
    assert rec.std_luminance < 1.0
    assert rec.frame_difference == 0.0
    assert rec.histogram_distance == 0.0
    assert rec.edge_density < 0.01
    assert len(rec.histogram) == 16
    assert pytest.approx(sum(rec.histogram), rel=0.01) == 1.0


def test_identical_consecutive_frames_zero_difference() -> None:
    """Two identical consecutive frames produce zero temporal difference and zero histogram distance."""
    frame1 = create_solid_frame(color=(50, 50, 50))
    frame2 = create_solid_frame(color=(50, 50, 50))

    rec1, gray1, hist1 = compute_single_frame_features(frame1, frame_index=0, timestamp_seconds=0.0)
    rec2, _, _ = compute_single_frame_features(
        frame2,
        frame_index=1,
        timestamp_seconds=1.0,
        previous_gray=gray1,
        previous_hist=hist1,
    )

    assert rec2.frame_difference == 0.0
    assert rec2.histogram_distance == 0.0


def test_distinct_consecutive_frames_positive_difference() -> None:
    """Frames with differing visuals produce high difference and histogram distance."""
    frame1 = create_solid_frame(color=(0, 0, 0))
    frame2 = create_solid_frame(color=(255, 255, 255))

    rec1, gray1, hist1 = compute_single_frame_features(frame1, frame_index=0, timestamp_seconds=0.0)
    rec2, _, _ = compute_single_frame_features(
        frame2,
        frame_index=1,
        timestamp_seconds=1.0,
        previous_gray=gray1,
        previous_hist=hist1,
    )

    assert rec2.frame_difference == 1.0
    assert rec2.histogram_distance > 0.50


def test_action_frame_high_edge_density() -> None:
    """Action frame with geometric circles and sparks has significantly higher edge density than solid frame."""
    solid = create_solid_frame()
    action = create_action_frame(intensity=0.9)

    rec_solid, _, _ = compute_single_frame_features(solid, 0, 0.0)
    rec_action, _, _ = compute_single_frame_features(action, 0, 0.0)

    assert rec_action.edge_density > rec_solid.edge_density
    assert rec_action.std_luminance > rec_solid.std_luminance


def test_extract_features_missing_file(tmp_path: Path) -> None:
    """Missing frame file yields is_valid=False without crashing."""
    missing = tmp_path / "nonexistent.jpg"
    rec, _, _ = extract_features_from_path(missing, frame_index=0, timestamp_seconds=0.0)

    assert rec.is_valid is False
    assert "not found" in (rec.error_message or "")


def test_extract_features_corrupt_file(tmp_path: Path) -> None:
    """Corrupted unreadable image file yields is_valid=False with diagnostic error."""
    corrupt = tmp_path / "corrupt.jpg"
    corrupt.write_bytes(b"not_a_valid_jpeg_payload")

    rec, _, _ = extract_features_from_path(corrupt, frame_index=0, timestamp_seconds=0.0)
    assert rec.is_valid is False
    assert rec.error_message is not None


def test_resolution_change_handling() -> None:
    """Dynamic resolution change between frames (e.g. 320x240 to 640x360) is resized without error."""
    f1 = create_solid_frame(width=320, height=240, color=(50, 50, 50))
    f2 = create_solid_frame(width=640, height=360, color=(50, 50, 50))

    _, gray1, hist1 = compute_single_frame_features(f1, 0, 0.0)
    rec2, _, _ = compute_single_frame_features(
        f2,
        frame_index=1,
        timestamp_seconds=1.0,
        previous_gray=gray1,
        previous_hist=hist1,
    )

    assert rec2.is_valid is True
    assert rec2.width == 640
    assert rec2.height == 360
    assert rec2.frame_difference == 0.0


def test_portrait_frame_handling() -> None:
    """Portrait aspect ratio frames (e.g. 360x640) are processed correctly."""
    portrait = create_solid_frame(width=360, height=640)
    rec, _, _ = compute_single_frame_features(portrait, 0, 0.0)

    assert rec.is_valid is True
    assert rec.width == 360
    assert rec.height == 640


def test_extract_sequence_features() -> None:
    """extract_sequence_features processes an ordered sequence of in-memory frames."""
    f1 = create_solid_frame()
    f2 = create_action_frame()
    entries = [(f1, 0.0), (f2, 1.0)]

    records = extract_sequence_features(entries)
    assert len(records) == 2
    assert records[0].timestamp_seconds == 0.0
    assert records[1].timestamp_seconds == 1.0
    assert records[1].frame_difference > 0.0
