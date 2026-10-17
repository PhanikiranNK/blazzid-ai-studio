"""Benchmarks for highlight candidate ranking, interval selection, and planning."""

from __future__ import annotations

from typing import Any

from blazzid_assembly.config import AssemblyConfig, RankingConfig
from blazzid_assembly.models import RankedCandidate
from blazzid_assembly.planning import plan_edit_decision_list
from blazzid_assembly.ranking import rank_gameplay_candidates
from blazzid_assembly.selection import select_budgeted_highlights
from blazzid_core.contracts.candidates import HighlightCandidate
from blazzid_core.contracts.events import GameplayEventCandidate, GameplayEventType
from blazzid_core.contracts.observations import Modality, Observation, ObservationProvenance
from blazzid_core.contracts.time import TimeInterval


def _generate_benchmark_candidates(count: int = 50) -> list[GameplayEventCandidate]:
    candidates: list[GameplayEventCandidate] = []
    for i in range(count):
        start = float(i * 4)
        end = start + 5.0  # Overlapping intervals with neighbor
        event_type = (
            GameplayEventType.SUSTAINED_COMBAT if i % 2 == 0 else GameplayEventType.VISUAL_BURST
        )
        candidates.append(
            GameplayEventCandidate(
                id=f"cand_{i:03d}",
                event_type=event_type,
                trigger_timestamp=start + 0.5,
                interval=TimeInterval(start=start, end=end),
                climax_timestamp=start + 2.5,
                composite_confidence=0.5 + ((i % 10) * 0.05),
                evidence_sources=[
                    Observation(
                        modality=Modality.VISUAL,
                        interval=TimeInterval(start=start, end=end),
                        confidence=0.8,
                        provenance=ObservationProvenance(detector_name="detector_a"),
                    ),
                    Observation(
                        modality=Modality.VISUAL,
                        interval=TimeInterval(start=start, end=end),
                        confidence=0.7,
                        provenance=ObservationProvenance(detector_name="detector_b"),
                    ),
                ],
                metadata={"peak_intensity": 0.6 + ((i % 5) * 0.08)},
            )
        )
    return candidates


def test_benchmark_candidate_ranking(benchmark: Any) -> None:
    candidates = _generate_benchmark_candidates(count=50)
    cfg = RankingConfig()

    def run_ranking() -> tuple[list[RankedCandidate], list[HighlightCandidate]]:
        return rank_gameplay_candidates(candidates, source_duration_seconds=300.0, config=cfg)

    ranked, core = benchmark(run_ranking)
    assert len(ranked) == 50
    assert len(core) == 50


def test_benchmark_budgeted_selection_50_candidates(benchmark: Any) -> None:
    candidates = _generate_benchmark_candidates(count=50)
    _, core = rank_gameplay_candidates(candidates, source_duration_seconds=300.0)
    cfg = AssemblyConfig(target_duration_seconds=60.0, quantum_bin_seconds=0.5)

    def run_selection() -> list[HighlightCandidate]:
        selected, _, _ = select_budgeted_highlights(core, cfg)
        return selected

    selected = benchmark(run_selection)
    assert len(selected) > 0


def test_benchmark_clip_planning(benchmark: Any) -> None:
    candidates = _generate_benchmark_candidates(count=50)
    ranked, core = rank_gameplay_candidates(candidates, source_duration_seconds=300.0)
    cfg = AssemblyConfig(target_duration_seconds=60.0)
    selected, exclusions, _ = select_budgeted_highlights(core, cfg)

    def run_planning() -> Any:
        return plan_edit_decision_list(
            selected_candidates=selected,
            ranked_candidates=ranked,
            source_duration_seconds=300.0,
            config=cfg,
            exclusions=exclusions,
        )

    plan = benchmark(run_planning)
    assert plan.selected_count > 0
