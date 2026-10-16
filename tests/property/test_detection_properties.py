"""Hypothesis property-based tests for gameplay event candidate invariants."""

from __future__ import annotations

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st

from blazzid_detection.config import DetectionConfig
from blazzid_detection.detector import GameplayEventDetector
from tests.fixtures.synthetic_gameplay import create_action_frame, create_solid_frame


@settings(max_examples=25, deadline=5000)
@given(
    action_start=st.floats(min_value=5.0, max_value=15.0),
    action_duration=st.floats(min_value=2.0, max_value=8.0),
    source_duration=st.floats(min_value=30.0, max_value=60.0),
)
def test_candidate_intervals_and_timestamp_containment_invariants(
    action_start: float,
    action_duration: float,
    source_duration: float,
) -> None:
    """Property: All generated candidates obey half-open bounds and containment invariants:

    1. 0.0 <= cand.interval.start < cand.interval.end <= source_duration
    2. cand.interval.start <= cand.trigger_timestamp < cand.interval.end
    3. cand.interval.start <= cand.climax_timestamp < cand.interval.end (if present)
    4. 0.0 <= cand.composite_confidence <= 1.0
    """
    action_end = action_start + action_duration
    entries: list[tuple[np.ndarray[int, np.dtype[np.uint8]], float]] = []

    # Sample at 1 fps
    timestamps = list(np.arange(0.0, source_duration, 1.0))
    for idx, t in enumerate(timestamps):
        if action_start <= t <= action_end:
            frame = create_action_frame(intensity=0.8, seed=idx + 1)
        else:
            frame = create_solid_frame()
        entries.append((frame, float(t)))

    detector = GameplayEventDetector(config=DetectionConfig())
    res = detector.detect(entries, source_duration_seconds=source_duration)

    assert res.is_success is True
    for cand in res.candidates:
        # Invariant 1: Temporal boundary containment
        assert 0.0 <= cand.interval.start < cand.interval.end <= (source_duration + 1e-4)

        # Invariant 2: Trigger timestamp containment
        assert cand.interval.contains_timestamp(cand.trigger_timestamp)

        # Invariant 3: Climax timestamp containment
        if cand.climax_timestamp is not None:
            assert cand.interval.contains_timestamp(cand.climax_timestamp)

        # Invariant 4: Confidence bounds
        assert 0.0 <= cand.composite_confidence <= 1.0
        assert len(cand.evidence_sources) >= 1
