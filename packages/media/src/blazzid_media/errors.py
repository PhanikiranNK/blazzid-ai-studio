"""Structured errors and exceptions for media ingestion and preprocessing."""

from __future__ import annotations

from blazzid_core.errors import BlazzidError


class MediaError(BlazzidError):
    """Base exception for all media processing operations."""


class MediaInputError(MediaError, ValueError):
    """Raised when an input media file is invalid, missing, unreadable, or out of bounds."""


class ProbeError(MediaError):
    """Raised when ffprobe execution or metadata parsing fails."""


class MissingVideoStreamError(ProbeError):
    """Raised when media contains no usable video stream."""


class PreprocessingError(MediaError):
    """Raised when FFmpeg preprocessing or extraction fails."""


class AudioExtractionError(PreprocessingError):
    """Raised when audio extraction from media stream fails."""


class FrameExtractionError(MediaError):
    """Raised when video decoding or frame extraction fails."""


class WaveformError(MediaError):
    """Raised when audio decoding or waveform generation fails."""
