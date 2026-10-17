"""Context-aware clip boundary planning and timeline offset mapping."""

from __future__ import annotations

from blazzid_assembly.config import AssemblyConfig
from blazzid_assembly.models import EditPlan, ExclusionRecord, PlannedClip, RankedCandidate
from blazzid_core.contracts.candidates import HighlightCandidate
from blazzid_core.contracts.time import TimeInterval


class _IntermediateClip:
    def __init__(
        self,
        candidate: HighlightCandidate,
        ranked: RankedCandidate | None,
        start: float,
        end: float,
        climax: float | None,
    ) -> None:
        self.candidate = candidate
        self.ranked = ranked
        self.start = start
        self.end = end
        self.climax = climax


def plan_edit_decision_list(
    selected_candidates: list[HighlightCandidate],
    ranked_candidates: list[RankedCandidate],
    source_duration_seconds: float,
    config: AssemblyConfig,
    exclusions: list[ExclusionRecord] | None = None,
) -> EditPlan:
    """Constructs a validated EditPlan with padded source boundaries and montage timeline mappings.

    Key guarantees:
    - Contextual lead-in and lead-out padding are applied to capture setup and payoff.
    - Boundaries are strictly clamped to [0.0, source_duration_seconds].
    - Unintended overlaps caused by padding are resolved deterministically.
    - Sequential montage intervals are computed: [0, dur_0), [dur_0, dur_0 + dur_1), etc.
    - Produces a machine-readable EditPlan for rendering.

    Args:
        selected_candidates: Highlight candidates selected by the optimization engine.
        ranked_candidates: Ranked candidates containing climax timestamps and metadata.
        source_duration_seconds: Total duration of the input video.
        config: Active assembly configuration.
        exclusions: Audit list of excluded candidates.

    Returns:
        Validated EditPlan ready for rendering.
    """
    if not selected_candidates:
        return EditPlan(
            clips=[],
            total_duration_seconds=0.0,
            target_budget_seconds=config.target_duration_seconds,
            budget_shortfall_seconds=config.target_duration_seconds,
            selected_count=0,
            excluded_candidates=exclusions or [],
        )

    ranked_map = {rc.candidate.candidate_id: rc for rc in ranked_candidates}

    # Step 1: Compute padded intervals
    raw_clips: list[_IntermediateClip] = []

    for cand in selected_candidates:
        ranked = ranked_map.get(cand.candidate_id)
        climax_ts = ranked.climax_timestamp if ranked else None

        raw_start = max(0.0, cand.interval.start - config.lead_in_padding_seconds)
        raw_end = min(source_duration_seconds, cand.interval.end + config.lead_out_padding_seconds)

        # Ensure start < end
        if raw_end <= raw_start:
            raw_end = min(source_duration_seconds, raw_start + 1.0)

        # Enforce max clip duration if configured
        if (
            config.max_clip_duration_seconds is not None
            and (raw_end - raw_start) > config.max_clip_duration_seconds
        ):
            # If climax is known, preserve context around climax
            if climax_ts is not None and raw_start <= climax_ts <= raw_end:
                half = config.max_clip_duration_seconds / 2.0
                raw_start = max(0.0, climax_ts - half)
                raw_end = min(source_duration_seconds, raw_start + config.max_clip_duration_seconds)
            else:
                raw_end = raw_start + config.max_clip_duration_seconds

        # Enforce min clip duration if feasible
        if (raw_end - raw_start) < config.min_clip_duration_seconds:
            shortfall = config.min_clip_duration_seconds - (raw_end - raw_start)
            left_exp = min(raw_start, shortfall / 2.0)
            raw_start -= left_exp
            remaining = shortfall - left_exp
            raw_end = min(source_duration_seconds, raw_start + remaining)

        raw_clips.append(
            _IntermediateClip(
                candidate=cand,
                ranked=ranked,
                start=round(raw_start, 3),
                end=round(raw_end, 3),
                climax=climax_ts,
            )
        )

    # Step 2: Sort chronologically by start time
    raw_clips.sort(key=lambda item: item.start)

    # Step 3: Resolve any overlaps between consecutive padded clips
    for i in range(len(raw_clips) - 1):
        if raw_clips[i].end > raw_clips[i + 1].start:
            midpoint = round((raw_clips[i].end + raw_clips[i + 1].start) / 2.0, 3)
            raw_clips[i].end = max(raw_clips[i].start + 0.5, midpoint)
            raw_clips[i + 1].start = max(raw_clips[i].end, midpoint)

    # Step 4: Construct PlannedClip objects and compute montage timeline offsets
    planned_clips: list[PlannedClip] = []
    current_montage_offset = 0.0

    for idx, item in enumerate(raw_clips):
        start = item.start
        end = item.end
        if end <= start:
            end = start + 0.5

        clip_dur = round(end - start, 3)
        source_interval = TimeInterval(start=start, end=end)
        montage_interval = TimeInterval(
            start=round(current_montage_offset, 3),
            end=round(current_montage_offset + clip_dur, 3),
        )

        rationale = (
            f"Selected candidate {item.candidate.candidate_id[:8]} "
            f"(rank_score={item.candidate.rank_score:.2f}, category={item.candidate.category}) "
            f"spanning [{start:.1f}s, {end:.1f}s) in source."
        )

        planned_clip = PlannedClip(
            clip_index=idx,
            candidate_id=cand.candidate_id,
            source_interval=source_interval,
            montage_interval=montage_interval,
            climax_timestamp=climax_ts,
            rank_score=cand.rank_score,
            category=cand.category,
            selection_rationale=rationale,
        )
        planned_clips.append(planned_clip)
        current_montage_offset += clip_dur

    total_dur = round(current_montage_offset, 3)
    shortfall = max(0.0, round(config.target_duration_seconds - total_dur, 3))

    return EditPlan(
        clips=planned_clips,
        total_duration_seconds=total_dur,
        target_budget_seconds=config.target_duration_seconds,
        budget_shortfall_seconds=shortfall,
        selected_count=len(planned_clips),
        excluded_candidates=exclusions or [],
    )
