"""Configuration models and predefined encoding profiles for assembly."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from blazzid_assembly.models import AssemblyProfile, ProfileConfig
from blazzid_core.errors import BudgetConstraintError

# Predefined profile presets
PROFILES: dict[AssemblyProfile, ProfileConfig] = {
    AssemblyProfile.LANDSCAPE_16_9: ProfileConfig(
        name=AssemblyProfile.LANDSCAPE_16_9,
        width=1920,
        height=1080,
        fps=30.0,
        video_codec="libx264",
        crf=22,
        pixel_format="yuv420p",
        audio_codec="aac",
        audio_sample_rate=44100,
        audio_channels=2,
        aspect_fit_policy="pad",
    ),
    AssemblyProfile.PORTRAIT_9_16: ProfileConfig(
        name=AssemblyProfile.PORTRAIT_9_16,
        width=1080,
        height=1920,
        fps=30.0,
        video_codec="libx264",
        crf=22,
        pixel_format="yuv420p",
        audio_codec="aac",
        audio_sample_rate=44100,
        audio_channels=2,
        aspect_fit_policy="pad",
    ),
    AssemblyProfile.DEV_LANDSCAPE: ProfileConfig(
        name=AssemblyProfile.DEV_LANDSCAPE,
        width=640,
        height=360,
        fps=30.0,
        video_codec="libx264",
        crf=24,
        pixel_format="yuv420p",
        audio_codec="aac",
        audio_sample_rate=44100,
        audio_channels=2,
        aspect_fit_policy="pad",
    ),
    AssemblyProfile.DEV_PORTRAIT: ProfileConfig(
        name=AssemblyProfile.DEV_PORTRAIT,
        width=360,
        height=640,
        fps=30.0,
        video_codec="libx264",
        crf=24,
        pixel_format="yuv420p",
        audio_codec="aac",
        audio_sample_rate=44100,
        audio_channels=2,
        aspect_fit_policy="pad",
    ),
}


class RankingConfig(BaseModel):
    """Heuristic weights and penalty configuration for candidate scoring."""

    model_config = ConfigDict(frozen=True)

    version: str = Field(default="ranking_v1.0", description="Ranking algorithm version.")
    confidence_weight: float = Field(
        default=0.40, ge=0.0, le=1.0, description="Weight for candidate composite confidence."
    )
    consensus_weight: float = Field(
        default=0.25, ge=0.0, le=1.0, description="Weight for multi-detector consensus."
    )
    intensity_weight: float = Field(
        default=0.20, ge=0.0, le=1.0, description="Weight for peak visual activity/climax."
    )
    duration_weight: float = Field(
        default=0.15, ge=0.0, le=1.0, description="Weight for sustained event persistence."
    )
    category_multipliers: dict[str, float] = Field(
        default_factory=lambda: {
            "SUSTAINED_COMBAT": 1.0,
            "VISUAL_BURST": 0.95,
            "TEAM_WIPE": 1.0,
            "CLUTCH_KILL": 1.0,
            "GENERIC_HIGHLIGHT": 0.70,
            "SCENE_TRANSITION": 0.30,
        },
        description="Category utility multipliers.",
    )
    min_confidence: float = Field(
        default=0.20, ge=0.0, le=1.0, description="Minimum confidence to qualify for ranking."
    )
    boundary_penalty_seconds: float = Field(
        default=2.0, ge=0.0, description="Margin near recording boundaries penalized for cutoff."
    )
    boundary_penalty_factor: float = Field(
        default=0.15, ge=0.0, le=1.0, description="Fraction deducted when clip touches boundary."
    )


class AssemblyConfig(BaseModel):
    """Configuration governing highlight selection, planning, and rendering."""

    model_config = ConfigDict(frozen=True)

    profile: AssemblyProfile = Field(
        default=AssemblyProfile.LANDSCAPE_16_9, description="Target output rendering profile."
    )
    target_duration_seconds: float = Field(
        default=30.0, gt=0.0, description="Target total duration budget for the highlight reel."
    )
    min_clip_duration_seconds: float = Field(
        default=2.0, gt=0.0, description="Minimum duration for an individual clip."
    )
    max_clip_duration_seconds: Optional[float] = Field(
        default=None, gt=0.0, description="Maximum duration for an individual clip."
    )
    max_clips_count: Optional[int] = Field(
        default=None, gt=0, description="Maximum allowable number of clips in reel."
    )
    lead_in_padding_seconds: float = Field(
        default=0.5, ge=0.0, description="Context lead-in padding added to candidate start."
    )
    lead_out_padding_seconds: float = Field(
        default=0.5, ge=0.0, description="Context lead-out padding added to candidate end."
    )
    quantum_bin_seconds: float = Field(
        default=0.5, gt=0.0, description="Quantization bin size for interval scheduling DP."
    )
    min_separation_seconds: float = Field(
        default=0.0, ge=0.0, description="Minimum gap required between distinct clip intervals."
    )
    ranking_config: RankingConfig = Field(
        default_factory=RankingConfig, description="Candidate ranking configuration."
    )
    work_dir: Optional[Path] = Field(
        default=None, description="Working directory for temporary clips and manifest."
    )
    timeout_seconds: int = Field(
        default=300, gt=0, description="Timeout for external FFmpeg render operations."
    )
    keep_intermediate_clips: bool = Field(
        default=False, description="Whether to retain per-clip video segments after assembly."
    )
    expand_to_budget: bool = Field(
        default=False,
        description="Whether to expand clip context padding to fulfill the target duration budget.",
    )
    auto_zoom: bool = Field(
        default=False,
        description="Whether to apply dynamic action cam punch-in zoom during combat climaxes.",
    )
    meme_overlays: bool = Field(
        default=False,
        description="Whether to render viral gaming reaction stickers at climax timestamps.",
    )
    soundtrack: Optional[str] = Field(
        default=None,
        description="Optional trending soundtrack style ('phonk', 'cyber', 'trap', or None).",
    )

    @model_validator(mode="after")
    def validate_durations(self) -> AssemblyConfig:
        if math.isnan(self.target_duration_seconds) or math.isinf(self.target_duration_seconds):
            raise BudgetConstraintError("target_duration_seconds must be a finite float.")
        if self.max_clip_duration_seconds is not None:
            if self.max_clip_duration_seconds < self.min_clip_duration_seconds:
                raise BudgetConstraintError(
                    f"max_clip_duration_seconds ({self.max_clip_duration_seconds}s) cannot be less "
                    f"than min_clip_duration_seconds ({self.min_clip_duration_seconds}s)."
                )
            if self.max_clip_duration_seconds > self.target_duration_seconds:
                object.__setattr__(self, "max_clip_duration_seconds", self.target_duration_seconds)
        return self

    def get_profile_config(self) -> ProfileConfig:
        """Returns the ProfileConfig corresponding to the configured profile preset."""
        return PROFILES[self.profile]
