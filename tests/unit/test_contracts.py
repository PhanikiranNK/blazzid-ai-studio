"""Unit tests for blazzid_core domain contracts and models."""

import pytest
from pydantic import ValidationError

from blazzid_core.contracts import (
    GameplayEventCandidate,
    GameplayEventType,
    HighlightCandidate,
    Modality,
    Observation,
    ObservationProvenance,
    SelectionConstraints,
    TimeInterval,
    validate_confidence,
)
from blazzid_core.errors import BudgetConstraintError, DomainValidationError, IntervalError


class TestTimeInterval:
    def test_valid_interval(self) -> None:
        interval = TimeInterval(start=10.5, end=20.0)
        assert interval.start == 10.5
        assert interval.end == 20.0
        assert pytest.approx(interval.duration) == 9.5

    def test_reject_start_greater_than_end(self) -> None:
        with pytest.raises(
            (ValidationError, IntervalError), match="must be strictly greater than start"
        ):
            TimeInterval(start=15.0, end=10.0)

    def test_reject_zero_duration_interval(self) -> None:
        with pytest.raises(
            (ValidationError, IntervalError), match="must be strictly greater than start"
        ):
            TimeInterval(start=5.0, end=5.0)

    def test_reject_negative_start(self) -> None:
        with pytest.raises((ValidationError, IntervalError), match="cannot be negative"):
            TimeInterval(start=-1.0, end=5.0)

    def test_reject_nan_and_inf(self) -> None:
        with pytest.raises((ValidationError, IntervalError), match="must be a finite float"):
            TimeInterval(start=float("nan"), end=10.0)
        with pytest.raises((ValidationError, IntervalError), match="must be a finite float"):
            TimeInterval(start=0.0, end=float("inf"))

    def test_overlaps_half_open_semantics(self) -> None:
        # [0, 5) and [5, 10) share a boundary point at 5, but are disjoint
        a = TimeInterval(start=0.0, end=5.0)
        b = TimeInterval(start=5.0, end=10.0)
        assert not a.overlaps(b)
        assert not b.overlaps(a)
        assert a.overlap_duration(b) == 0.0

        # [0, 5.1) and [5.0, 10.0) overlap on [5.0, 5.1)
        c = TimeInterval(start=0.0, end=5.1)
        d = TimeInterval(start=5.0, end=10.0)
        assert c.overlaps(d)
        assert d.overlaps(c)
        assert pytest.approx(c.overlap_duration(d)) == 0.1

        # Completely nested
        outer = TimeInterval(start=0.0, end=20.0)
        inner = TimeInterval(start=5.0, end=15.0)
        assert outer.overlaps(inner)
        assert outer.contains_interval(inner)
        assert not inner.contains_interval(outer)

    def test_intersection(self) -> None:
        a = TimeInterval(start=2.0, end=8.0)
        b = TimeInterval(start=5.0, end=12.0)
        inter = a.intersection(b)
        assert inter is not None
        assert inter.start == 5.0
        assert inter.end == 8.0

        # Disjoint intersection
        c = TimeInterval(start=10.0, end=15.0)
        assert a.intersection(c) is None

    def test_contains_timestamp(self) -> None:
        interval = TimeInterval(start=10.0, end=20.0)
        assert not interval.contains_timestamp(9.999)
        assert interval.contains_timestamp(10.0)
        assert interval.contains_timestamp(15.0)
        assert interval.contains_timestamp(19.999)
        assert not interval.contains_timestamp(20.0)  # half-open [10, 20)
        assert not interval.contains_timestamp(float("nan"))


class TestConfidenceValidation:
    def test_valid_confidence(self) -> None:
        assert validate_confidence(0.0) == 0.0
        assert validate_confidence(0.5) == 0.5
        assert validate_confidence(1.0) == 1.0

    def test_reject_out_of_bounds(self) -> None:
        with pytest.raises(DomainValidationError, match="range \\[0.0, 1.0\\]"):
            validate_confidence(-0.01)
        with pytest.raises(DomainValidationError, match="range \\[0.0, 1.0\\]"):
            validate_confidence(1.001)

    def test_reject_nan_inf(self) -> None:
        with pytest.raises(DomainValidationError, match="finite float"):
            validate_confidence(float("nan"))
        with pytest.raises(DomainValidationError, match="finite float"):
            validate_confidence(float("inf"))


class TestObservationContract:
    def test_valid_observation(self) -> None:
        provenance = ObservationProvenance(
            detector_name="AudioEnergyDetector",
            detector_version="1.2.0",
            raw_features={"rms_db": -12.4, "z_score": 3.8},
        )
        obs = Observation(
            modality=Modality.AUDIO,
            interval=TimeInterval(start=100.0, end=105.0),
            confidence=0.88,
            provenance=provenance,
        )
        assert obs.modality == Modality.AUDIO
        assert obs.confidence == 0.88
        assert obs.provenance.detector_name == "AudioEnergyDetector"

    def test_invalid_observation_confidence(self) -> None:
        provenance = ObservationProvenance(detector_name="TestDetector")
        with pytest.raises(ValidationError):
            Observation(
                modality=Modality.VISUAL,
                interval=TimeInterval(start=1.0, end=2.0),
                confidence=1.5,
                provenance=provenance,
            )


class TestGameplayEventCandidateContract:
    def test_valid_gameplay_event(self) -> None:
        interval = TimeInterval(start=50.0, end=65.0)
        event = GameplayEventCandidate(
            event_type=GameplayEventType.TEAM_WIPE,
            trigger_timestamp=58.0,
            interval=interval,
            climax_timestamp=60.0,
            composite_confidence=0.95,
        )
        assert event.event_type == GameplayEventType.TEAM_WIPE
        assert event.composite_confidence == 0.95

    def test_reject_trigger_outside_interval(self) -> None:
        interval = TimeInterval(start=50.0, end=60.0)
        with pytest.raises(
            (ValidationError, DomainValidationError), match="Trigger timestamp.*must lie within"
        ):
            GameplayEventCandidate(
                event_type=GameplayEventType.CLUTCH_KILL,
                trigger_timestamp=65.0,  # outside [50, 60)
                interval=interval,
                composite_confidence=0.9,
            )

    def test_reject_climax_outside_interval(self) -> None:
        interval = TimeInterval(start=50.0, end=60.0)
        with pytest.raises(
            (ValidationError, DomainValidationError), match="Climax timestamp.*must lie within"
        ):
            GameplayEventCandidate(
                event_type=GameplayEventType.CLUTCH_KILL,
                trigger_timestamp=55.0,
                interval=interval,
                climax_timestamp=45.0,  # outside [50, 60)
                composite_confidence=0.9,
            )


class TestHighlightCandidateContract:
    def test_valid_candidate(self) -> None:
        cand = HighlightCandidate(
            candidate_id="cand-001",
            interval=TimeInterval(start=12.0, end=20.0),
            rank_score=94.5,
            confidence=0.92,
            category="TEAM_WIPE",
        )
        assert cand.duration == 8.0
        assert cand.rank_score == 94.5
        assert cand.confidence == 0.92

    def test_reject_nan_score(self) -> None:
        with pytest.raises((ValidationError, DomainValidationError)):
            HighlightCandidate(
                candidate_id="cand-002",
                interval=TimeInterval(start=10.0, end=15.0),
                rank_score=float("nan"),
                confidence=0.8,
            )


class TestSelectionConstraintsContract:
    def test_valid_constraints(self) -> None:
        c = SelectionConstraints(
            target_duration_seconds=180.0,
            min_clip_duration_seconds=5.0,
            max_clip_duration_seconds=20.0,
            quantum_bin_seconds=0.5,
        )
        assert c.target_duration_seconds == 180.0
        assert c.max_clip_duration_seconds == 20.0

    def test_reject_max_clip_less_than_min_clip(self) -> None:
        with pytest.raises(
            (ValidationError, BudgetConstraintError), match="cannot be less than min_clip_duration"
        ):
            SelectionConstraints(
                target_duration_seconds=180.0,
                min_clip_duration_seconds=15.0,
                max_clip_duration_seconds=10.0,
            )

    def test_reject_max_clip_greater_than_target(self) -> None:
        with pytest.raises(
            (ValidationError, BudgetConstraintError), match="cannot exceed target_duration"
        ):
            SelectionConstraints(
                target_duration_seconds=60.0,
                max_clip_duration_seconds=75.0,
            )
