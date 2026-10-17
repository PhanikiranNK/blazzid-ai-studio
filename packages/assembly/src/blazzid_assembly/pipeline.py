"""Unified HighlightAssemblyPipeline orchestrator coordinating ranking, selection, rendering, and validation."""

from __future__ import annotations

import time
from collections.abc import Sequence
from pathlib import Path
from typing import Optional

from blazzid_assembly.config import AssemblyConfig
from blazzid_assembly.models import (
    AssemblyResult,
    EditManifest,
    EditPlan,
    RankedCandidate,
    ValidationReport,
)
from blazzid_assembly.planning import plan_edit_decision_list
from blazzid_assembly.ranking import rank_gameplay_candidates
from blazzid_assembly.rendering import render_montage
from blazzid_assembly.validation import validate_rendered_montage
from blazzid_core.contracts.events import GameplayEventCandidate
from blazzid_media.probe import probe_media
from blazzid_media.validation import ensure_safe_directory


class HighlightAssemblyPipeline:
    """End-to-end highlight assembly pipeline.

    Orchestrates:
    1. Candidate scoring and explainable ranking (GameplayEventCandidate -> RankedCandidate).
    2. Constrained selection via Dynamic Programming Weighted Interval Scheduling under duration budget.
    3. Narrative context padding and clip boundary planning into a validated EditPlan.
    4. Deterministic clip extraction, profile canvas normalization, and concatenation via FFmpeg.
    5. Post-render container, video/audio stream, and decode smoke test validation.
    6. Machine-readable JSON edit manifest serialization.
    """

    def __init__(self, config: Optional[AssemblyConfig] = None) -> None:
        self.config = config or AssemblyConfig()

    def assemble(
        self,
        source_path: Path,
        candidates: Sequence[GameplayEventCandidate],
        output_path: Path,
        *,
        source_duration_seconds: Optional[float] = None,
        source_has_audio: Optional[bool] = None,
    ) -> AssemblyResult:
        """Executes the complete highlight assembly pipeline.

        Args:
            source_path: Path to source gameplay video.
            candidates: Sequence of Stage 3 GameplayEventCandidate objects.
            output_path: Target path for the rendered MP4 montage video.
            source_duration_seconds: Total duration of source video. If None, probed via ffprobe.
            source_has_audio: Whether source has audio. If None, probed via ffprobe.

        Returns:
            AssemblyResult containing final paths, edit plan, validation report, and manifest.
        """
        stage_durations: dict[str, float] = {}

        if not source_path.is_file():
            empty_plan = EditPlan(
                clips=[],
                total_duration_seconds=0.0,
                target_budget_seconds=self.config.target_duration_seconds,
                budget_shortfall_seconds=self.config.target_duration_seconds,
                selected_count=0,
                excluded_candidates=[],
            )
            return AssemblyResult(
                is_success=False,
                output_video_path=None,
                manifest_path=None,
                edit_plan=empty_plan,
                validation_report=None,
                manifest=None,
                error_message=f"Source media file not found: '{source_path}'",
            )

        ensure_safe_directory(output_path.parent)

        # Probe source if metadata not provided
        t0 = time.perf_counter()
        if source_duration_seconds is None or source_has_audio is None:
            try:
                inspection = probe_media(source_path)
                if source_duration_seconds is None:
                    source_duration_seconds = inspection.container.duration_seconds
                if source_has_audio is None:
                    source_has_audio = inspection.audio is not None
            except Exception as exc:
                empty_plan = EditPlan(
                    clips=[],
                    total_duration_seconds=0.0,
                    target_budget_seconds=self.config.target_duration_seconds,
                    budget_shortfall_seconds=self.config.target_duration_seconds,
                    selected_count=0,
                    excluded_candidates=[],
                )
                return AssemblyResult(
                    is_success=False,
                    output_video_path=None,
                    manifest_path=None,
                    edit_plan=empty_plan,
                    validation_report=None,
                    manifest=None,
                    error_message=f"Failed probing source media: {exc}",
                )
        stage_durations["source_probe"] = round(time.perf_counter() - t0, 4)

        # Stage 1: Candidate Ranking
        t_rank = time.perf_counter()
        ranked_candidates, core_candidates = rank_gameplay_candidates(
            candidates=candidates,
            source_duration_seconds=source_duration_seconds,
            config=self.config.ranking_config,
        )
        stage_durations["ranking"] = round(time.perf_counter() - t_rank, 4)

        # Stage 2: Budgeted Selection
        t_sel = time.perf_counter()
        from blazzid_assembly.selection import select_budgeted_highlights

        selected_candidates, exclusions, _ = select_budgeted_highlights(
            candidates=core_candidates,
            config=self.config,
        )
        stage_durations["selection"] = round(time.perf_counter() - t_sel, 4)

        # Stage 3: Clip Boundary Planning
        t_plan = time.perf_counter()
        edit_plan = plan_edit_decision_list(
            selected_candidates=selected_candidates,
            ranked_candidates=ranked_candidates,
            source_duration_seconds=source_duration_seconds,
            config=self.config,
            exclusions=exclusions,
        )
        stage_durations["planning"] = round(time.perf_counter() - t_plan, 4)

        if not edit_plan.clips:
            # Handle empty selection gracefully without crashing
            manifest = self._build_manifest(
                source_path=source_path,
                source_duration_seconds=source_duration_seconds,
                ranked_candidates=ranked_candidates,
                edit_plan=edit_plan,
                output_path=output_path,
                validation_report=None,
                stage_durations=stage_durations,
                warnings=[
                    "Zero clips qualified within the requested duration budget and constraints."
                ],
            )
            manifest_path = self._write_manifest(manifest, output_path)
            return AssemblyResult(
                is_success=False,
                output_video_path=None,
                manifest_path=manifest_path,
                edit_plan=edit_plan,
                validation_report=None,
                manifest=manifest,
                error_message="No clips qualified under duration budget and selection constraints.",
            )

        # Stage 4: Rendering Montage
        t_render = time.perf_counter()
        try:
            rendered_video = render_montage(
                source_path=source_path,
                edit_plan=edit_plan,
                output_path=output_path,
                config=self.config,
                source_has_audio=bool(source_has_audio),
                temp_dir=self.config.work_dir,
            )
        except Exception as exc:
            stage_durations["rendering"] = round(time.perf_counter() - t_render, 4)
            manifest = self._build_manifest(
                source_path=source_path,
                source_duration_seconds=source_duration_seconds,
                ranked_candidates=ranked_candidates,
                edit_plan=edit_plan,
                output_path=output_path,
                validation_report=None,
                stage_durations=stage_durations,
                warnings=[f"Rendering aborted due to error: {exc}"],
            )
            manifest_path = self._write_manifest(manifest, output_path)
            return AssemblyResult(
                is_success=False,
                output_video_path=None,
                manifest_path=manifest_path,
                edit_plan=edit_plan,
                validation_report=None,
                manifest=manifest,
                error_message=f"Montage rendering failed: {exc}",
            )
        stage_durations["rendering"] = round(time.perf_counter() - t_render, 4)

        # Stage 5: Validation
        t_val = time.perf_counter()
        val_report = validate_rendered_montage(
            output_path=rendered_video,
            edit_plan=edit_plan,
            config=self.config,
            expected_has_audio=bool(source_has_audio),
        )
        stage_durations["validation"] = round(time.perf_counter() - t_val, 4)

        # Stage 6: Manifest Generation
        manifest = self._build_manifest(
            source_path=source_path,
            source_duration_seconds=source_duration_seconds,
            ranked_candidates=ranked_candidates,
            edit_plan=edit_plan,
            output_path=output_path,
            validation_report=val_report,
            stage_durations=stage_durations,
            warnings=val_report.warnings,
        )
        manifest_path = self._write_manifest(manifest, output_path)

        return AssemblyResult(
            is_success=val_report.is_valid,
            output_video_path=rendered_video if val_report.is_valid else None,
            manifest_path=manifest_path,
            edit_plan=edit_plan,
            validation_report=val_report,
            manifest=manifest,
            error_message="; ".join(val_report.errors) if not val_report.is_valid else None,
        )

    def _build_manifest(
        self,
        source_path: Path,
        source_duration_seconds: float,
        ranked_candidates: list[RankedCandidate],
        edit_plan: EditPlan,
        output_path: Path,
        validation_report: Optional[ValidationReport],
        stage_durations: dict[str, float],
        warnings: list[str],
    ) -> EditManifest:
        profile = self.config.get_profile_config()

        ranked_dicts = [
            {
                "candidate_id": rc.candidate.candidate_id,
                "rank_index": rc.rank_index,
                "category": rc.event_type,
                "rank_score": rc.candidate.rank_score,
                "confidence": rc.candidate.confidence,
                "interval": {
                    "start": rc.candidate.interval.start,
                    "end": rc.candidate.interval.end,
                },
                "climax_timestamp": rc.climax_timestamp,
                "scoring_breakdown": rc.candidate.scoring_breakdown,
                "explanation": rc.scoring_explanation,
            }
            for rc in ranked_candidates
        ]

        selected_dicts = [
            {
                "clip_index": c.clip_index,
                "candidate_id": c.candidate_id,
                "category": c.category,
                "rank_score": c.rank_score,
                "source_interval": {"start": c.source_interval.start, "end": c.source_interval.end},
                "montage_interval": {
                    "start": c.montage_interval.start,
                    "end": c.montage_interval.end,
                },
                "climax_timestamp": c.climax_timestamp,
                "rationale": c.selection_rationale,
            }
            for c in edit_plan.clips
        ]

        excluded_dicts = [
            {
                "candidate_id": e.candidate_id,
                "reason": e.reason.value,
                "details": e.details,
            }
            for e in edit_plan.excluded_candidates
        ]

        val_dict = validation_report.model_dump(mode="json") if validation_report else {}

        return EditManifest(
            manifest_version="1.0.0",
            source_media_path=str(source_path.resolve()),
            source_duration_seconds=round(source_duration_seconds, 3),
            ranking_config_version=self.config.ranking_config.version,
            selection_constraints={
                "target_duration_seconds": self.config.target_duration_seconds,
                "min_clip_duration_seconds": self.config.min_clip_duration_seconds,
                "max_clip_duration_seconds": self.config.max_clip_duration_seconds,
                "max_clips_count": self.config.max_clips_count,
                "lead_in_padding_seconds": self.config.lead_in_padding_seconds,
                "lead_out_padding_seconds": self.config.lead_out_padding_seconds,
                "quantum_bin_seconds": self.config.quantum_bin_seconds,
                "min_separation_seconds": self.config.min_separation_seconds,
            },
            ranked_candidates=ranked_dicts,
            selected_candidates=selected_dicts,
            excluded_candidates=excluded_dicts,
            planned_clips=selected_dicts,
            rendering_profile=profile.model_dump(mode="json"),
            output_path=str(output_path.resolve()),
            validation=val_dict,
            stage_durations=stage_durations,
            warnings=warnings,
        )

    def _write_manifest(self, manifest: EditManifest, output_path: Path) -> Path:
        manifest_path = output_path.parent / f"{output_path.stem}.manifest.json"
        manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        return manifest_path
