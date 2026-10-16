"""Contract exports for blazzid_core."""

from blazzid_core.contracts.candidates import HighlightCandidate
from blazzid_core.contracts.confidence import validate_confidence
from blazzid_core.contracts.events import GameplayEventCandidate, GameplayEventType
from blazzid_core.contracts.observations import Modality, Observation, ObservationProvenance
from blazzid_core.contracts.selection import SelectionConstraints, SelectionResult
from blazzid_core.contracts.time import TimeInterval

__all__ = [
    "TimeInterval",
    "validate_confidence",
    "Modality",
    "ObservationProvenance",
    "Observation",
    "GameplayEventType",
    "GameplayEventCandidate",
    "HighlightCandidate",
    "SelectionConstraints",
    "SelectionResult",
]
