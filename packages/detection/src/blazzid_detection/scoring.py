"""Explainable scoring and confidence calibration for gameplay event candidates."""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from blazzid_core.contracts.confidence import validate_confidence
from blazzid_core.contracts.events import GameplayEventCandidate, GameplayEventType
from blazzid_core.contracts.observations import Modality, Observation, ObservationProvenance
from blazzid_core.contracts.time import TimeInterval
from blazzid_detection.config import DetectionConfig
from blazzid_detection.models import RawEventTrigger


def create_detector_observation(
    trigger: RawEventTrigger,
    config: DetectionConfig,
) -> Observation:
    """Wraps an intermediate detector trigger into a validated core Observation contract.

    Args:
        trigger: The raw detector trigger.
        config: Active detection configuration.

    Returns:
        Validated Observation instance with Modality.VISUAL and explicit provenance.
    """
    provenance = ObservationProvenance(
        detector_name=trigger.detector_type.value,
        detector_version=config.config_version,
        raw_features=trigger.supporting_features,
        notes=f"Peak intensity={trigger.peak_intensity} at t={trigger.peak_seconds}s",
    )
    interval = TimeInterval(
        start=trigger.start_seconds,
        end=max(trigger.end_seconds, trigger.start_seconds + 0.1),
    )
    return Observation(
        id=str(uuid4()),
        modality=Modality.VISUAL,
        interval=interval,
        confidence=trigger.confidence,
        provenance=provenance,
    )


def build_event_candidate(
    event_type: GameplayEventType,
    interval: TimeInterval,
    trigger_timestamp: float,
    climax_timestamp: Optional[float],
    triggers: list[RawEventTrigger],
    config: DetectionConfig,
    source_duration_seconds: float,
) -> GameplayEventCandidate:
    """Constructs an explainable GameplayEventCandidate with fused multi-detector evidence.

    Confidence Calibration Formula:
    $$c_{\\text{fused}} = \\min\\left(0.98, \\max(c_i) + 0.10 \\cdot (K - 1) - \\text{penalty}_{\\text{coverage}}\\right)$$
    where:
    - $\\max(c_i)$ is the highest confidence among contributing detector triggers.
    - $K$ is the number of distinct contributing detector sub-engines (corroboration bonus).
    - $\\text{penalty}_{\\text{coverage}}$ penalizes events clipped against recording edges.

    Args:
        event_type: Classified gameplay event category.
        interval: Narrative temporal interval [start, end).
        trigger_timestamp: Instantaneous moment the event began or crossed threshold.
        climax_timestamp: Peak action timestamp (must lie within interval).
        triggers: List of raw detector triggers contributing to this candidate.
        config: Active detection configuration.
        source_duration_seconds: Total duration of the recording.

    Returns:
        Fully validated GameplayEventCandidate.
    """
    # 1. Base confidence from strongest trigger
    base_conf = max((t.confidence for t in triggers), default=0.30)

    # 2. Corroboration bonus for multi-detector consensus
    detector_types = {t.detector_type.value for t in triggers}
    corroboration_bonus = 0.08 * max(0, len(detector_types) - 1)

    # 3. Penalize extreme temporal edge clipping
    edge_penalty = 0.0
    if interval.start <= 0.05 or interval.end >= (source_duration_seconds - 0.05):
        edge_penalty = 0.05

    composite_conf = max(0.10, min(0.98, base_conf + corroboration_bonus - edge_penalty))
    valid_conf = validate_confidence(composite_conf)

    # 4. Generate observation evidence provenance
    evidence_sources = [create_detector_observation(t, config) for t in triggers]

    # 5. Peak intensity
    peak_intensity = max((t.peak_intensity for t in triggers), default=0.0)

    metadata: dict[str, Any] = {
        "scoring_breakdown": {
            "base_confidence": round(base_conf, 4),
            "corroboration_bonus": round(corroboration_bonus, 4),
            "edge_penalty": round(edge_penalty, 4),
            "peak_intensity": round(peak_intensity, 4),
        },
        "contributing_detectors": sorted(detector_types),
        "source_frame_count": sum(len(t.frame_indices) for t in triggers),
        "detector_version": config.config_version,
    }

    # Ensure trigger and climax timestamps lie strictly inside [interval.start, interval.end)
    safe_trigger = max(interval.start, min(interval.end - 1e-3, trigger_timestamp))
    safe_climax = (
        max(interval.start, min(interval.end - 1e-3, climax_timestamp))
        if climax_timestamp is not None
        else None
    )

    return GameplayEventCandidate(
        id=str(uuid4()),
        event_type=event_type,
        trigger_timestamp=safe_trigger,
        interval=interval,
        climax_timestamp=safe_climax,
        composite_confidence=valid_conf,
        evidence_sources=evidence_sources,
        metadata=metadata,
    )
