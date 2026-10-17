"""Explainable highlight candidate ranking and scoring engine."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Optional

from blazzid_assembly.config import RankingConfig
from blazzid_assembly.models import RankedCandidate
from blazzid_core.contracts.candidates import HighlightCandidate
from blazzid_core.contracts.events import GameplayEventCandidate


def rank_gameplay_candidates(
    candidates: Sequence[GameplayEventCandidate],
    source_duration_seconds: float,
    config: Optional[RankingConfig] = None,
) -> tuple[list[RankedCandidate], list[HighlightCandidate]]:
    """Scores, ranks, and converts GameplayEventCandidate objects into HighlightCandidates.

    Features:
    - Normalizes scores into [0.0, 1.0] with transparent sub-score weights.
    - Evaluates composite confidence, detector consensus, climax intensity, and event persistence.
    - Applies category multipliers (e.g. sustained combat prioritized over generic transitions).
    - Deducts penalties for boundary cutoffs near 0s or source duration.
    - Generates human-readable scoring explanations for every candidate.
    - Sorts descending by rank score with deterministic tie-breaking.

    Args:
        candidates: Sequence of Stage 3 gameplay event candidates.
        source_duration_seconds: Total duration of the source recording in seconds.
        config: Ranking configuration weights. If None, uses defaults.

    Returns:
        Tuple of (ranked_candidates, core_highlight_candidates).
    """
    cfg = config or RankingConfig()

    scored_items: list[tuple[RankedCandidate, HighlightCandidate]] = []

    for event_cand in candidates:
        # Confidence score
        conf = float(event_cand.composite_confidence)

        # Skip candidates below minimum confidence threshold
        if conf < cfg.min_confidence:
            continue

        # Detector consensus: number of distinct evidence sources
        obs_count = len(event_cand.evidence_sources)
        consensus_score = min(1.0, 0.40 * obs_count) if obs_count > 0 else 0.30

        # Peak intensity at climax point
        meta = event_cand.metadata or {}
        climax_intensity = float(meta.get("peak_intensity", 0.50))
        climax_intensity = max(0.0, min(1.0, climax_intensity))

        # Duration persistence score (optimal range ~ 4-8 seconds)
        dur = float(event_cand.interval.duration)
        dur_score = min(1.0, dur / 8.0) if dur > 0.0 else 0.0

        # Category multiplier
        cat_key = event_cand.event_type.value
        cat_multiplier = float(cfg.category_multipliers.get(cat_key, 0.70))

        # Boundary cutoff penalty
        touches_start = event_cand.interval.start <= cfg.boundary_penalty_seconds
        touches_end = (
            source_duration_seconds - event_cand.interval.end
        ) <= cfg.boundary_penalty_seconds
        boundary_penalty = cfg.boundary_penalty_factor if (touches_start or touches_end) else 0.0

        # Weighted composite score
        base_score = (
            cfg.confidence_weight * conf
            + cfg.consensus_weight * consensus_score
            + cfg.intensity_weight * climax_intensity
            + cfg.duration_weight * dur_score
        )

        final_rank_score = round(
            max(0.0, min(1.0, base_score * cat_multiplier * (1.0 - boundary_penalty))),
            4,
        )

        breakdown = {
            "confidence": round(conf, 4),
            "consensus": round(consensus_score, 4),
            "climax_intensity": round(climax_intensity, 4),
            "duration_factor": round(dur_score, 4),
            "category_multiplier": round(cat_multiplier, 4),
            "boundary_penalty": round(boundary_penalty, 4),
            "final_rank_score": final_rank_score,
        }

        explanation = (
            f"Type={cat_key} (mult={cat_multiplier:.2f}), "
            f"Confidence={conf:.2f} (w={cfg.confidence_weight:.2f}), "
            f"Consensus={obs_count} detectors (w={cfg.consensus_weight:.2f}), "
            f"Intensity={climax_intensity:.2f} (w={cfg.intensity_weight:.2f}), "
            f"Duration={dur:.1f}s (w={cfg.duration_weight:.2f})"
        )
        if boundary_penalty > 0.0:
            explanation += f", BoundaryPenalty=-{boundary_penalty:.2f}"

        core_candidate = HighlightCandidate(
            candidate_id=event_cand.id,
            event_id=event_cand.id,
            interval=event_cand.interval,
            rank_score=final_rank_score,
            confidence=conf,
            category=cat_key,
            scoring_breakdown=breakdown,
            is_selected=False,
        )

        ranked = RankedCandidate(
            candidate=core_candidate,
            rank_index=1,  # updated after sorting
            event_type=cat_key,
            climax_timestamp=event_cand.climax_timestamp,
            trigger_timestamp=event_cand.trigger_timestamp,
            scoring_explanation=explanation,
        )

        scored_items.append((ranked, core_candidate))

    # Sort descending by rank_score, tie-breaking deterministically:
    # higher confidence, earlier start time, candidate_id
    scored_items.sort(
        key=lambda item: (
            -item[1].rank_score,
            -item[1].confidence,
            item[1].interval.start,
            item[1].candidate_id,
        )
    )

    ranked_list: list[RankedCandidate] = []
    core_list: list[HighlightCandidate] = []

    for rank_idx, (ranked, core_cand) in enumerate(scored_items, start=1):
        updated_ranked = RankedCandidate(
            candidate=core_cand,
            rank_index=rank_idx,
            event_type=ranked.event_type,
            climax_timestamp=ranked.climax_timestamp,
            trigger_timestamp=ranked.trigger_timestamp,
            scoring_explanation=ranked.scoring_explanation,
        )
        ranked_list.append(updated_ranked)
        core_list.append(core_cand)

    return ranked_list, core_list
