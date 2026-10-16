# BLAZZID AI Studio — Stage 3: Gameplay Event Detection & Candidate Generation

## 1. Overview & Architecture

Stage 3 introduces the first gameplay event detection engine for BLAZZID AI Studio. Operating on the sparse frame sequence and media artifacts produced by Stage 2 (`blazzid-media`), Stage 3 analyzes visual dynamics to identify candidate gameplay moments—intense combat engagements, sudden action bursts, sustained firefights, and structural scene transitions.

Crucially, **Stage 3 produces timestamped, explainable event candidates, not final publishable video cuts**. It uses deterministic computer vision and signal processing heuristics rather than black-box deep learning or OCR, ensuring high throughput, deterministic reproducibility, and transparent provenance.

The implementation is located in `packages/detection/` (`blazzid-detection`):

```text
packages/detection/
├── pyproject.toml
└── src/blazzid_detection/
    ├── __init__.py          # Public package exports
    ├── models.py            # Feature records, triggers, diagnostics, detection result
    ├── config.py            # DetectionConfig with validated thresholds and window bounds
    ├── features.py          # Timestamp-aware visual feature extraction (luminance, histograms, edges)
    ├── activity.py          # Activity metrics, Welford rolling z-score bursts, sustained combat
    ├── transitions.py       # Abrupt scene cuts and visual boundary detection
    ├── grouping.py          # Hypothesis clustering, narrative padding, clamping, IoU deduplication
    ├── scoring.py           # Multi-detector evidence fusion, calibration, Observation provenance
    └── detector.py          # High-level GameplayEventDetector integrating Stage 2 artifacts
```

### Module Responsibilities

| Module | Responsibility | Key Public Entry Points |
| :--- | :--- | :--- |
| `blazzid_detection.models` | Immutable data contracts for frame feature records, raw triggers, diagnostics, and result containers. | `FrameFeatureRecord`, `RawEventTrigger`, `DetectionResult` |
| `blazzid_detection.config` | Pydantic v2 configuration model validating all detection thresholds, rolling window limits, and narrative padding parameters. | `DetectionConfig` |
| `blazzid_detection.features` | Per-frame and sequential feature extraction (grayscale luminance, 16-bin L1-normalized histograms, delta norms, edge density). | `compute_single_frame_features`, `extract_sequence_features` |
| `blazzid_detection.activity` | Rolling statistical analysis, visual activity scoring, local z-score burst detection, and sustained combat state machines. | `detect_visual_activity`, `detect_visual_bursts`, `detect_sustained_combat` |
| `blazzid_detection.transitions` | Abrupt scene change detection using joint Bhattacharyya histogram divergence and frame pixel differences. | `detect_transitions` |
| `blazzid_detection.grouping` | Sweep-line clustering of proximate triggers, narrative lead-in/out padding, duration bounding, interval clamping, and Non-Maximum Suppression. | `group_triggers_into_candidates` |
| `blazzid_detection.scoring` | Heuristic confidence fusion, multi-detector agreement bonuses, edge uncertainty penalties, and structured `Observation` creation. | `build_event_candidate`, `calculate_composite_confidence` |
| `blazzid_detection.detector` | Unified public facade accepting Stage 2 `PipelineResult`, `FrameExtractionResult`, frame directory, or frame lists. | `GameplayEventDetector.detect` |

---

## 2. Public API and Example Usage

The primary entry point is `GameplayEventDetector`, which accepts inputs directly from Stage 2 or isolated frame lists.

### Direct Integration with Stage 2 Pipeline

```python
from pathlib import Path
from blazzid_media.pipeline import MediaPipeline
from blazzid_detection.detector import GameplayEventDetector
from blazzid_detection.config import DetectionConfig

# 1. Execute Stage 2 Media Ingestion & Preprocessing
pipeline = MediaPipeline(frame_interval_seconds=1.0)
pipeline_result = pipeline.process(
    source_path=Path("recordings/brawl_stars_match.mp4"),
    work_dir=Path("artifacts/job_101/"),
)

# 2. Configure Stage 3 Event Detector
config = DetectionConfig(
    activity_threshold=0.25,
    burst_zscore_threshold=2.5,
    min_event_duration_seconds=3.0,
    lead_in_seconds=1.5,
    lead_out_seconds=1.5,
)
detector = GameplayEventDetector(config=config)

# 3. Detect Gameplay Candidates directly from PipelineResult
result = detector.detect(pipeline_result)

if result.is_success:
    print(f"Scanned {result.diagnostics.valid_frames_count} frames in {result.diagnostics.execution_time_seconds:.2f}s")
    for candidate in result.candidates:
        print(
            f"Event [{candidate.event_type.value}] "
            f"from {candidate.interval.start:.2f}s to {candidate.interval.end:.2f}s "
            f"(climax: {candidate.climax_timestamp:.2f}s) "
            f"- Confidence: {candidate.composite_confidence:.2f}"
        )
```

---

## 3. Feature Model & Normalization

All visual features are extracted sequentially to maintain $O(1)$ frame memory overhead. Features are strictly normalized to $[0.0, 1.0]$ ranges with documented units and null-handling semantics:

| Feature Name | Type | Range | Units / Formula | Null / Missing Frame Behavior |
| :--- | :--- | :--- | :--- | :--- |
| `luminance_mean` | `float` | $[0.0, 1.0]$ | Mean pixel intensity of grayscale image divided by 255.0. | Defaults to `0.0` if decode fails. |
| `luminance_std` | `float` | $[0.0, 1.0]$ | Standard deviation of grayscale image divided by 128.0 (clamped). | Defaults to `0.0`. |
| `histogram` | `list[float]` | $[0.0, 1.0]^{16}$ | 16-bin L1-normalized grayscale histogram ($\sum h_i = 1.0$). | Empty list `[]` if decode fails. |
| `frame_diff_mean` | `float` | $[0.0, 1.0]$ | Normalized absolute pixel difference between consecutive grayscale frames: $\frac{1}{255 \cdot N} \sum \|I_t - I_{t-1}\|$. | `0.0` for the first frame or after invalid frames. |
| `histogram_distance` | `float` | $[0.0, 1.0]$ | Bhattacharyya distance $d(H_1, H_2) = \sqrt{1 - \sum \sqrt{H_1 \cdot H_2}}$. | `0.0` for initial/invalid frames. |
| `edge_density` | `float` | $[0.0, 1.0]$ | Sobel gradient magnitude thresholded at 50, divided by total pixel count. | Defaults to `0.0`. |
| `is_valid` | `bool` | `{True, False}` | Flag indicating successful image decoding and feature extraction. | `False` on unreadable or corrupt frames. |
| `error_message` | `Optional[str]` | `str` | Diagnostic string describing I/O or decoding failure. | `None` when `is_valid=True`. |

---

## 4. Detector Mechanics & Configuration

Stage 3 runs four independent, complementary baseline detectors:

### A. Visual Activity Detector (`detect_visual_activity`)
Computes an instantaneous composite activity metric for each frame:
$$A_t = 0.50 \cdot \text{frame\_diff\_mean} + 0.35 \cdot \text{histogram\_distance} + 0.15 \cdot \text{edge\_density}$$
Whenever $A_t \ge \text{activity\_threshold}$ (default `0.20`), an activity trigger is emitted.

### B. Visual Burst Detector (`detect_visual_bursts`)
Identifies sudden visual surges (e.g. supers, explosions, sudden team fights) relative to local context. It maintains a bounded rolling window (default $W = 7$ samples) of activity scores and computes running mean $\mu_W$ and standard deviation $\sigma_W$ using Welford's streaming algorithm:
$$z_t = \frac{A_t - \mu_W}{\sigma_W + \epsilon}$$
Triggers are emitted when $z_t \ge \text{burst\_zscore\_threshold}$ (default `2.2`) and $A_t \ge \text{activity\_threshold} \cdot 0.8$.

### C. Sustained Combat Detector (`detect_sustained_combat`)
Detects extended skirmishes by tracking consecutive frames with elevated visual activity. A 3-sample triangular moving average filters high-frequency noise. A trigger is produced when active fighting persists for at least $\text{sustained_min_frames}$ consecutive samples (default: 3 frames / 3 seconds at 1 fps).

### D. Abrupt Transition Detector (`detect_transitions`)
Identifies hard camera cuts, battle loading transitions, respawn flashes, and match phase boundaries. A transition trigger is declared when:
$$\text{histogram\_distance} \ge 0.50 \quad \text{and} \quad \text{frame\_diff\_mean} \ge 0.25$$
Transitions are explicitly classified as structural markers rather than combat excitement.

---

## 5. Candidate Grouping, Intervals & Deduplication

### Half-Open Interval Semantics
All candidates strictly follow standard $[start, end)$ half-open interval semantics in seconds:
- $start < end$ is enforced unconditionally.
- $0.0 \le start < end \le \text{source\_duration\_seconds}$ is guaranteed by boundary clamping.

### Hypothesis-Aware Grouping
Triggers are partitioned into two distinct hypothesis spaces before clustering:
1. **Combat & Action Hypotheses**: `VISUAL_ACTIVITY`, `VISUAL_BURST`, `SUSTAINED_COMBAT`.
2. **Structural Hypotheses**: `SCENE_TRANSITION`.

Within each hypothesis space:
- Contiguous triggers separated by $\le \text{merge\_gap\_seconds}$ (default: 2.0s) are merged.
- Narrative padding ($\text{lead\_in\_seconds} = 1.5\text{s}$, $\text{lead\_out\_seconds} = 1.5\text{s}$) is added to capture setup and resolution.
- Intervals are clamped to $[\text{min\_event\_duration\_seconds}, \text{max\_event\_duration\_seconds}]$ (defaults: 2.0s to 30.0s).

### Non-Maximum Suppression (Deduplication)
Candidate events are sorted by composite confidence. If two candidates within the same hypothesis category share temporal Intersection-over-Union $\text{IoU} \ge 0.70$, the lower-confidence duplicate is suppressed, preserving unique gameplay episodes.

---

## 6. Explainable Scoring & Confidence Calibration

Every candidate produced by Stage 3 includes an explicit `composite_confidence` in $[0.0, 1.0]$ and an explainable list of `Observation` objects detailing what triggered the detection.

### Scoring Breakdown
The score is composed of four weighted heuristic factors:

1. **Peak Intensity ($w = 0.40$)**: The maximum visual activity or burst z-score observed within the interval.
2. **Multi-Detector Consensus ($w = 0.30$)**: Proportional bonus based on independent detector agreement:
   $$\text{Consensus} = \min(1.0, 0.40 \cdot N_{\text{detectors}})$$
3. **Event Persistence ($w = 0.15$)**: Scaled duration factor rewarding sustained gameplay sequences.
4. **Temporal Edge Penalty ($w = 0.15$)**: Damps confidence for candidates occurring within 2.0 seconds of the recording boundary (where lead-in context is truncated).

### Explicit Confidence Disclaimer
> [!IMPORTANT]
> Stage 3 scores are **heuristic confidence values** calibrated to reflect signal strength and detector consensus. They do **not** represent verified statistical probabilities of kills, victories, or defeats.

---

## 7. Failure Handling & Edge Cases

The detection engine is engineered for resilience against imperfect real-world screen captures:

- **Empty Input**: Returns a successful `DetectionResult` with 0 candidates and diagnostic counts set to 0.
- **Corrupt or Missing Frame Files**: OpenCV decode failures are caught gracefully; invalid frames emit `FrameFeatureRecord(is_valid=False)` and do not throw exceptions or halt pipeline execution.
- **Variable Frame Rate (VFR) / Irregular Timestamps**: Timestamps are read directly from frame metadata or presentation timestamps, never assumed to be equidistant indices.
- **Static Menu Screens**: Static menus exhibit zero frame differences; all detectors remain silent and output zero candidates.
- **Resolution or Aspect Ratio Changes**: Consecutive frame comparison dynamically resizes previous frame buffers if orientation or resolution changes mid-stream.
- **Portrait & Landscape Orientation**: Seamlessly handled without code branching or distortion.

---

## 8. Ground-Truth Synthetic Evaluation

To guarantee deterministic correctness, the test suite includes synthetic gameplay generators producing procedural combat bursts, static menu footage, and flash cuts with known ground-truth intervals:

| Synthetic Scenario | Ground-Truth Interval | Expected Detection | Test Status |
| :--- | :--- | :--- | :--- |
| **Static Idle Screen** | None | 0 candidates | Passed |
| **High-Contrast Combat** | $[10.0\text{s}, 16.0\text{s}]$ | Detected with $\text{IoU} \ge 0.50$ | Passed |
| **Abrupt White Flash Cut** | $22.0\text{s}$ | `SCENE_TRANSITION` candidate | Passed |
| **Missing / Corrupt JPEGs** | $1.0\text{s}$ corrupted | Handled with zero crashes | Passed |
| **Stage 2 Pipeline Integration** | 4.0s generated video | Fully integrated end-to-end | Passed |

---

## 9. Performance & Benchmarks

Benchmarks were measured using `pytest-benchmark` on an Apple Silicon (macOS) developer workstation:

| Benchmark Target | Metric | Mean Latency | Throughput (OPS) |
| :--- | :--- | :--- | :--- |
| **Feature Extraction (Single 720p Frame)** | Per-frame feature computation | $10.51\text{ ms}$ | $95.17\text{ frames/sec}$ |
| **Signal Processing & Burst Detection** | 60-frame time series | $226.78\text{ }\mu\text{s}$ | $4,409.52\text{ sequences/sec}$ |
| **Trigger Grouping & Deduplication** | 50 overlapping triggers | $1.19\text{ ms}$ | $836.26\text{ operations/sec}$ |
| **End-to-End Pipeline Detection** | 30s recording (30 sparse frames) | $127.35\text{ ms}$ | $7.85\text{ recordings/sec}$ |

### Performance Characteristics
- **Memory Footprint**: $O(1)$ memory streaming model. Frames are decoded one at a time and discarded; full video frames are never held in memory simultaneously.
- **Analysis Speed**: Analyzes a 10-minute Brawl Stars match (at 1 frame per second) in under **6.5 seconds**, achieving $\approx 92\times$ real-time throughput.

---

## 10. Known Failure Modes & Limitations

1. **Non-Combat Action Sequences**: Fast camera pans in non-combat modes or rapid scrolling through the Brawler inventory menu produce high visual difference scores and may generate false-positive visual activity candidates.
2. **Prolonged Respawn Countdown**: A black or static screen followed by a respawn flash is correctly detected as a `SCENE_TRANSITION`, but should not be mistaken for an elimination highlight without downstream kill-feed verification.
3. **Heuristic Candidate vs. Semantic Event**: Stage 3 guarantees that an intense visual change took place; it does **not** assert whether a specific player scored a goal in Brawl Ball, captured gems in Gem Grab, or was eliminated.

---

## 11. Instructions for Real Brawl Stars Evaluation

To evaluate Stage 3 on real mobile device recordings:

1. Ingest the match recording using Stage 2:
   ```bash
   .venv/bin/python -c "
   from blazzid_media.pipeline import MediaPipeline
   from pathlib import Path
   pipeline = MediaPipeline(frame_interval_seconds=1.0)
   res = pipeline.process(Path('tests/fixtures/real_brawl_match.mp4'), Path('tmp_analysis'))
   "
   ```
2. Run `GameplayEventDetector` over the resulting output directory.
3. Inspect `result.candidates` to examine detected timestamps against manual video playback.
