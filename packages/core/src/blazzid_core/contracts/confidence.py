"""Confidence score domain contract.

All confidence scores are calibrated probabilities strictly bounded in [0.0, 1.0].
"""

import math

from blazzid_core.errors import DomainValidationError


def validate_confidence(value: float) -> float:
    """Validates that a confidence value is a finite float in [0.0, 1.0]."""
    if math.isnan(value) or math.isinf(value):
        raise DomainValidationError(f"Confidence score must be a finite float, got {value}")
    if not 0.0 <= value <= 1.0:
        raise DomainValidationError(
            f"Confidence score must be normalized in range [0.0, 1.0], got {value}"
        )
    return float(value)
