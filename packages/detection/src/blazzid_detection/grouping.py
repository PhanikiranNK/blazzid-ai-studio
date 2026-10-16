"""Temporal boundary grouping, interval expansion, and candidate deduplication."""

from __future__ import annotations

from blazzid_core.contracts.events import GameplayEventCandidate, GameplayEventType
from blazzid_core.contracts.time import TimeInterval
from blazzid_detection.config import DetectionConfig
from blazzid_detection.models import DetectorType, RawEventTrigger
from blazzid_detection.scoring import build_event_candidate


def determine_cluster_event_type(triggers: list[RawEventTrigger]) -> GameplayEventType:
    """Classifies the primary event category for a cluster of merged detector triggers."""
    types = {t.detector_type for t in triggers}
    if DetectorType.SUSTAINED_COMBAT in types:
        return GameplayEventType.SUSTAINED_COMBAT
    if DetectorType.VISUAL_BURST in types:
        return GameplayEventType.VISUAL_BURST
    if DetectorType.SCENE_TRANSITION in types:
        return GameplayEventType.SCENE_TRANSITION
    return GameplayEventType.GENERIC_HIGHLIGHT


def group_triggers_into_candidates(
    triggers: list[RawEventTrigger],
    source_duration_seconds: float,
    config: DetectionConfig,
) -> list[GameplayEventCandidate]:
    """Groups, expands, and deduplicates raw triggers into narrative GameplayEventCandidates.

    Features:
    - Sorts triggers by start time.
    - Merges contiguous or proximate triggers within merge_gap_seconds.
    - Applies lead-in and lead-out narrative padding.
    - Clamps boundaries strictly into [0.0, source_duration_seconds].
    - Suppresses duplicate or high-IoU candidates.

    Args:
        triggers: Chronological list of raw detector triggers.
        source_duration_seconds: Total duration of the recording.
        config: Active detection configuration.

    Returns:
        List of finalized, non-redundant GameplayEventCandidate instances.
    """
    if not triggers:
        return []

    # Partition triggers into gameplay action vs scene transition hypotheses
    action_triggers = [t for t in triggers if t.detector_type != DetectorType.SCENE_TRANSITION]
    transition_triggers = [t for t in triggers if t.detector_type == DetectorType.SCENE_TRANSITION]

    def _cluster_triggers(
        raw_list: list[RawEventTrigger],
    ) -> list[GameplayEventCandidate]:
        if not raw_list:
            return []

        sorted_t = sorted(raw_list, key=lambda t: (t.start_seconds, t.end_seconds))
        clusters: list[list[RawEventTrigger]] = []
        current: list[RawEventTrigger] = [sorted_t[0]]
        cluster_end = sorted_t[0].end_seconds

        for t in sorted_t[1:]:
            if t.start_seconds <= (cluster_end + config.merge_gap_seconds):
                current.append(t)
                cluster_end = max(cluster_end, t.end_seconds)
            else:
                clusters.append(current)
                current = [t]
                cluster_end = t.end_seconds

        if current:
            clusters.append(current)

        result: list[GameplayEventCandidate] = []
        for cluster in clusters:
            raw_start = min(t.start_seconds for t in cluster)
            raw_end = max(t.end_seconds for t in cluster)

            pad_start = max(0.0, raw_start - config.lead_in_seconds)
            pad_end = min(source_duration_seconds, raw_end + config.lead_out_seconds)

            if (pad_end - pad_start) < config.min_event_duration_seconds:
                shortfall = config.min_event_duration_seconds - (pad_end - pad_start)
                left_expand = min(pad_start, shortfall / 2.0)
                pad_start -= left_expand
                remaining_shortfall = shortfall - left_expand
                pad_end = min(source_duration_seconds, pad_end + remaining_shortfall)

            if (pad_end - pad_start) > config.max_event_duration_seconds:
                pad_end = pad_start + config.max_event_duration_seconds

            peak_trigger = max(cluster, key=lambda t: t.peak_intensity)
            climax_ts = max(pad_start, min(pad_end - 1e-3, peak_trigger.peak_seconds))
            trigger_ts = max(pad_start, min(pad_end - 1e-3, raw_start))

            if pad_end <= pad_start:
                pad_end = min(source_duration_seconds, pad_start + 0.1)
                if pad_end <= pad_start:
                    continue

            interval = TimeInterval(start=round(pad_start, 3), end=round(pad_end, 3))
            event_type = determine_cluster_event_type(cluster)

            cand = build_event_candidate(
                event_type=event_type,
                interval=interval,
                trigger_timestamp=round(trigger_ts, 3),
                climax_timestamp=round(climax_ts, 3),
                triggers=cluster,
                config=config,
                source_duration_seconds=source_duration_seconds,
            )

            if cand.composite_confidence >= config.min_confidence_threshold:
                result.append(cand)
        return result

    candidates = _cluster_triggers(action_triggers) + _cluster_triggers(transition_triggers)

    # Phase 3: Non-Maximum Suppression / High-IoU Deduplication
    if len(candidates) <= 1:
        return candidates

    deduped: list[GameplayEventCandidate] = []
    # Rank candidates by composite confidence
    candidates.sort(key=lambda c: c.composite_confidence, reverse=True)

    for cand in candidates:
        suppress = False
        for existing in deduped:
            iou = cand.interval.intersection_over_union(existing.interval)
            # Suppress if very high overlap and compatible hypothesis category
            is_same_category = (cand.event_type == GameplayEventType.SCENE_TRANSITION) == (
                existing.event_type == GameplayEventType.SCENE_TRANSITION
            )
            if iou >= 0.70 and is_same_category:
                suppress = True
                break
        if not suppress:
            deduped.append(cand)

    # Sort final candidates chronologically
    deduped.sort(key=lambda c: c.interval.start)
    return deduped
