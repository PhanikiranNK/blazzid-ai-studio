"""BLAZZID AI Studio - Gameplay Event Detection & Candidate Generation.

Stage 3 local visual feature extraction, activity & burst detection,
scene transition classification, and temporal candidate generation.
"""

from blazzid_detection.activity import (
    compute_frame_activity_metric,
    detect_sustained_combat,
    detect_visual_activity,
    detect_visual_bursts,
)
from blazzid_detection.config import DetectionConfig
from blazzid_detection.detector import GameplayEventDetector
from blazzid_detection.features import (
    compute_single_frame_features,
    extract_features_from_path,
    extract_sequence_features,
)
from blazzid_detection.grouping import group_triggers_into_candidates
from blazzid_detection.models import (
    DetectionDiagnostics,
    DetectionResult,
    DetectorType,
    FrameFeatureRecord,
    RawEventTrigger,
)
from blazzid_detection.scoring import build_event_candidate, create_detector_observation
from blazzid_detection.transitions import detect_transitions

__all__ = [
    # Configuration & Public Detector
    "DetectionConfig",
    "GameplayEventDetector",
    # Models
    "DetectorType",
    "FrameFeatureRecord",
    "RawEventTrigger",
    "DetectionDiagnostics",
    "DetectionResult",
    # Feature Extraction
    "compute_single_frame_features",
    "extract_features_from_path",
    "extract_sequence_features",
    "compute_frame_activity_metric",
    # Detectors
    "detect_visual_activity",
    "detect_visual_bursts",
    "detect_sustained_combat",
    "detect_transitions",
    # Grouping & Scoring
    "group_triggers_into_candidates",
    "build_event_candidate",
    "create_detector_observation",
]
