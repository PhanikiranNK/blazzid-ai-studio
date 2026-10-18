"""Media processing engine orchestrating Stages 2, 3, and 4 pipelines."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional

from blazzid_assembly.config import AssemblyConfig
from blazzid_assembly.models import AssemblyProfile
from blazzid_assembly.pipeline import HighlightAssemblyPipeline
from blazzid_detection.detector import GameplayEventDetector
from blazzid_jobs.errors import (
    JobCancelledError,
    PermanentProcessingError,
    RetryableProcessingError,
)
from blazzid_jobs.models import JobRecord
from blazzid_jobs.repository import JobRepository
from blazzid_jobs.states import JobStage
from blazzid_media.errors import MediaError, ProbeError
from blazzid_media.pipeline import MediaPipeline
from blazzid_media.probe import probe_media
from blazzid_media.validation import validate_input_media_file
from blazzid_storage.interfaces import ArtifactType, StorageBackend

logger = logging.getLogger("blazzid.worker.processor")


class MediaJobProcessor:
    """Orchestrates video preprocessing, gameplay detection, and highlight montage rendering."""

    def __init__(
        self,
        storage: StorageBackend,
        repository: JobRepository,
    ) -> None:
        self.storage = storage
        self.repository = repository

    def _check_cancellation(
        self, job_id: str, is_cancelled_fn: Optional[Callable[[], bool]] = None
    ) -> None:
        if is_cancelled_fn and is_cancelled_fn():
            raise JobCancelledError(f"Job {job_id} cancelled by user request")
        if self.repository.check_cancellation(job_id):
            raise JobCancelledError(f"Job {job_id} cancellation detected in database")

    def process(
        self,
        job: JobRecord,
        worker_id: str,
        is_cancelled_fn: Optional[Callable[[], bool]] = None,
    ) -> dict[str, Any]:
        """Execute the full video processing pipeline with staged progress reporting."""
        job_id = job.job_id
        logger.info("Worker %s beginning execution of job %s", worker_id, job_id)

        scratch_dir = self.storage.create_job_working_dir(job_id)

        try:
            # 1. VALIDATING_INPUT
            self._check_cancellation(job_id, is_cancelled_fn)
            self.repository.update_progress(job_id, worker_id, JobStage.VALIDATING_INPUT)

            try:
                source_path = self.storage.get_source_path(job_id)
            except Exception as err:
                raise PermanentProcessingError(f"Failed to locate source media: {err}") from err

            try:
                validate_input_media_file(source_path)
            except MediaError as err:
                raise PermanentProcessingError(f"Input media validation failed: {err}") from err

            # 2. PROBING_MEDIA
            self._check_cancellation(job_id, is_cancelled_fn)
            self.repository.update_progress(job_id, worker_id, JobStage.PROBING_MEDIA)

            try:
                inspection = probe_media(source_path)
            except ProbeError as err:
                raise PermanentProcessingError(f"Failed to probe media streams: {err}") from err

            duration = inspection.container.duration_seconds
            has_audio = inspection.audio is not None

            # 3. PREPROCESSING (Stage 2)
            self._check_cancellation(job_id, is_cancelled_fn)
            self.repository.update_progress(job_id, worker_id, JobStage.PREPROCESSING)

            media_work_dir = scratch_dir / "media_pipeline"
            media_work_dir.mkdir(parents=True, exist_ok=True)

            try:
                media_pipeline = MediaPipeline(frame_interval_seconds=1.0)
                media_result = media_pipeline.process(
                    source_path=source_path, work_dir=media_work_dir
                )
            except Exception as err:
                raise RetryableProcessingError(
                    f"Stage 2 media preprocessing failed: {err}"
                ) from err

            # 4. DETECTING_EVENTS (Stage 3)
            self._check_cancellation(job_id, is_cancelled_fn)
            self.repository.update_progress(job_id, worker_id, JobStage.DETECTING_EVENTS)

            try:
                detector = GameplayEventDetector()
                detection_result = detector.detect(
                    media_input=media_result,
                    source_duration_seconds=duration,
                )
                candidates = detection_result.candidates
                logger.info("Job %s: detected %d candidate events", job_id, len(candidates))
            except Exception as err:
                raise RetryableProcessingError(f"Stage 3 gameplay detection failed: {err}") from err

            # Save candidates as artifact
            if not candidates:
                logger.info(
                    "Job %s: No gameplay events triggered by detector; generating default candidate from source",
                    job_id,
                )
                from blazzid_core.contracts import (
                    GameplayEventCandidate,
                    GameplayEventType,
                    Modality,
                    Observation,
                    ObservationProvenance,
                    TimeInterval,
                )

                clip_dur = min(duration, max(2.5, job.target_duration_sec))
                cand_interval = TimeInterval(start=0.0, end=clip_dur)
                candidates = [
                    GameplayEventCandidate(
                        id=f"evt-{job_id}-preview",
                        event_type=GameplayEventType.GENERIC_HIGHLIGHT,
                        trigger_timestamp=0.0,
                        interval=cand_interval,
                        climax_timestamp=clip_dur / 2.0,
                        composite_confidence=0.8,
                        evidence_sources=[
                            Observation(
                                modality=Modality.VISUAL,
                                interval=cand_interval,
                                confidence=0.8,
                                provenance=ObservationProvenance(detector_name="preview_detector"),
                            )
                        ],
                    )
                ]

            candidates_path = scratch_dir / "candidates.json"
            with open(candidates_path, "w", encoding="utf-8") as f:
                json.dump([c.model_dump(mode="json") for c in candidates], f, indent=2)
            self.storage.store_artifact_from_path(
                job_id=job_id,
                artifact_type=ArtifactType.CANDIDATES_JSON,
                local_file_path=candidates_path,
            )

            # 5. RANKING_HIGHLIGHTS (Stage 4)
            self._check_cancellation(job_id, is_cancelled_fn)
            self.repository.update_progress(job_id, worker_id, JobStage.RANKING_HIGHLIGHTS)

            # 6. PLANNING_EDIT (Stage 4)
            self._check_cancellation(job_id, is_cancelled_fn)
            self.repository.update_progress(job_id, worker_id, JobStage.PLANNING_EDIT)

            # Map profile
            profile_enum = (
                AssemblyProfile.PORTRAIT_9_16
                if job.assembly_profile in ("youtube_shorts", "PORTRAIT_9_16")
                else AssemblyProfile.LANDSCAPE_16_9
            )

            assembly_config = AssemblyConfig(
                profile=profile_enum,
                target_duration_seconds=job.target_duration_sec,
                max_clips_count=job.max_clips,
                work_dir=scratch_dir / "assembly",
            )
            assembly_pipeline = HighlightAssemblyPipeline(config=assembly_config)

            # 7. RENDERING (Stage 4)
            self._check_cancellation(job_id, is_cancelled_fn)
            self.repository.update_progress(job_id, worker_id, JobStage.RENDERING)

            montage_out = scratch_dir / f"{job_id}_montage.mp4"

            try:
                assembly_result = assembly_pipeline.assemble(
                    source_path=source_path,
                    candidates=candidates,
                    output_path=montage_out,
                    source_duration_seconds=duration,
                    source_has_audio=has_audio,
                    is_cancelled_fn=is_cancelled_fn,
                )
            except Exception as err:
                raise RetryableProcessingError(f"Stage 4 montage rendering failed: {err}") from err

            # 8. VALIDATING_OUTPUT (Stage 4)
            self._check_cancellation(job_id, is_cancelled_fn)
            self.repository.update_progress(job_id, worker_id, JobStage.VALIDATING_OUTPUT)

            if not assembly_result.is_success or not assembly_result.output_video_path:
                err_msg = assembly_result.error_message or "Montage assembly did not produce output"
                raise PermanentProcessingError(f"Stage 4 assembly failed: {err_msg}")

            if assembly_result.validation_report and not assembly_result.validation_report.is_valid:
                err_details = "; ".join(assembly_result.validation_report.errors)
                raise PermanentProcessingError(
                    f"Rendered montage failed output validation: {err_details}"
                )

            # 9. FINALIZING
            self._check_cancellation(job_id, is_cancelled_fn)
            self.repository.update_progress(
                job_id, worker_id, JobStage.FINALIZING, progress_percent=98.0
            )

            # Persist rendered video
            montage_artifact = self.storage.store_artifact_from_path(
                job_id=job_id,
                artifact_type=ArtifactType.RENDERED_MONTAGE,
                local_file_path=assembly_result.output_video_path,
                filename=f"{job_id}_highlight.mp4",
                content_type="video/mp4",
            )

            # Persist manifest
            manifest_dict = (
                assembly_result.manifest.model_dump(mode="json") if assembly_result.manifest else {}
            )
            manifest_file = scratch_dir / f"{job_id}_manifest.json"
            with open(manifest_file, "w", encoding="utf-8") as f:
                json.dump(manifest_dict, f, indent=2)

            self.storage.store_artifact_from_path(
                job_id=job_id,
                artifact_type=ArtifactType.EDIT_MANIFEST_JSON,
                local_file_path=manifest_file,
                filename=f"{job_id}_manifest.json",
                content_type="application/json",
            )

            logger.info(
                "Job %s completed successfully (montage: %s)", job_id, montage_artifact.storage_path
            )
            return manifest_dict

        finally:
            # Deterministic cleanup of temporary scratch directory
            logger.debug("Cleaning scratch directory for job %s", job_id)
            self.storage.clean_scratch(job_id)
