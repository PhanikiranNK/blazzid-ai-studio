"""Abrupt visual transition and scene cut detector."""

from __future__ import annotations

from blazzid_detection.config import DetectionConfig
from blazzid_detection.models import DetectorType, FrameFeatureRecord, RawEventTrigger


def detect_transitions(
    features: list[FrameFeatureRecord],
    config: DetectionConfig,
) -> list[RawEventTrigger]:
    """Identifies sharp scene cuts, respawn screens, and major visual transitions.

    Distinguishes sharp, isolated structural boundary changes from continuous motion
    by checking that both the pixel difference and histogram Bhattacharyya distance
    spike simultaneously.

    Args:
        features: Chronological list of frame feature records.
        config: Operational thresholds and duration bounds.

    Returns:
        List of RawEventTrigger instances with DetectorType.SCENE_TRANSITION.
    """
    if len(features) < 2:
        return []

    triggers: list[RawEventTrigger] = []

    for i in range(1, len(features)):
        f_curr = features[i]
        if not f_curr.is_valid:
            continue

        # Both pixel change and global color histogram must shift substantially
        is_cut = (
            f_curr.frame_difference >= config.transition_difference_threshold
            and f_curr.histogram_distance >= config.transition_hist_distance_threshold
        )

        if is_cut:
            t_curr = f_curr.timestamp_seconds
            t_prev = features[i - 1].timestamp_seconds
            t_mid = (t_curr + t_prev) / 2.0

            # Expand into a tight narrative interval around the cut
            t_start = max(0.0, t_mid - 0.75)
            t_end = t_mid + 0.75

            # Transition intensity composite
            intensity = 0.5 * f_curr.frame_difference + 0.5 * f_curr.histogram_distance
            conf = min(0.95, max(0.40, intensity))

            triggers.append(
                RawEventTrigger(
                    detector_type=DetectorType.SCENE_TRANSITION,
                    start_seconds=round(t_start, 3),
                    end_seconds=round(t_end, 3),
                    peak_seconds=round(t_curr, 3),
                    peak_intensity=round(intensity, 4),
                    raw_score=round(intensity, 4),
                    confidence=round(conf, 4),
                    supporting_features={
                        "frame_difference": round(f_curr.frame_difference, 4),
                        "histogram_distance": round(f_curr.histogram_distance, 4),
                        "transition_frame_index": i,
                    },
                    frame_indices=[i - 1, i],
                )
            )

    return triggers
