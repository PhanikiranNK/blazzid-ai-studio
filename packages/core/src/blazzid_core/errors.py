"""Core domain errors and exceptions for BLAZZID AI Studio."""

from typing import Optional


class BlazzidError(Exception):
    """Base exception for all BLAZZID platform errors."""

    def __init__(self, message: str, details: Optional[dict[str, object]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class DomainValidationError(BlazzidError, ValueError):
    """Raised when domain constraints or invariants are violated."""


class IntervalError(DomainValidationError):
    """Raised when temporal interval bounds or semantics are invalid."""


class BudgetConstraintError(DomainValidationError):
    """Raised when duration budget parameters are invalid."""


class AlgorithmExecutionError(BlazzidError):
    """Raised when an algorithm encounters an unexpected execution state."""
