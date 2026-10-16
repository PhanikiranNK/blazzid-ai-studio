"""High-level GameplayEventDetector entry point integrating Stage 2 artifacts."""

from __future__ import annotations

import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Optional, Union

import numpy as np

from blazzid_core.contracts.events import GameplayEventCandidate
from blazzid_detection.activity import (
    detect_sustained_combat,
    detect_visual_activity,
    detect_visual_bursts,
)
from blazzid_detection.config import DetectionConfig
from blazzid_detection.features import extract_sequence_features
from blazzid_detection.grouping import group_triggers_into_candidates
from blazzid_detection.models import (
    DetectionDiagnostics,
    DetectionResult,
    FrameFeatureRecord,
    RawEventTrigger,
)
from blazzid_detection.transitions import detect_transitions
from blazzid_media.models import ExtractedFrame, FrameExtractionResult, PipelineResult


class GameplayEventDetector:
    """Orchestrates visual feature extraction and gameplay event detection across video frames."""

    def __init__(self, config: Optional[DetectionConfig] = None) -> None:
        self.config = config or DetectionConfig()

    def detect(
        self,
        media_input: Union[
            PipelineResult,
            FrameExtractionResult,
            Sequence[ExtractedFrame],
            Sequence[tuple[Union[Path, np.ndarray[Any, Any]], float]],
            Path,
            str,
        ],
        *,
        source_duration_seconds: Optional[float] = None,
    ) -> DetectionResult:
        """Executes full gameplay event detection and candidate generation.

        Accepts Stage 2 PipelineResult, FrameExtractionResult, a list of frames,
        or a directory path containing extracted frames.

        Args:
            media_input: Stage 2 pipeline outcome, frame extraction result, or frames directory.
            source_duration_seconds: Total duration of recording in seconds. If None,
                inferred from media_input metadata or last frame timestamp.

        Returns:
            DetectionResult with candidates, diagnostics, and feature records.
        """
        t0 = time.perf_counter()

        # 1. Resolve frame entries and source duration
        frame_entries: list[tuple[Union[Path, np.ndarray[Any, Any]], float]] = []
        resolved_duration = source_duration_seconds

        if isinstance(media_input, PipelineResult):
            resolved_duration = media_input.inspection.container.duration_seconds
            for frame in media_input.frames.frames:
                frame_entries.append((frame.file_path, frame.timestamp_seconds))
        elif isinstance(media_input, FrameExtractionResult):
            for frame in media_input.frames:
                frame_entries.append((frame.file_path, frame.timestamp_seconds))
            if resolved_duration is None and frame_entries:
                resolved_duration = frame_entries[-1][1] + 1.0
        elif isinstance(media_input, list):
            for item in media_input:
                if isinstance(item, ExtractedFrame):
                    frame_entries.append((item.file_path, item.timestamp_seconds))
                elif isinstance(item, tuple) and len(item) == 2:
                    frame_entries.append((item[0], float(item[1])))
            if resolved_duration is None and frame_entries:
                resolved_duration = frame_entries[-1][1] + 1.0
        elif isinstance(media_input, (Path, str)):
            p = Path(media_input)
            if p.is_dir():
                # Discover frame_*.jpg or frame_*.png
                img_files = sorted(
                    [
                        f
                        for f in p.iterdir()
                        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png")
                    ]
                )
                for f in img_files:
                    # Attempt parsing timestamp from standard name: frame_{index:06d}_{timestamp_ms:08d}.jpg
                    parts = f.stem.split("_")
                    ts = 0.0
                    if len(parts) >= 3 and parts[-1].isdigit():
                        ts = int(parts[-1]) / 1000.0
                    frame_entries.append((f, ts))
                if resolved_duration is None and frame_entries:
                    resolved_duration = frame_entries[-1][1] + 1.0
            else:
                raise ValueError(f"Input path '{p}' is not a directory of frames.")
        else:
            raise TypeError(f"Unsupported media_input type: {type(media_input)}")

        # Ensure frames are sorted chronologically by timestamp
        frame_entries.sort(key=lambda x: x[1])

        # Default source duration if still unknown
        if resolved_duration is None or resolved_duration <= 0.0:
            resolved_duration = frame_entries[-1][1] + 1.0 if frame_entries else 0.0

        # Handle empty frame sequence gracefully
        if not frame_entries:
            diagnostics = DetectionDiagnostics(
                total_frames_analyzed=0,
                valid_frames_count=0,
                corrupt_or_missing_frames_count=0,
                source_duration_seconds=resolved_duration,
                temporal_coverage_ratio=0.0,
                mean_sampling_interval_seconds=0.0,
                events_detected_by_type={},
                execution_elapsed_seconds=round(time.perf_counter() - t0, 3),
            )
            return DetectionResult(
                candidates=[],
                diagnostics=diagnostics,
                features=[],
                is_success=True,
            )

        # 2. Extract visual features across all frames
        features: list[FrameFeatureRecord] = extract_sequence_features(frame_entries)
        valid_features = [f for f in features if f.is_valid]
        corrupt_count = len(features) - len(valid_features)

        # 3. Execute independent detectors
        triggers: list[RawEventTrigger] = []
        triggers.extend(detect_visual_activity(features, self.config))
        triggers.extend(detect_visual_bursts(features, self.config))
        triggers.extend(detect_sustained_combat(features, self.config))
        triggers.extend(detect_transitions(features, self.config))

        # 4. Group, expand narrative intervals, and deduplicate candidates
        candidates: list[GameplayEventCandidate] = group_triggers_into_candidates(
            triggers=triggers,
            source_duration_seconds=resolved_duration,
            config=self.config,
        )

        # 5. Compile telemetry diagnostics
        events_by_type: dict[str, int] = {}
        for c in candidates:
            events_by_type[c.event_type.value] = events_by_type.get(c.event_type.value, 0) + 1

        timestamps = [f.timestamp_seconds for f in valid_features]
        time_span = (timestamps[-1] - timestamps[0]) if len(timestamps) > 1 else 0.0
        coverage_ratio = min(1.0, max(0.0, time_span / max(0.1, resolved_duration)))
        mean_interval = (time_span / max(1, len(timestamps) - 1)) if len(timestamps) > 1 else 1.0

        diagnostics = DetectionDiagnostics(
            total_frames_analyzed=len(features),
            valid_frames_count=len(valid_features),
            corrupt_or_missing_frames_count=corrupt_count,
            source_duration_seconds=round(resolved_duration, 3),
            temporal_coverage_ratio=round(coverage_ratio, 4),
            mean_sampling_interval_seconds=round(mean_interval, 3),
            events_detected_by_type=events_by_type,
            execution_elapsed_seconds=round(time.perf_counter() - t0, 3),
        )

        return DetectionResult(
            candidates=candidates,
            diagnostics=diagnostics,
            features=features,
            is_success=True,
        )
