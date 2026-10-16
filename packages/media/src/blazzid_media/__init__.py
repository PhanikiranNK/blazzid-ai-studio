"""BLAZZID AI Studio - Media Ingestion, Preprocessing & Fast Video Analysis.

Stage 2 local-first media processing pipeline for video inspection,
proxy generation, audio extraction, sparse frame extraction, and waveform calculation.
"""

from blazzid_media.errors import (
    AudioExtractionError,
    FrameExtractionError,
    MediaError,
    MediaInputError,
    MissingVideoStreamError,
    PreprocessingError,
    ProbeError,
    WaveformError,
)
from blazzid_media.frames import extract_sparse_frames
from blazzid_media.models import (
    AudioStreamMetadata,
    ContainerMetadata,
    ExtractedFrame,
    FrameExtractionResult,
    FrameRateMode,
    MediaInspectionResult,
    PipelineResult,
    PipelineStageResult,
    PreprocessingConfig,
    PreprocessingResult,
    VideoStreamMetadata,
    WaveformResult,
)
from blazzid_media.pipeline import MediaPipeline
from blazzid_media.preprocessing import (
    extract_audio_wav,
    generate_analysis_proxy,
    preprocess_media,
)
from blazzid_media.probe import probe_media
from blazzid_media.validation import (
    ensure_safe_directory,
    validate_input_media_file,
)
from blazzid_media.waveform import generate_waveform_peaks

# Ergonomic aliases
inspect_media = probe_media
extract_audio = extract_audio_wav
validate_input_file = validate_input_media_file

__all__ = [
    # Errors
    "MediaError",
    "MediaInputError",
    "ProbeError",
    "MissingVideoStreamError",
    "PreprocessingError",
    "AudioExtractionError",
    "FrameExtractionError",
    "WaveformError",
    # Models
    "FrameRateMode",
    "VideoStreamMetadata",
    "AudioStreamMetadata",
    "ContainerMetadata",
    "MediaInspectionResult",
    "PreprocessingConfig",
    "PreprocessingResult",
    "ExtractedFrame",
    "FrameExtractionResult",
    "WaveformResult",
    "PipelineStageResult",
    "PipelineResult",
    # Functions & Classes
    "validate_input_media_file",
    "validate_input_file",
    "ensure_safe_directory",
    "probe_media",
    "inspect_media",
    "generate_analysis_proxy",
    "extract_audio_wav",
    "extract_audio",
    "preprocess_media",
    "extract_sparse_frames",
    "generate_waveform_peaks",
    "MediaPipeline",
]
