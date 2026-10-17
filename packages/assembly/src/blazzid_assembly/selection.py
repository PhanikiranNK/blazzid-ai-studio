"""Duration-budgeted candidate selection integrating weighted interval scheduling."""

from __future__ import annotations

from collections.abc import Sequence

from blazzid_algorithms.interval_selection import select_highlights_dp
from blazzid_assembly.config import AssemblyConfig
from blazzid_assembly.models import ExclusionReason, ExclusionRecord
from blazzid_core.contracts.candidates import HighlightCandidate
from blazzid_core.contracts.selection import SelectionConstraints


def select_budgeted_highlights(
    candidates: Sequence[HighlightCandidate],
    config: AssemblyConfig,
) -> tuple[list[HighlightCandidate], list[ExclusionRecord], float]:
    """Applies constrained dynamic programming optimization to select the best highlight subset.

    Integrates blazzid_algorithms.select_highlights_dp under the requested duration budget.
    Additionally enforces max_clips_count, minimum separation constraints, and produces
    structured audit records explaining why each non-selected candidate was excluded.

    Args:
        candidates: Sequence of scored HighlightCandidate objects.
        config: Assembly configuration containing duration budget and clip bounds.

    Returns:
        Tuple of:
        - selected_candidates: List of selected HighlightCandidates sorted chronologically.
        - exclusions: List of ExclusionRecords for all unselected candidates.
        - budget_shortfall_seconds: Unused duration budget in seconds.
    """
    if not candidates:
        return [], [], config.target_duration_seconds

    # Build SelectionConstraints
    constraints = SelectionConstraints(
        target_duration_seconds=config.target_duration_seconds,
        max_overlap_ratio=0.0,  # Strict zero-overlap
        min_clip_duration_seconds=config.min_clip_duration_seconds,
        max_clip_duration_seconds=config.max_clip_duration_seconds,
        quantum_bin_seconds=config.quantum_bin_seconds,
    )

    # Pre-categorize candidates violating duration constraints
    exclusions: list[ExclusionRecord] = []
    eligible_candidates: list[HighlightCandidate] = []

    for c in candidates:
        dur = c.duration
        if dur < config.min_clip_duration_seconds:
            exclusions.append(
                ExclusionRecord(
                    candidate_id=c.candidate_id,
                    reason=ExclusionReason.DURATION_TOO_SHORT,
                    details=f"Duration {dur:.2f}s is below minimum {config.min_clip_duration_seconds:.2f}s.",
                )
            )
        elif (
            config.max_clip_duration_seconds is not None and dur > config.max_clip_duration_seconds
        ):
            exclusions.append(
                ExclusionRecord(
                    candidate_id=c.candidate_id,
                    reason=ExclusionReason.DURATION_EXCEEDS_BUDGET,
                    details=f"Duration {dur:.2f}s exceeds maximum clip duration {config.max_clip_duration_seconds:.2f}s.",
                )
            )
        elif dur > config.target_duration_seconds:
            exclusions.append(
                ExclusionRecord(
                    candidate_id=c.candidate_id,
                    reason=ExclusionReason.DURATION_EXCEEDS_BUDGET,
                    details=f"Duration {dur:.2f}s exceeds target budget {config.target_duration_seconds:.2f}s.",
                )
            )
        else:
            eligible_candidates.append(c)

    if not eligible_candidates:
        return [], exclusions, config.target_duration_seconds

    # Run 2D DP Weighted Interval Scheduling
    dp_result = select_highlights_dp(eligible_candidates, constraints)
    selected = list(dp_result.selected_candidates)

    # Optional post-processing: min separation gap constraint
    if config.min_separation_seconds > 0.0 and len(selected) > 1:
        filtered_selected: list[HighlightCandidate] = [selected[0]]
        for candidate in selected[1:]:
            prev = filtered_selected[-1]
            gap = candidate.interval.start - prev.interval.end
            if gap < config.min_separation_seconds:
                # Keep candidate with higher rank score
                if candidate.rank_score > prev.rank_score:
                    exclusions.append(
                        ExclusionRecord(
                            candidate_id=prev.candidate_id,
                            reason=ExclusionReason.INSUFFICIENT_SEPARATION,
                            details=(
                                f"Separation gap {gap:.2f}s is less than required "
                                f"{config.min_separation_seconds:.2f}s; replaced by higher-scoring candidate."
                            ),
                        )
                    )
                    filtered_selected[-1] = candidate
                else:
                    exclusions.append(
                        ExclusionRecord(
                            candidate_id=candidate.candidate_id,
                            reason=ExclusionReason.INSUFFICIENT_SEPARATION,
                            details=(
                                f"Separation gap {gap:.2f}s is less than required "
                                f"{config.min_separation_seconds:.2f}s."
                            ),
                        )
                    )
            else:
                filtered_selected.append(candidate)
        selected = filtered_selected

    # Optional post-processing: max clips count limit
    if config.max_clips_count is not None and len(selected) > config.max_clips_count:
        # Keep top max_clips_count by rank score
        ranked_by_score = sorted(selected, key=lambda c: c.rank_score, reverse=True)
        kept = {c.candidate_id for c in ranked_by_score[: config.max_clips_count]}
        pruned_selected: list[HighlightCandidate] = []
        for c in selected:
            if c.candidate_id in kept:
                pruned_selected.append(c)
            else:
                exclusions.append(
                    ExclusionRecord(
                        candidate_id=c.candidate_id,
                        reason=ExclusionReason.MAX_CLIPS_REACHED,
                        details=f"Limit of {config.max_clips_count} maximum clips reached.",
                    )
                )
        selected = pruned_selected

    selected_ids = {c.candidate_id for c in selected}

    # Audit exclusions for eligible candidates that were not selected by DP
    for c in eligible_candidates:
        if c.candidate_id not in selected_ids:
            # Determine whether unselected due to interval overlap or capacity
            overlaps = any(
                c.interval.intersection_over_union(sel.interval) > 0.0 for sel in selected
            )
            if overlaps:
                exclusions.append(
                    ExclusionRecord(
                        candidate_id=c.candidate_id,
                        reason=ExclusionReason.OVERLAPS_SUPERIOR_CANDIDATE,
                        details="Candidate temporally overlaps with a higher-utility selected highlight.",
                    )
                )
            else:
                exclusions.append(
                    ExclusionRecord(
                        candidate_id=c.candidate_id,
                        reason=ExclusionReason.BUDGET_EXHAUSTED,
                        details="Duration budget was exhausted by other higher-scoring non-overlapping clips.",
                    )
                )

    # Sort selected chronologically
    selected.sort(key=lambda c: c.interval.start)

    total_selected_duration = sum(c.duration for c in selected)
    shortfall = max(0.0, round(config.target_duration_seconds - total_selected_duration, 4))

    return selected, exclusions, shortfall
