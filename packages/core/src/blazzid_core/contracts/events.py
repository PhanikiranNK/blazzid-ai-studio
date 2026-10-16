"""Gameplay event candidate contracts.

Represents fused multimodal event hypotheses prior to final highlight optimization.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from blazzid_core.contracts.confidence import validate_confidence
from blazzid_core.contracts.observations import Observation
from blazzid_core.contracts.time import TimeInterval
from blazzid_core.errors import DomainValidationError


class GameplayEventType(str, Enum):
    """Categorized gameplay event types."""

    TEAM_WIPE = "TEAM_WIPE"
    CLUTCH_KILL = "CLUTCH_KILL"
    OBJECTIVE_SECURED = "OBJECTIVE_SECURED"
    SHOWDOWN_WIN = "SHOWDOWN_WIN"
    OVERTIME_STINGER = "OVERTIME_STINGER"
    GENERIC_HIGHLIGHT = "GENERIC_HIGHLIGHT"
    VISUAL_BURST = "VISUAL_BURST"
    SUSTAINED_COMBAT = "SUSTAINED_COMBAT"
    SCENE_TRANSITION = "SCENE_TRANSITION"


class GameplayEventCandidate(BaseModel):
    """A fused multimodal gameplay event candidate."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique event ID.")
    event_type: GameplayEventType = Field(..., description="Classified gameplay event type.")
    trigger_timestamp: float = Field(
        ..., ge=0.0, description="Timestamp in seconds when event was first triggered."
    )
    interval: TimeInterval = Field(
        ..., description="Expanded narrative interval [start, end) around the event."
    )
    climax_timestamp: Optional[float] = Field(
        default=None, ge=0.0, description="Point of maximum action intensity in seconds."
    )
    composite_confidence: float = Field(
        ..., description="Fused Bayesian confidence score in [0.0, 1.0]."
    )
    evidence_sources: list[Observation] = Field(
        default_factory=list, description="List of contributing detector observations."
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Game-specific contextual metadata."
    )

    @field_validator("composite_confidence")
    @classmethod
    def check_composite_confidence(cls, v: float) -> float:
        return validate_confidence(v)

    @model_validator(mode="after")
    def validate_event_timestamps(self) -> GameplayEventCandidate:
        if not self.interval.contains_timestamp(self.trigger_timestamp):
            raise DomainValidationError(
                f"Trigger timestamp {self.trigger_timestamp}s must lie within the "
                f"event interval [{self.interval.start}s, {self.interval.end}s)"
            )
        if self.climax_timestamp is not None and not self.interval.contains_timestamp(
            self.climax_timestamp
        ):
            raise DomainValidationError(
                f"Climax timestamp {self.climax_timestamp}s must lie within the "
                f"event interval [{self.interval.start}s, {self.interval.end}s)"
            )
        return self
