"""Validated data models and contract definitions for media processing."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class FrameRateMode(str, Enum):
    """Classification of video stream temporal pacing."""

    CFR = "CFR"  # Constant frame rate
    VFR = "VFR"  # Variable frame rate
    UNKNOWN = "UNKNOWN"  # Insufficient or conflicting evidence


class VideoStreamMetadata(BaseModel):
    """Detailed metadata for a validated video stream."""

    model_config = ConfigDict(frozen=True)

    index: int = Field(..., ge=0, description="Stream index in container.")
    codec_name: str = Field(..., description="FFmpeg codec identifier (e.g. h264, hevc).")
    profile: Optional[str] = Field(default=None, description="Codec profile name.")
    width: int = Field(..., gt=0, description="Coded frame width in pixels.")
    height: int = Field(..., gt=0, description="Coded frame height in pixels.")
    pixel_format: str = Field(..., description="Chroma pixel format (e.g. yuv420p).")
    avg_frame_rate: Optional[float] = Field(
        default=None, gt=0.0, description="Reported average frame rate (fps)."
    )
    r_frame_rate: Optional[float] = Field(
        default=None, gt=0.0, description="Reported base/real frame rate (fps)."
    )
    time_base: Optional[str] = Field(
        default=None, description="Elementary stream time base (e.g. 1/30000)."
    )
    frame_count: Optional[int] = Field(
        default=None, ge=0, description="Total frame count if indexed."
    )
    duration_seconds: Optional[float] = Field(
        default=None, ge=0.0, description="Stream duration in seconds."
    )
    start_time_seconds: Optional[float] = Field(
        default=None, description="Stream presentation start offset."
    )
    sample_aspect_ratio: Optional[str] = Field(
        default=None, description="Pixel aspect ratio (SAR)."
    )
    display_aspect_ratio: Optional[str] = Field(
        default=None, description="Display aspect ratio (DAR)."
    )
    rotation: Optional[int] = Field(
        default=None, description="Display orientation rotation degrees."
    )
    frame_rate_mode: FrameRateMode = Field(
        default=FrameRateMode.UNKNOWN, description="CFR/VFR temporal pacing classification."
    )


class AudioStreamMetadata(BaseModel):
    """Detailed metadata for an audio stream."""

    model_config = ConfigDict(frozen=True)

    index: int = Field(..., ge=0, description="Stream index in container.")
    codec_name: str = Field(..., description="Audio codec identifier (e.g. aac, opus, pcm_s16le).")
    sample_rate: int = Field(..., gt=0, description="Audio sample frequency in Hz.")
    channels: int = Field(..., gt=0, description="Number of audio channels.")
    channel_layout: Optional[str] = Field(
        default=None, description="Channel layout name (e.g. stereo, mono)."
    )
    duration_seconds: Optional[float] = Field(
        default=None, ge=0.0, description="Audio stream duration in seconds."
    )
    start_time_seconds: Optional[float] = Field(
        default=None, description="Audio presentation start offset."
    )


class ContainerMetadata(BaseModel):
    """Container-level inspection information."""

    model_config = ConfigDict(frozen=True)

    format_name: str = Field(..., description="Short format identifier (e.g. mov,mp4,m4a).")
    format_long_name: Optional[str] = Field(default=None, description="Descriptive container name.")
    duration_seconds: float = Field(..., ge=0.0, description="Container duration in seconds.")
    size_bytes: int = Field(..., ge=0, description="Physical file size in bytes.")
    bit_rate: Optional[int] = Field(
        default=None, ge=0, description="Overall container bit rate (bps)."
    )
    tags: dict[str, str] = Field(
        default_factory=dict, description="Metadata tags (title, encoder, etc.)."
    )


class MediaInspectionResult(BaseModel):
    """Comprehensive inspection result for an input media file."""

    model_config = ConfigDict(frozen=True)

    source_path: Path = Field(..., description="Absolute path to inspected file.")
    container: ContainerMetadata = Field(..., description="Container-level properties.")
    video: VideoStreamMetadata = Field(..., description="Primary video stream metadata.")
    audio: Optional[AudioStreamMetadata] = Field(
        default=None, description="Audio stream metadata if present."
    )
    has_audio: bool = Field(..., description="Whether an audio stream was detected.")


class PreprocessingConfig(BaseModel):
    """Operational settings for proxy generation and audio extraction."""

    model_config = ConfigDict(frozen=True)

    proxy_width: int = Field(default=1280, gt=0, description="Target proxy bounding width.")
    proxy_height: int = Field(default=720, gt=0, description="Target proxy bounding height.")
    proxy_fps: int = Field(default=30, gt=0, description="Target proxy frame rate.")
    proxy_crf: int = Field(default=23, ge=0, le=51, description="H.264 constant rate factor.")
    audio_sample_rate: int = Field(default=16000, gt=0, description="Extracted WAV sample rate.")
    audio_channels: int = Field(
        default=1, gt=0, description="Extracted WAV channel count (1=mono)."
    )
    timeout_seconds: int = Field(default=300, gt=0, description="Subprocess execution timeout.")


class PreprocessingResult(BaseModel):
    """Artifacts produced by proxy video downscaling and audio extraction."""

    model_config = ConfigDict(frozen=True)

    proxy_path: Path = Field(..., description="Path to generated 720p H.264 analysis proxy.")
    proxy_metadata: MediaInspectionResult = Field(..., description="ffprobe metadata of the proxy.")
    audio_path: Optional[Path] = Field(
        default=None, description="Path to extracted 16kHz mono WAV (None if no audio)."
    )
    has_audio: bool = Field(..., description="Whether audio was extracted.")
    duration_seconds: float = Field(
        ..., ge=0.0, description="Valid duration of preprocessed media."
    )


class ExtractedFrame(BaseModel):
    """Metadata for an individual timestamped extracted frame image."""

    model_config = ConfigDict(frozen=True)

    frame_index: int = Field(..., ge=0, description="Sequential sampling index.")
    timestamp_seconds: float = Field(
        ..., ge=0.0, description="Source-relative timestamp in seconds."
    )
    file_path: Path = Field(..., description="Absolute path to saved frame image file.")
    width: int = Field(..., gt=0, description="Frame width in pixels.")
    height: int = Field(..., gt=0, description="Frame height in pixels.")


class FrameExtractionResult(BaseModel):
    """Result of sparse frame extraction over a video stream."""

    model_config = ConfigDict(frozen=True)

    frames: list[ExtractedFrame] = Field(
        ..., description="Sequence of timestamped extracted frames."
    )
    target_interval_seconds: float = Field(..., gt=0.0, description="Configured sampling interval.")
    total_frames_extracted: int = Field(..., ge=0, description="Total count of saved frames.")


class WaveformResult(BaseModel):
    """Compact peak and energy summary of an audio stream for timeline scrubbing."""

    model_config = ConfigDict(frozen=True)

    sample_rate: int = Field(..., gt=0, description="Source audio sample rate (Hz).")
    channels: int = Field(..., gt=0, description="Audio channel count.")
    bucket_duration_seconds: float = Field(
        ..., gt=0.0, description="Temporal width of each peak bin."
    )
    audio_start_seconds: float = Field(default=0.0, description="Audio presentation offset.")
    total_buckets: int = Field(..., ge=0, description="Total number of peak buckets.")
    peaks: list[float] = Field(..., description="Normalized peak amplitudes in [0.0, 1.0].")
    rms: list[float] = Field(
        default_factory=list, description="Normalized RMS energy values in [0.0, 1.0]."
    )


class PipelineStageStatus(str, Enum):
    """Execution status of an individual pipeline stage."""

    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class PipelineStageResult(BaseModel):
    """Diagnostic execution result for a single processing stage."""

    model_config = ConfigDict(frozen=True)

    stage_name: str = Field(..., description="Identifier of the pipeline stage.")
    status: PipelineStageStatus = Field(..., description="Outcome of the stage.")
    elapsed_seconds: float = Field(..., ge=0.0, description="Execution wall-clock time.")
    details: dict[str, Any] = Field(default_factory=dict, description="Diagnostic stage metrics.")


class PipelineResult(BaseModel):
    """Comprehensive outcome of the complete media ingestion and preprocessing pipeline."""

    model_config = ConfigDict(frozen=True)

    source_path: Path = Field(..., description="Path to original input recording.")
    work_dir: Path = Field(..., description="Directory containing all generated artifacts.")
    inspection: MediaInspectionResult = Field(..., description="Source media ffprobe inspection.")
    preprocessing: PreprocessingResult = Field(..., description="Generated proxy and audio assets.")
    frames: FrameExtractionResult = Field(..., description="Sparse sampled frame metadata.")
    waveform: Optional[WaveformResult] = Field(
        default=None, description="Waveform peaks if audio was present."
    )
    has_audio: bool = Field(..., description="Whether recording contained audio.")
    stages: list[PipelineStageResult] = Field(..., description="Stage-by-stage audit breakdown.")
    total_elapsed_seconds: float = Field(..., ge=0.0, description="Total pipeline execution time.")
    is_success: bool = Field(..., description="Whether pipeline completed without fatal error.")
