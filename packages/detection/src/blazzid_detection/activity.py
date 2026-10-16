"""Visual activity, burst, and sustained combat detectors."""

from __future__ import annotations

from blazzid_algorithms.rolling_statistics import compute_rolling_stats
from blazzid_detection.config import DetectionConfig
from blazzid_detection.models import DetectorType, FrameFeatureRecord, RawEventTrigger


def compute_frame_activity_metric(feature: FrameFeatureRecord) -> float:
    """Computes a balanced, normalized visual activity intensity in [0.0, 1.0].

    Weights:
    - 50% temporal pixel difference (direct motion & visual changes)
    - 30% histogram distance (color/lighting shift)
    - 20% spatial edge gradient density (scene complexity/effects)
    """
    if not feature.is_valid:
        return 0.0

    score = (
        0.50 * feature.frame_difference
        + 0.30 * feature.histogram_distance
        + 0.20 * feature.edge_density
    )
    return max(0.0, min(1.0, score))


def detect_visual_activity(
    features: list[FrameFeatureRecord],
    config: DetectionConfig,
) -> list[RawEventTrigger]:
    """Detects contiguous intervals of elevated visual motion and graphical activity.

    Args:
        features: Chronological list of frame feature records.
        config: Operational thresholds and duration bounds.

    Returns:
        List of RawEventTrigger instances with DetectorType.VISUAL_ACTIVITY.
    """
    if len(features) < 2:
        return []

    activity_scores = [compute_frame_activity_metric(f) for f in features]
    triggers: list[RawEventTrigger] = []

    in_event = False
    start_idx = 0
    peak_idx = 0
    max_score = 0.0

    for i, score in enumerate(activity_scores):
        if score >= config.activity_threshold:
            if not in_event:
                in_event = True
                start_idx = i
                peak_idx = i
                max_score = score
            else:
                if score > max_score:
                    max_score = score
                    peak_idx = i
        else:
            if in_event:
                in_event = False
                end_idx = i - 1
                t_start = features[start_idx].timestamp_seconds
                t_end = features[end_idx].timestamp_seconds
                # Enforce minimum duration
                if (t_end - t_start) >= config.min_event_duration_seconds:
                    t_peak = features[peak_idx].timestamp_seconds
                    conf = min(1.0, max_score * 1.2)
                    triggers.append(
                        RawEventTrigger(
                            detector_type=DetectorType.VISUAL_ACTIVITY,
                            start_seconds=round(t_start, 3),
                            end_seconds=round(t_end, 3),
                            peak_seconds=round(t_peak, 3),
                            peak_intensity=round(max_score, 4),
                            raw_score=round(max_score, 4),
                            confidence=round(conf, 4),
                            supporting_features={
                                "mean_activity": round(
                                    float(
                                        sum(activity_scores[start_idx:i]) / max(1, i - start_idx)
                                    ),
                                    4,
                                ),
                                "max_activity": round(max_score, 4),
                                "duration_seconds": round(t_end - t_start, 3),
                            },
                            frame_indices=list(range(start_idx, i)),
                        )
                    )

    # Final interval trailing to stream end
    if in_event:
        end_idx = len(features) - 1
        t_start = features[start_idx].timestamp_seconds
        t_end = features[end_idx].timestamp_seconds
        if (t_end - t_start) >= config.min_event_duration_seconds:
            t_peak = features[peak_idx].timestamp_seconds
            conf = min(1.0, max_score * 1.2)
            triggers.append(
                RawEventTrigger(
                    detector_type=DetectorType.VISUAL_ACTIVITY,
                    start_seconds=round(t_start, 3),
                    end_seconds=round(t_end, 3),
                    peak_seconds=round(t_peak, 3),
                    peak_intensity=round(max_score, 4),
                    raw_score=round(max_score, 4),
                    confidence=round(conf, 4),
                    supporting_features={
                        "mean_activity": round(
                            float(
                                sum(activity_scores[start_idx:]) / max(1, len(features) - start_idx)
                            ),
                            4,
                        ),
                        "max_activity": round(max_score, 4),
                        "duration_seconds": round(t_end - t_start, 3),
                    },
                    frame_indices=list(range(start_idx, len(features))),
                )
            )

    return triggers


def detect_visual_bursts(
    features: list[FrameFeatureRecord],
    config: DetectionConfig,
) -> list[RawEventTrigger]:
    """Detects sudden, high-intensity activity bursts using adaptive rolling z-scores.

    Identifies localized anomalous activity exceeding moving baseline statistics.

    Args:
        features: Chronological list of frame feature records.
        config: Operational thresholds and duration bounds.

    Returns:
        List of RawEventTrigger instances with DetectorType.VISUAL_BURST.
    """
    if len(features) < 4:
        return []

    activity_scores = [compute_frame_activity_metric(f) for f in features]

    # Approximate window size in frame counts (assuming ~1 fps or median sampling step)
    time_deltas = [
        features[i + 1].timestamp_seconds - features[i].timestamp_seconds
        for i in range(len(features) - 1)
        if features[i + 1].timestamp_seconds > features[i].timestamp_seconds
    ]
    median_step = float(sorted(time_deltas)[len(time_deltas) // 2]) if time_deltas else 1.0
    window_frames = max(3, int(round(config.rolling_window_seconds / max(0.1, median_step))))

    stats = compute_rolling_stats(activity_scores, window_size=window_frames)
    z_scores = stats.z_scores

    triggers: list[RawEventTrigger] = []
    i = 0
    n = len(features)

    while i < n:
        if (
            z_scores[i] >= config.activity_z_score_threshold
            and activity_scores[i] >= config.activity_threshold
        ):
            start_idx = i
            peak_idx = i
            max_z = z_scores[i]
            max_act = activity_scores[i]

            while i < n and (
                z_scores[i] >= config.activity_z_score_threshold * 0.7
                or activity_scores[i] >= config.activity_threshold * 0.8
            ):
                if z_scores[i] > max_z:
                    max_z = z_scores[i]
                    max_act = activity_scores[i]
                    peak_idx = i
                i += 1

            end_idx = i - 1
            t_start = features[start_idx].timestamp_seconds
            t_end = features[end_idx].timestamp_seconds
            t_peak = features[peak_idx].timestamp_seconds

            # Saturated heuristic confidence based on z-score magnitude: z=1.5 -> 0.50, z=3.0 -> 0.85
            conf = min(0.95, max(0.30, 0.30 + (max_z - config.activity_z_score_threshold) * 0.20))

            triggers.append(
                RawEventTrigger(
                    detector_type=DetectorType.VISUAL_BURST,
                    start_seconds=round(t_start, 3),
                    end_seconds=round(max(t_end, t_start + 1.0), 3),
                    peak_seconds=round(t_peak, 3),
                    peak_intensity=round(max_act, 4),
                    raw_score=round(max_z, 4),
                    confidence=round(conf, 4),
                    supporting_features={
                        "max_z_score": round(max_z, 3),
                        "peak_activity": round(max_act, 4),
                        "local_mean": round(stats.means[peak_idx], 4),
                        "local_stdev": round(stats.stds[peak_idx], 4),
                    },
                    frame_indices=list(range(start_idx, end_idx + 1)),
                )
            )
        else:
            i += 1

    return triggers


def detect_sustained_combat(
    features: list[FrameFeatureRecord],
    config: DetectionConfig,
) -> list[RawEventTrigger]:
    """Detects multi-second prolonged combat episodes with sustained high visual activity."""
    if len(features) < 4:
        return []

    activity_scores = [compute_frame_activity_metric(f) for f in features]
    triggers: list[RawEventTrigger] = []

    # Compute 3-sample moving average
    kernel_size = 3
    smoothed: list[float] = []
    for i in range(len(activity_scores)):
        window = activity_scores[max(0, i - kernel_size + 1) : i + 1]
        smoothed.append(sum(window) / len(window))

    in_combat = False
    start_idx = 0
    peak_idx = 0
    max_smoothed = 0.0

    for i, val in enumerate(smoothed):
        is_active = val >= config.sustained_activity_ratio and activity_scores[i] >= (
            config.activity_threshold * 0.6
        )
        if is_active:
            if not in_combat:
                in_combat = True
                start_idx = i
                peak_idx = i
                max_smoothed = val
            else:
                if val > max_smoothed:
                    max_smoothed = val
                    peak_idx = i
        else:
            if in_combat:
                in_combat = False
                end_idx = i - 1
                t_start = features[start_idx].timestamp_seconds
                t_end = features[end_idx].timestamp_seconds
                dur = t_end - t_start
                count_elevated = sum(
                    1
                    for idx in range(start_idx, i)
                    if activity_scores[idx] >= config.activity_threshold
                )
                if dur >= config.min_event_duration_seconds and count_elevated >= 3:
                    t_peak = features[peak_idx].timestamp_seconds
                    conf = min(0.90, max(0.40, max_smoothed * 2.0))
                    triggers.append(
                        RawEventTrigger(
                            detector_type=DetectorType.SUSTAINED_COMBAT,
                            start_seconds=round(t_start, 3),
                            end_seconds=round(t_end, 3),
                            peak_seconds=round(t_peak, 3),
                            peak_intensity=round(max_smoothed, 4),
                            raw_score=round(max_smoothed * dur, 4),
                            confidence=round(conf, 4),
                            supporting_features={
                                "duration_seconds": round(dur, 3),
                                "peak_smoothed_activity": round(max_smoothed, 4),
                                "elevated_frames_count": count_elevated,
                            },
                            frame_indices=list(range(start_idx, i)),
                        )
                    )

    if in_combat:
        end_idx = len(features) - 1
        t_start = features[start_idx].timestamp_seconds
        t_end = features[end_idx].timestamp_seconds
        dur = t_end - t_start
        count_elevated = sum(
            1
            for idx in range(start_idx, len(features))
            if activity_scores[idx] >= config.activity_threshold
        )
        if dur >= config.min_event_duration_seconds and count_elevated >= 3:
            t_peak = features[peak_idx].timestamp_seconds
            conf = min(0.90, max(0.40, max_smoothed * 2.0))
            triggers.append(
                RawEventTrigger(
                    detector_type=DetectorType.SUSTAINED_COMBAT,
                    start_seconds=round(t_start, 3),
                    end_seconds=round(t_end, 3),
                    peak_seconds=round(t_peak, 3),
                    peak_intensity=round(max_smoothed, 4),
                    raw_score=round(max_smoothed * dur, 4),
                    confidence=round(conf, 4),
                    supporting_features={
                        "duration_seconds": round(dur, 3),
                        "peak_smoothed_activity": round(max_smoothed, 4),
                        "elevated_frames_count": count_elevated,
                    },
                    frame_indices=list(range(start_idx, len(features))),
                )
            )

    return triggers
