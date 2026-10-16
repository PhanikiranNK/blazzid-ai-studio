"""Highlight selection constraints and result contracts.

Specifies parameters and diagnostic outputs for constrained highlight selection.
"""

from __future__ import annotations

import math
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from blazzid_core.contracts.candidates import HighlightCandidate
from blazzid_core.errors import BudgetConstraintError


class SelectionConstraints(BaseModel):
    """Configuration constraints governing highlight selection and reel duration."""

    model_config = ConfigDict(frozen=True)

    target_duration_seconds: float = Field(
        ..., gt=0.0, description="Target total highlight reel duration budget in seconds."
    )
    max_overlap_ratio: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Maximum permissible pairwise overlap ratio (0.0 enforces zero overlap).",
    )
    min_clip_duration_seconds: float = Field(
        default=1.0, gt=0.0, description="Minimum allowable duration for an individual clip."
    )
    max_clip_duration_seconds: Optional[float] = Field(
        default=None, gt=0.0, description="Maximum allowable duration for an individual clip."
    )
    quantum_bin_seconds: float = Field(
        default=0.5,
        gt=0.0,
        description="Time quantization resolution (seconds) for dynamic programming knapsack.",
    )

    @model_validator(mode="after")
    def validate_duration_bounds(self) -> SelectionConstraints:
        if math.isnan(self.target_duration_seconds) or math.isinf(self.target_duration_seconds):
            raise BudgetConstraintError("target_duration_seconds must be a finite float.")
        if self.max_clip_duration_seconds is not None:
            if self.max_clip_duration_seconds < self.min_clip_duration_seconds:
                raise BudgetConstraintError(
                    f"max_clip_duration_seconds ({self.max_clip_duration_seconds}s) cannot be less "
                    f"than min_clip_duration_seconds ({self.min_clip_duration_seconds}s)."
                )
            if self.max_clip_duration_seconds > self.target_duration_seconds:
                raise BudgetConstraintError(
                    f"max_clip_duration_seconds ({self.max_clip_duration_seconds}s) cannot exceed "
                    f"target_duration_seconds ({self.target_duration_seconds}s)."
                )
        return self


class SelectionResult(BaseModel):
    """The outcome of running constrained highlight optimization over candidate intervals."""

    model_config = ConfigDict(frozen=True)

    selected_candidates: list[HighlightCandidate] = Field(
        ..., description="Subset of non-overlapping candidates maximizing total utility."
    )
    total_duration_seconds: float = Field(
        ..., ge=0.0, description="Exact sum of selected clip durations in seconds."
    )
    total_score: float = Field(..., description="Cumulative utility score of selected candidates.")
    discarded_count: int = Field(
        ..., ge=0, description="Number of candidate clips evaluated but not included."
    )
    quantum_step: float = Field(
        ..., gt=0.0, description="Quantization bin size used in discretization."
    )
    solver_diagnostics: dict[str, Any] = Field(
        default_factory=dict, description="Diagnostic metrics, e.g. DP matrix size, solve time."
    )
