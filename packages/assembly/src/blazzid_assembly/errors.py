"""Domain exceptions for highlight assembly and rendering."""

from __future__ import annotations

from blazzid_core.errors import BlazzidError


class AssemblyError(BlazzidError):
    """Base exception for all assembly, planning, and rendering errors."""


class RankingError(AssemblyError):
    """Raised when candidate ranking fails due to invalid data."""


class PlanningError(AssemblyError):
    """Raised when clip boundary planning fails."""


class AssemblyRenderError(AssemblyError):
    """Raised when FFmpeg clip extraction or montage rendering fails."""


class OutputValidationError(AssemblyError):
    """Raised when post-render verification detects an invalid video artifact."""
