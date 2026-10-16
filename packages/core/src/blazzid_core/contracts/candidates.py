"""Highlight candidate contracts.

Represents ranked video intervals evaluated for inclusion in the final highlight reel.
"""

import math
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from blazzid_core.contracts.confidence import validate_confidence
from blazzid_core.contracts.time import TimeInterval
from blazzid_core.errors import DomainValidationError


class HighlightCandidate(BaseModel):
    """An individual highlight candidate interval with utility rank score and metadata."""

    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(
        default_factory=lambda: str(uuid4()), description="Unique candidate ID."
    )
    event_id: Optional[str] = Field(
        default=None, description="Reference to parent GameplayEventCandidate."
    )
    interval: TimeInterval = Field(
        ..., description="Half-open temporal window [start, end) of the clip."
    )
    rank_score: float = Field(
        ..., description="Composite utility score used for optimization (finite float)."
    )
    confidence: float = Field(..., description="Calibrated confidence probability in [0.0, 1.0].")
    category: str = Field(default="HIGHLIGHT", description="Category or tag of the highlight play.")
    scoring_breakdown: dict[str, float] = Field(
        default_factory=dict, description="Feature contribution sub-scores."
    )
    is_selected: bool = Field(
        default=False, description="Whether selected into active Edit Decision List."
    )

    @field_validator("confidence")
    @classmethod
    def check_confidence(cls, v: float) -> float:
        return validate_confidence(v)

    @field_validator("rank_score")
    @classmethod
    def check_rank_score(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            raise DomainValidationError(f"Rank score must be a finite float, got {v}")
        return float(v)

    @property
    def duration(self) -> float:
        """Convenience property returning interval duration in seconds."""
        return self.interval.duration
