"""Configuration specifications for gameplay event detection."""

from __future__ import annotations

import math
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from blazzid_core.errors import DomainValidationError


class DetectionConfig(BaseModel):
    """Configurable operational parameters for gameplay event detectors.

    Controls activity thresholds, rolling statistics windows, transition sensitivities,
    and temporal candidate boundary expansion.
    """

    model_config = ConfigDict(frozen=True)

    # Narrative temporal boundaries (seconds)
    min_event_duration_seconds: float = Field(
        default=2.0, gt=0.0, description="Minimum duration for a valid candidate event."
    )
    max_event_duration_seconds: float = Field(
        default=30.0,
        gt=0.0,
        description="Maximum duration before a candidate event is capped/split.",
    )
    merge_gap_seconds: float = Field(
        default=2.0,
        ge=0.0,
        description="Maximum separation between events of same type to be merged.",
    )
    min_separation_seconds: float = Field(
        default=1.0, ge=0.0, description="Minimum temporal separation between distinct candidates."
    )
    lead_in_seconds: float = Field(
        default=1.5,
        ge=0.0,
        description="Pre-trigger narrative context added to candidate interval.",
    )
    lead_out_seconds: float = Field(
        default=1.5, ge=0.0, description="Post-climax narrative payoff added to candidate interval."
    )

    # Visual activity & burst parameters
    activity_threshold: float = Field(
        default=0.08, ge=0.0, le=1.0, description="Base visual activity threshold [0.0, 1.0]."
    )
    activity_z_score_threshold: float = Field(
        default=1.5,
        gt=0.0,
        description="Z-score above local moving baseline triggering an activity burst.",
    )
    sustained_activity_ratio: float = Field(
        default=0.12,
        ge=0.0,
        le=1.0,
        description="Minimum moving average activity for sustained combat.",
    )
    rolling_window_seconds: float = Field(
        default=10.0, gt=0.0, description="Temporal window width for moving mean/variance baseline."
    )

    # Transition detection thresholds
    transition_difference_threshold: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description="Normalized pixel difference triggering scene change.",
    )
    transition_hist_distance_threshold: float = Field(
        default=0.45,
        ge=0.0,
        le=1.0,
        description="Bhattacharyya histogram distance triggering scene change.",
    )

    # Scoring & filtering thresholds
    min_confidence_threshold: float = Field(
        default=0.25,
        ge=0.0,
        le=1.0,
        description="Minimum composite confidence for emitted candidates.",
    )

    # Version tracking for provenance
    config_version: str = Field(
        default="1.0.0", description="Semantic configuration version for audit provenance."
    )

    @field_validator(
        "min_event_duration_seconds",
        "max_event_duration_seconds",
        "merge_gap_seconds",
        "min_separation_seconds",
        "lead_in_seconds",
        "lead_out_seconds",
        "activity_threshold",
        "activity_z_score_threshold",
        "sustained_activity_ratio",
        "rolling_window_seconds",
        "transition_difference_threshold",
        "transition_hist_distance_threshold",
        "min_confidence_threshold",
    )
    @classmethod
    def validate_finite_positive(cls, v: float) -> float:
        """Validates that all numerical thresholds are finite numbers."""
        if math.isnan(v) or math.isinf(v):
            raise DomainValidationError(f"Configuration parameter must be a finite float, got {v}")
        return float(v)

    def model_post_init(self, __context: Optional[dict[str, object]]) -> None:
        """Enforces relational constraints among duration bounds."""
        if self.min_event_duration_seconds > self.max_event_duration_seconds:
            raise DomainValidationError(
                f"min_event_duration_seconds ({self.min_event_duration_seconds}s) cannot exceed "
                f"max_event_duration_seconds ({self.max_event_duration_seconds}s)"
            )
