"""Observation domain contracts.

Represents raw detector outputs from individual modalities (Audio, Visual, OCR, Speech)
with explicit evidence provenance.
"""

from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from blazzid_core.contracts.confidence import validate_confidence
from blazzid_core.contracts.time import TimeInterval


class Modality(str, Enum):
    """Supported detection modalities."""

    AUDIO = "AUDIO"
    VISUAL = "VISUAL"
    OCR = "OCR"
    SPEECH = "SPEECH"


class ObservationProvenance(BaseModel):
    """Audit metadata tracking the origin, model, and raw features of an observation."""

    model_config = ConfigDict(frozen=True)

    detector_name: str = Field(..., min_length=1, description="Identifier of the detector.")
    detector_version: str = Field(default="1.0.0", description="Semver of the algorithm or model.")
    raw_features: dict[str, Any] = Field(
        default_factory=dict, description="Raw detector outputs, e.g. z-score, bounding box."
    )
    notes: Optional[str] = Field(default=None, description="Human or algorithmic remarks.")


class Observation(BaseModel):
    """An individual detector observation with interval, confidence, and provenance."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique observation ID.")
    modality: Modality = Field(..., description="Modality of origin.")
    interval: TimeInterval = Field(..., description="Half-open observation interval [start, end).")
    confidence: float = Field(..., description="Calibrated confidence score in [0.0, 1.0].")
    provenance: ObservationProvenance = Field(
        ..., description="Provenance metadata identifying source detector."
    )

    @field_validator("confidence")
    @classmethod
    def check_confidence(cls, v: float) -> float:
        return validate_confidence(v)
