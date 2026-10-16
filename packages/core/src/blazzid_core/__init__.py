"""BLAZZID Core domain package."""

from blazzid_core.contracts import (
    GameplayEventCandidate,
    GameplayEventType,
    HighlightCandidate,
    Modality,
    Observation,
    ObservationProvenance,
    SelectionConstraints,
    SelectionResult,
    TimeInterval,
    validate_confidence,
)
from blazzid_core.errors import (
    AlgorithmExecutionError,
    BlazzidError,
    BudgetConstraintError,
    DomainValidationError,
    IntervalError,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "BlazzidError",
    "DomainValidationError",
    "IntervalError",
    "BudgetConstraintError",
    "AlgorithmExecutionError",
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
