"""BLAZZID AI Studio — Highlight Ranking, Selection & Montage Assembly."""

from __future__ import annotations

from blazzid_assembly.config import PROFILES, AssemblyConfig, RankingConfig
from blazzid_assembly.errors import (
    AssemblyError,
    AssemblyRenderError,
    OutputValidationError,
    PlanningError,
    RankingError,
)
from blazzid_assembly.models import (
    AssemblyProfile,
    AssemblyResult,
    EditManifest,
    EditPlan,
    ExclusionReason,
    ExclusionRecord,
    PlannedClip,
    ProfileConfig,
    RankedCandidate,
    ValidationReport,
)
from blazzid_assembly.pipeline import HighlightAssemblyPipeline
from blazzid_assembly.planning import plan_edit_decision_list
from blazzid_assembly.ranking import rank_gameplay_candidates
from blazzid_assembly.rendering import render_montage
from blazzid_assembly.selection import select_budgeted_highlights
from blazzid_assembly.validation import validate_rendered_montage

__version__ = "0.1.0"

__all__ = [
    "AssemblyConfig",
    "AssemblyError",
    "AssemblyProfile",
    "AssemblyRenderError",
    "AssemblyResult",
    "EditManifest",
    "EditPlan",
    "ExclusionReason",
    "ExclusionRecord",
    "HighlightAssemblyPipeline",
    "OutputValidationError",
    "PlannedClip",
    "PlanningError",
    "ProfileConfig",
    "PROFILES",
    "RankedCandidate",
    "RankingConfig",
    "RankingError",
    "ValidationReport",
    "plan_edit_decision_list",
    "rank_gameplay_candidates",
    "render_montage",
    "select_budgeted_highlights",
    "validate_rendered_montage",
]
