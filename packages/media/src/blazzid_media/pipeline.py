"""Composable media ingestion, probing, preprocessing, and extraction pipeline."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from blazzid_media.frames import extract_sparse_frames
from blazzid_media.models import (
    FrameExtractionResult,
    MediaInspectionResult,
    PipelineResult,
    PipelineStageResult,
    PipelineStageStatus,
    PreprocessingConfig,
    PreprocessingResult,
    WaveformResult,
)
from blazzid_media.preprocessing import preprocess_media
from blazzid_media.probe import probe_media
from blazzid_media.validation import ensure_safe_directory, validate_input_media_file
from blazzid_media.waveform import generate_waveform_peaks, save_waveform_json


class MediaPipeline:
    """Synchronous, local-first media analysis pipeline."""

    def __init__(
        self,
        *,
        preprocessing_config: Optional[PreprocessingConfig] = None,
        frame_interval_seconds: float = 1.0,
        waveform_bucket_seconds: float = 0.1,
    ) -> None:
        self.preprocessing_config = preprocessing_config or PreprocessingConfig()
        self.frame_interval_seconds = frame_interval_seconds
        self.waveform_bucket_seconds = waveform_bucket_seconds

    def process(
        self,
        source_path: Path | str,
        work_dir: Path | str,
    ) -> PipelineResult:
        """Executes full end-to-end media preprocessing on a video recording.

        Stages:
        1. VALIDATION: Validates file existence, permissions, and size bounds.
        2. INSPECTION: ffprobe stream analysis and frame-rate classification.
        3. PREPROCESSING: 720p H.264 proxy transcode and 16kHz mono audio extraction.
        4. FRAME_EXTRACTION: Sparse timestamp-aware keyframe extraction.
        5. WAVEFORM_GENERATION: Compact audio peak and RMS calculation (if audio present).

        Args:
            source_path: Path to raw input video recording.
            work_dir: Target directory where analysis artifacts are written.

        Returns:
            PipelineResult containing verified artifact paths, metadata, and stage audit.

        Raises:
            MediaError: If any fatal processing step fails.
        """
        pipeline_start = time.perf_counter()
        stages: list[PipelineStageResult] = []
        w_dir = ensure_safe_directory(work_dir)

        # Stage 1: Validation
        t0 = time.perf_counter()
        validated_src = validate_input_media_file(source_path)
        stages.append(
            PipelineStageResult(
                stage_name="VALIDATION",
                status=PipelineStageStatus.SUCCESS,
                elapsed_seconds=round(time.perf_counter() - t0, 3),
                details={"file_size_bytes": validated_src.stat().st_size},
            )
        )

        # Stage 2: Inspection (ffprobe)
        t0 = time.perf_counter()
        inspection: MediaInspectionResult = probe_media(validated_src)
        stages.append(
            PipelineStageResult(
                stage_name="INSPECTION",
                status=PipelineStageStatus.SUCCESS,
                elapsed_seconds=round(time.perf_counter() - t0, 3),
                details={
                    "format": inspection.container.format_name,
                    "duration_seconds": inspection.container.duration_seconds,
                    "resolution": f"{inspection.video.width}x{inspection.video.height}",
                    "codec": inspection.video.codec_name,
                    "frame_rate_mode": inspection.video.frame_rate_mode.value,
                    "has_audio": inspection.has_audio,
                },
            )
        )

        # Stage 3: Preprocessing (Proxy + Audio WAV)
        t0 = time.perf_counter()
        preprocessing: PreprocessingResult = preprocess_media(
            validated_src,
            w_dir,
            config=self.preprocessing_config,
            inspection=inspection,
        )
        stages.append(
            PipelineStageResult(
                stage_name="PREPROCESSING",
                status=PipelineStageStatus.SUCCESS,
                elapsed_seconds=round(time.perf_counter() - t0, 3),
                details={
                    "proxy_path": str(preprocessing.proxy_path),
                    "proxy_size_bytes": preprocessing.proxy_path.stat().st_size,
                    "audio_path": str(preprocessing.audio_path)
                    if preprocessing.audio_path
                    else None,
                },
            )
        )

        # Stage 4: Sparse Frame Extraction
        t0 = time.perf_counter()
        frames_dir = w_dir / "frames"
        frames_res: FrameExtractionResult = extract_sparse_frames(
            preprocessing.proxy_path,
            frames_dir,
            target_interval_seconds=self.frame_interval_seconds,
        )
        stages.append(
            PipelineStageResult(
                stage_name="FRAME_EXTRACTION",
                status=PipelineStageStatus.SUCCESS,
                elapsed_seconds=round(time.perf_counter() - t0, 3),
                details={
                    "frames_extracted": frames_res.total_frames_extracted,
                    "interval_seconds": frames_res.target_interval_seconds,
                },
            )
        )

        # Stage 5: Waveform Generation (if audio present)
        t0 = time.perf_counter()
        waveform_res: Optional[WaveformResult] = None
        if preprocessing.has_audio and preprocessing.audio_path is not None:
            audio_start = (
                inspection.audio.start_time_seconds
                if (inspection.audio and inspection.audio.start_time_seconds is not None)
                else 0.0
            )
            waveform_res = generate_waveform_peaks(
                preprocessing.audio_path,
                bucket_duration_seconds=self.waveform_bucket_seconds,
                audio_start_seconds=audio_start,
            )
            waveform_json_path = w_dir / "waveform.json"
            save_waveform_json(waveform_res, waveform_json_path)

            stages.append(
                PipelineStageResult(
                    stage_name="WAVEFORM_GENERATION",
                    status=PipelineStageStatus.SUCCESS,
                    elapsed_seconds=round(time.perf_counter() - t0, 3),
                    details={
                        "total_buckets": waveform_res.total_buckets,
                        "bucket_duration_seconds": waveform_res.bucket_duration_seconds,
                        "artifact_path": str(waveform_json_path),
                    },
                )
            )
        else:
            stages.append(
                PipelineStageResult(
                    stage_name="WAVEFORM_GENERATION",
                    status=PipelineStageStatus.SKIPPED,
                    elapsed_seconds=0.0,
                    details={"reason": "no_audio_stream_in_media"},
                )
            )

        total_elapsed = round(time.perf_counter() - pipeline_start, 3)

        return PipelineResult(
            source_path=validated_src,
            work_dir=w_dir,
            inspection=inspection,
            preprocessing=preprocessing,
            frames=frames_res,
            waveform=waveform_res,
            has_audio=inspection.has_audio,
            stages=stages,
            total_elapsed_seconds=total_elapsed,
            is_success=True,
        )
