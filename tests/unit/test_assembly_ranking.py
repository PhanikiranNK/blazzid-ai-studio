"""Unit tests for highlight candidate ranking and scoring."""

from __future__ import annotations

from blazzid_assembly.config import RankingConfig
from blazzid_assembly.ranking import rank_gameplay_candidates
from blazzid_core.contracts.events import GameplayEventCandidate, GameplayEventType
from blazzid_core.contracts.observations import Modality, Observation, ObservationProvenance
from blazzid_core.contracts.time import TimeInterval


def _make_candidate(
    cid: str,
    event_type: GameplayEventType,
    start: float,
    end: float,
    confidence: float,
    peak_intensity: float = 0.8,
    obs_count: int = 2,
) -> GameplayEventCandidate:
    obs = [
        Observation(
            modality=Modality.VISUAL,
            interval=TimeInterval(start=start, end=end),
            confidence=confidence,
            provenance=ObservationProvenance(detector_name=f"detector_{i}"),
        )
        for i in range(obs_count)
    ]
    return GameplayEventCandidate(
        id=cid,
        event_type=event_type,
        trigger_timestamp=start + 0.1,
        interval=TimeInterval(start=start, end=end),
        climax_timestamp=start + (end - start) / 2.0,
        composite_confidence=confidence,
        evidence_sources=obs,
        metadata={"peak_intensity": peak_intensity},
    )


def test_ranking_orders_candidates_by_utility() -> None:
    c1 = _make_candidate("c1", GameplayEventType.GENERIC_HIGHLIGHT, 10.0, 15.0, confidence=0.50)
    c2 = _make_candidate("c2", GameplayEventType.SUSTAINED_COMBAT, 20.0, 26.0, confidence=0.85)
    c3 = _make_candidate("c3", GameplayEventType.SCENE_TRANSITION, 30.0, 32.0, confidence=0.60)

    ranked, core = rank_gameplay_candidates([c1, c2, c3], source_duration_seconds=60.0)

    assert len(ranked) == 3
    assert len(core) == 3

    # c2 (SUSTAINED_COMBAT, high confidence) should rank 1st
    assert ranked[0].candidate.candidate_id == "c2"
    assert ranked[0].rank_index == 1
    assert ranked[0].candidate.rank_score >= ranked[1].candidate.rank_score
    assert ranked[1].candidate.rank_score >= ranked[2].candidate.rank_score


def test_ranking_category_multiplier() -> None:
    # Identical confidence, intensity, and duration, but different categories
    combat = _make_candidate(
        "combat", GameplayEventType.SUSTAINED_COMBAT, 10.0, 15.0, confidence=0.80
    )
    transition = _make_candidate(
        "cut", GameplayEventType.SCENE_TRANSITION, 20.0, 25.0, confidence=0.80
    )

    ranked, _ = rank_gameplay_candidates([combat, transition], source_duration_seconds=60.0)

    combat_rank = next(r for r in ranked if r.candidate.candidate_id == "combat")
    cut_rank = next(r for r in ranked if r.candidate.candidate_id == "cut")

    assert combat_rank.candidate.rank_score > cut_rank.candidate.rank_score
    assert cut_rank.candidate.scoring_breakdown["category_multiplier"] == 0.30
    assert combat_rank.candidate.scoring_breakdown["category_multiplier"] == 1.00


def test_ranking_boundary_cutoff_penalty() -> None:
    # Candidate starting at 0.5s (near 0) vs candidate starting in middle at 20.0s
    boundary_cand = _make_candidate(
        "bound", GameplayEventType.VISUAL_BURST, 0.5, 5.0, confidence=0.80
    )
    middle_cand = _make_candidate(
        "mid", GameplayEventType.VISUAL_BURST, 20.0, 24.5, confidence=0.80
    )

    cfg = RankingConfig(boundary_penalty_seconds=2.0, boundary_penalty_factor=0.20)
    ranked, _ = rank_gameplay_candidates(
        [boundary_cand, middle_cand], source_duration_seconds=60.0, config=cfg
    )

    bound_r = next(r for r in ranked if r.candidate.candidate_id == "bound")
    mid_r = next(r for r in ranked if r.candidate.candidate_id == "mid")

    assert bound_r.candidate.scoring_breakdown["boundary_penalty"] == 0.20
    assert mid_r.candidate.scoring_breakdown["boundary_penalty"] == 0.0
    assert mid_r.candidate.rank_score > bound_r.candidate.rank_score


def test_ranking_filters_low_confidence() -> None:
    low = _make_candidate("low", GameplayEventType.GENERIC_HIGHLIGHT, 10.0, 14.0, confidence=0.15)
    high = _make_candidate("high", GameplayEventType.SUSTAINED_COMBAT, 20.0, 25.0, confidence=0.75)

    cfg = RankingConfig(min_confidence=0.30)
    ranked, core = rank_gameplay_candidates([low, high], source_duration_seconds=60.0, config=cfg)

    assert len(ranked) == 1
    assert ranked[0].candidate.candidate_id == "high"


def test_ranking_explanation_contains_audit_details() -> None:
    cand = _make_candidate("c1", GameplayEventType.SUSTAINED_COMBAT, 10.0, 16.0, confidence=0.82)
    ranked, _ = rank_gameplay_candidates([cand], source_duration_seconds=60.0)

    explanation = ranked[0].scoring_explanation
    assert "Type=SUSTAINED_COMBAT" in explanation
    assert "Confidence=0.82" in explanation
    assert "Consensus=" in explanation
