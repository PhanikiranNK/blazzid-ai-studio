"""Data models and schemas for highlight ranking, selection, and assembly."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from blazzid_core.contracts.candidates import HighlightCandidate
from blazzid_core.contracts.time import TimeInterval


class AssemblyProfile(str, Enum):
    """Predefined output video profiles."""

    PORTRAIT_9_16 = "PORTRAIT_9_16"
    LANDSCAPE_16_9 = "LANDSCAPE_16_9"
    DEV_PORTRAIT = "DEV_PORTRAIT"
    DEV_LANDSCAPE = "DEV_LANDSCAPE"


class ProfileConfig(BaseModel):
    """Detailed encoding, canvas, and format specification for an assembly profile."""

    model_config = ConfigDict(frozen=True)

    name: AssemblyProfile = Field(..., description="Assembly profile identifier.")
    width: int = Field(..., gt=0, description="Target canvas width in pixels.")
    height: int = Field(..., gt=0, description="Target canvas height in pixels.")
    fps: float = Field(default=30.0, gt=0.0, description="Target frames per second.")
    video_codec: str = Field(default="libx264", description="Video encoder codec.")
    crf: int = Field(default=22, ge=0, le=51, description="H.264 Constant Rate Factor.")
    pixel_format: str = Field(default="yuv420p", description="Standard 8-bit YUV pixel format.")
    audio_codec: str = Field(default="aac", description="Audio encoder codec.")
    audio_sample_rate: int = Field(default=44100, gt=0, description="Audio sampling rate (Hz).")
    audio_channels: int = Field(default=2, ge=1, le=8, description="Number of audio channels.")
    aspect_fit_policy: str = Field(
        default="pad",
        description="Aspect ratio fitting policy: 'pad' (letterbox/pillarbox) or 'crop' (center crop).",
    )


class ExclusionReason(str, Enum):
    """Categorized explanation for excluding a candidate from the highlight edit plan."""

    DURATION_TOO_SHORT = "DURATION_TOO_SHORT"
    DURATION_EXCEEDS_BUDGET = "DURATION_EXCEEDS_BUDGET"
    OVERLAPS_SUPERIOR_CANDIDATE = "OVERLAPS_SUPERIOR_CANDIDATE"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    MAX_CLIPS_REACHED = "MAX_CLIPS_REACHED"
    INSUFFICIENT_SEPARATION = "INSUFFICIENT_SEPARATION"
    SOURCE_BOUNDARY_CUTOFF = "SOURCE_BOUNDARY_CUTOFF"


class ExclusionRecord(BaseModel):
    """Structured audit record describing why a candidate was not selected."""

    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(..., description="Excluded candidate ID.")
    reason: ExclusionReason = Field(..., description="Categorized exclusion reason.")
    details: str = Field(..., description="Human-readable explanation of exclusion.")


class RankedCandidate(BaseModel):
    """A scored highlight candidate enriched with ranking position and explanations."""

    model_config = ConfigDict(frozen=True)

    candidate: HighlightCandidate = Field(..., description="Underlying highlight candidate.")
    rank_index: int = Field(..., ge=1, description="1-based priority ranking rank.")
    event_type: str = Field(..., description="Underlying gameplay event type.")
    climax_timestamp: Optional[float] = Field(
        default=None, description="Climax timestamp in seconds."
    )
    trigger_timestamp: float = Field(..., description="Event trigger timestamp in seconds.")
    scoring_explanation: str = Field(
        ..., description="Narrative summary of evidence and scoring factors."
    )


class PlannedClip(BaseModel):
    """An individual video segment planned for extraction and concatenation."""

    model_config = ConfigDict(frozen=True)

    clip_index: int = Field(..., ge=0, description="Sequential 0-based order in final montage.")
    clip_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique clip ID.")
    candidate_id: str = Field(..., description="Reference to parent candidate ID.")
    source_interval: TimeInterval = Field(
        ..., description="Half-open source interval [start, end) to extract."
    )
    montage_interval: TimeInterval = Field(
        ..., description="Planned timeline placement [start, end) in output montage."
    )
    climax_timestamp: Optional[float] = Field(
        default=None, description="Peak action timestamp relative to source."
    )
    rank_score: float = Field(..., description="Rank score of contributing candidate.")
    category: str = Field(..., description="Highlight category.")
    selection_rationale: str = Field(..., description="Explainable selection justification.")

    @property
    def duration(self) -> float:
        return self.source_interval.duration


class EditPlan(BaseModel):
    """A validated, duration-budgeted sequence of clips ready for rendering."""

    model_config = ConfigDict(frozen=True)

    clips: list[PlannedClip] = Field(..., description="Ordered list of clips to concatenate.")
    total_duration_seconds: float = Field(
        ..., ge=0.0, description="Sum of planned clip durations in seconds."
    )
    target_budget_seconds: float = Field(..., gt=0.0, description="Requested target reel duration.")
    budget_shortfall_seconds: float = Field(
        ..., ge=0.0, description="Unfilled duration budget in seconds."
    )
    selected_count: int = Field(..., ge=0, description="Number of selected clips.")
    excluded_candidates: list[ExclusionRecord] = Field(
        default_factory=list, description="Audit of all evaluated but excluded candidates."
    )


class ValidationReport(BaseModel):
    """Post-rendering verification metrics and health check results."""

    model_config = ConfigDict(frozen=True)

    is_valid: bool = Field(..., description="Whether rendered video satisfies all quality gates.")
    output_path: Path = Field(..., description="Filesystem path to rendered video file.")
    container_format: str = Field(..., description="Probed container format (e.g. mov,mp4).")
    has_video: bool = Field(..., description="Whether a valid video stream is present.")
    has_audio: bool = Field(..., description="Whether an audio stream is present.")
    width: int = Field(..., ge=0, description="Measured frame width in pixels.")
    height: int = Field(..., ge=0, description="Measured frame height in pixels.")
    fps: float = Field(default=0.0, ge=0.0, description="Measured frame rate.")
    actual_duration_seconds: float = Field(
        ..., ge=0.0, description="Probed container duration in seconds."
    )
    planned_duration_seconds: float = Field(
        ..., ge=0.0, description="Expected duration from EditPlan."
    )
    duration_difference_seconds: float = Field(
        ..., ge=0.0, description="Absolute difference between actual and planned duration."
    )
    checks_passed: list[str] = Field(
        default_factory=list, description="List of passed validation checks."
    )
    errors: list[str] = Field(
        default_factory=list, description="List of validation failures or errors."
    )
    warnings: list[str] = Field(
        default_factory=list, description="Non-fatal warnings or anomalies."
    )


class EditManifest(BaseModel):
    """Complete machine-readable JSON manifest recording all assembly provenance."""

    model_config = ConfigDict(frozen=True)

    manifest_version: str = Field(
        default="1.0.0", description="Semantic version of the manifest schema."
    )
    source_media_path: str = Field(..., description="Path or identifier of source media file.")
    source_duration_seconds: float = Field(
        ..., ge=0.0, description="Duration of source video in seconds."
    )
    ranking_config_version: str = Field(
        ..., description="Identifier or version of ranking configuration."
    )
    selection_constraints: dict[str, Any] = Field(
        default_factory=dict, description="Constraints applied during interval selection."
    )
    ranked_candidates: list[dict[str, Any]] = Field(
        default_factory=list, description="All ranked candidates with scoring breakdowns."
    )
    selected_candidates: list[dict[str, Any]] = Field(
        default_factory=list, description="Selected candidate intervals and scores."
    )
    excluded_candidates: list[dict[str, Any]] = Field(
        default_factory=list, description="Excluded candidates with reasons."
    )
    planned_clips: list[dict[str, Any]] = Field(
        default_factory=list, description="Planned clip sequence and timeline offsets."
    )
    rendering_profile: dict[str, Any] = Field(
        default_factory=dict, description="Video/audio profile settings used during render."
    )
    output_path: str = Field(..., description="Destination path of the rendered montage.")
    validation: dict[str, Any] = Field(
        default_factory=dict, description="Summary of post-render probe validation."
    )
    stage_durations: dict[str, float] = Field(
        default_factory=dict, description="Wall-clock elapsed seconds per assembly stage."
    )
    warnings: list[str] = Field(default_factory=list, description="Pipeline warnings.")


class AssemblyResult(BaseModel):
    """Final output from the highlight assembly pipeline."""

    model_config = ConfigDict(frozen=True)

    is_success: bool = Field(..., description="Whether assembly and rendering succeeded.")
    output_video_path: Optional[Path] = Field(
        default=None, description="Path to rendered output video file."
    )
    manifest_path: Optional[Path] = Field(
        default=None, description="Path to companion JSON edit manifest."
    )
    edit_plan: EditPlan = Field(..., description="Edit plan executed for this assembly.")
    validation_report: Optional[ValidationReport] = Field(
        default=None, description="Output validation findings."
    )
    manifest: Optional[EditManifest] = Field(
        default=None, description="Machine-readable edit manifest."
    )
    error_message: Optional[str] = Field(
        default=None, description="Error message if assembly failed."
    )
