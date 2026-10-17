# BLAZZID AI Studio

> **AI-Powered Gaming Video Intelligence Platform**  
> *Transforming long gaming recordings into high-quality, ranked, context-aware, publish-ready highlights.*

---

## 1. Executive Overview

**BLAZZID AI Studio** is an enterprise-grade media intelligence and automated video editing platform. While initialized with specialized support for **Brawl Stars** (fast-paced mobile 3v3 and battle royale gameplay), the platform is architected around a domain-agnostic, multimodal evidence fusion framework capable of expanding to competitive tactical shooters, MOBAs, and sports titles.

### Core Architectural Principles
1. **Multimodal Evidence over Black-Box Magic:** We reject end-to-end "black-box" highlight classification. Highlights are detected via calibrated evidence fusion across audio energy, visual HUD state transitions, and game OCR with full audit provenance.
2. **Context-Aware Temporal Optimization:** Highlights follow a three-act narrative structure (Setup $\to$ Climax $\to$ Payoff) assembled via Dynamic Programming Weighted Interval Scheduling to guarantee zero clip overlap within strict duration budgets.
3. **Pragmatic Production Topology:** The platform adopts a modular monolith codebase deployed as two runtime artifacts: a lightweight, responsive **Studio Web & API Service**, and a horizontally scalable **Media & AI Worker Pool** managed via Redis Streams and KEDA on Kubernetes.

---

## 2. Project Status & Stage Completion

- [x] **Stage 0: Principal Architecture & Engineering Design** (Complete — see [`docs/`](./docs/))
- [x] **Stage 1: Repository Foundation, Contracts & Core Algorithms** (Complete — see [`docs/algorithm-implementation.md`](./docs/algorithm-implementation.md))
- [x] **Stage 2: Media Ingestion, Preprocessing & Fast Video Analysis** (Complete — see [`docs/media-pipeline.md`](./docs/media-pipeline.md))
- [x] **Stage 3: Gameplay Event Detection & Candidate Generation** (Complete — see [`docs/gameplay-event-detection.md`](./docs/gameplay-event-detection.md))
- [x] **Stage 4: Highlight Ranking, Duration-Budgeted Selection & Montage Assembly** (Complete — see [`docs/highlight-assembly.md`](./docs/highlight-assembly.md))
- [ ] **Stage 5: Production Service Architecture & Distributed Job Orchestration** (Pending explicit approval)

---

## 3. Quickstart & Developer Workflow

### Environment Setup
```bash
# 1. Create and activate a Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install editable packages and development dependencies
pip install --upgrade pip
pip install -e packages/core -e packages/algorithms -e packages/media -e packages/detection -e packages/assembly
pip install "pytest>=8.0.0" "hypothesis>=6.98.0" "pytest-benchmark>=4.0.0" "ruff>=0.3.0" "mypy>=1.9.0"
```

### Quality Gate Commands (From Repository Root)
```bash
# Formatting & Linting
.venv/bin/ruff format --check .
.venv/bin/ruff check .

# Strict Type Checking (mypy --strict across all packages, test suites, and benchmarks)
.venv/bin/mypy --strict packages/core/src packages/algorithms/src packages/media/src packages/detection/src packages/assembly/src tests benchmarks

# Complete Test Suite (152 tests: unit, property, synthetic media, and pipeline integration)
.venv/bin/pytest -v tests

# Repeatable Performance Benchmarks (17 benchmarks)
.venv/bin/pytest -v benchmarks
```

---

## 4. Repository Structure

```text
├── pyproject.toml                         # Root tooling & dependency configuration
├── .python-version                        # Python target version (3.9)
├── packages/
│   ├── core/                              # blazzid-core: shared domain contracts & DTOs
│   │   ├── pyproject.toml
│   │   └── src/blazzid_core/
│   │       ├── contracts/                 # TimeInterval, Confidence, Observations, Events, Selection
│   │       └── errors.py                  # DomainValidationError, IntervalError, BudgetConstraintError
│   ├── algorithms/                        # blazzid-algorithms: pure mathematical primitives
│   │   ├── pyproject.toml
│   │   └── src/blazzid_algorithms/
│   │       ├── top_k.py                   # Bounded min-heap streaming selector (O(M log K))
│   │       ├── interval_selection.py      # 2D DP Weighted Interval Scheduling & Exhaustive Oracle
│   │       ├── rolling_statistics.py      # Numerically stabilized rolling stats & z-scores
│   │       └── perceptual_hash.py         # 64-bit Hamming distance & visual similarity
│   ├── media/                             # blazzid-media: Stage 2 media ingestion & preprocessing
│   │   ├── pyproject.toml
│   │   └── src/blazzid_media/
│   │       ├── validation.py              # File bounds, safe paths & traversal prevention
│   │       ├── probe.py                   # ffprobe stream inspection & CFR/VFR empirical pacing
│   │       ├── preprocessing.py           # 720p 30fps H.264 proxy & 16kHz mono audio extraction
│   │       ├── frames.py                  # Timestamp-aware sparse frame extraction via OpenCV
│   │       ├── waveform.py                # Bounded-buffer waveform peak & RMS generation
│   │       ├── pipeline.py                # Composable local MediaPipeline orchestrator
│   │       ├── models.py                  # Pydantic v2 metadata & pipeline result schemas
│   │       └── errors.py                  # Structured domain media exceptions
│   ├── detection/                         # blazzid-detection: Stage 3 gameplay event detection
│   │   ├── pyproject.toml
│   │   └── src/blazzid_detection/
│   │       ├── models.py                  # FrameFeatureRecord, RawEventTrigger, DetectionResult
│   │       ├── config.py                  # Validated DetectionConfig thresholds and window sizes
│   │       ├── features.py                # Normalized visual feature extraction (luminance, hist, Sobel)
│   │       ├── activity.py                # Activity metrics, Welford rolling z-score bursts & combat
│   │       ├── transitions.py             # Abrupt scene cuts & visual boundary detection
│   │       ├── grouping.py                # Hypothesis clustering, narrative padding & NMS deduplication
│   │       ├── scoring.py                 # Multi-detector evidence calibration & Observation provenance
│   │       └── detector.py                # Public GameplayEventDetector orchestrator
│   └── assembly/                          # blazzid-assembly: Stage 4 ranking, selection & montage rendering
│       ├── pyproject.toml
│       └── src/blazzid_assembly/
│           ├── models.py                  # RankedCandidate, PlannedClip, EditPlan, ValidationReport, EditManifest
│           ├── config.py                  # Predefined profiles (16:9, 9:16), AssemblyConfig, RankingConfig
│           ├── ranking.py                 # Multi-factor highlight scoring & explainable ranking
│           ├── selection.py               # Constrained 2D DP selection with structured exclusion audits
│           ├── planning.py                # Context lead-in/out padding & montage timeline mapping
│           ├── rendering.py               # Subprocess FFmpeg clip extraction, aspect padding & concat
│           ├── validation.py              # ffprobe stream inspection & headless decode smoke tests
│           ├── pipeline.py                # Unified HighlightAssemblyPipeline orchestrator
│           └── errors.py                  # Structured domain assembly & render exceptions
├── tests/
│   ├── unit/                              # Isolated component & boundary tests (126 tests)
│   ├── property/                          # Hypothesis mathematical invariant tests (12 tests)
│   ├── integration/                       # End-to-end Pipeline & Assembly tests (14 tests)
│   └── fixtures/                          # Synthetic FFmpeg video & gameplay test fixtures
├── benchmarks/                            # pytest-benchmark performance test suite (17 benchmarks)
└── docs/                                  # Complete Stage 0, Stage 1, Stage 2, Stage 3 & Stage 4 records
```

---

## 5. Stage Deliverables & Acceptance Verification

| Capability / Requirement | Implementation Module | Verification Test Suite | Benchmark Performance |
| :--- | :--- | :--- | :--- |
| **Top-$K$ Selection** | [`top_k.py`](./packages/algorithms/src/blazzid_algorithms/top_k.py) | [`test_top_k.py`](./tests/unit/test_top_k.py)<br>[`test_top_k_properties.py`](./tests/property/test_top_k_properties.py) | **$1,627,000\text{ items/s}$** ($6.14\text{ms}$ per 10k items) |
| **Weighted Interval Scheduling** | [`interval_selection.py`](./packages/algorithms/src/blazzid_algorithms/interval_selection.py) | [`test_interval_selection.py`](./tests/unit/test_interval_selection.py)<br>[`test_interval_selection_properties.py`](./tests/property/test_interval_selection_properties.py) | **$10.78\text{ms}$** ($100$ clips, $360$ capacity bins) |
| **Rolling Statistics** | [`rolling_statistics.py`](./packages/algorithms/src/blazzid_algorithms/rolling_statistics.py) | [`test_rolling_statistics.py`](./tests/unit/test_rolling_statistics.py)<br>[`test_rolling_statistics_properties.py`](./tests/property/test_rolling_statistics_properties.py) | **$893,000\text{ samples/s}$** ($55.93\text{ms}$ per 50k samples) |
| **64-bit Hash Distance** | [`perceptual_hash.py`](./packages/algorithms/src/blazzid_algorithms/perceptual_hash.py) | [`test_perceptual_hash.py`](./tests/unit/test_perceptual_hash.py)<br>[`test_perceptual_hash_properties.py`](./tests/property/test_perceptual_hash_properties.py) | **$1,515,000\text{ comparisons/s}$** ($6.59\text{ms}$ per 10k pairs) |
| **Media Probing & VFR Pacing** | [`probe.py`](./packages/media/src/blazzid_media/probe.py) | [`test_probe.py`](./tests/unit/test_probe.py) | **$62.00\text{ms}$** per file inspection |
| **Analysis Proxy Transcode** | [`preprocessing.py`](./packages/media/src/blazzid_media/preprocessing.py) | [`test_preprocessing.py`](./tests/unit/test_preprocessing.py) | **$352.68\text{ms}$** (3s 720p H.264) |
| **16kHz Mono WAV Extraction** | [`preprocessing.py`](./packages/media/src/blazzid_media/preprocessing.py) | [`test_preprocessing.py`](./tests/unit/test_preprocessing.py) | **$32.11\text{ms}$** per stream extraction |
| **Sparse Keyframe Extraction** | [`frames.py`](./packages/media/src/blazzid_media/frames.py) | [`test_frames.py`](./tests/unit/test_frames.py) | **$52.70\text{ms}$** (3 keyframes via OpenCV) |
| **Waveform Peak Generation** | [`waveform.py`](./packages/media/src/blazzid_media/waveform.py) | [`test_waveform.py`](./tests/unit/test_waveform.py) | **$1.28\text{ms}$** ($776\text{ ops/s}$ on 10s audio) |
| **End-to-End MediaPipeline** | [`pipeline.py`](./packages/media/src/blazzid_media/pipeline.py) | [`test_media_pipeline.py`](./tests/integration/test_media_pipeline.py) | **$515.94\text{ms}$** (~6x faster than realtime) |
| **Visual Feature Extraction** | [`features.py`](./packages/detection/src/blazzid_detection/features.py) | [`test_detection_features.py`](./tests/unit/test_detection_features.py) | **$10.51\text{ms}$** ($95\text{ frames/s}$) |
| **Signal Burst & Combat State** | [`activity.py`](./packages/detection/src/blazzid_detection/activity.py) | [`test_detection_activity.py`](./tests/unit/test_detection_activity.py) | **$226.78\text{ }\mu\text{s}$** ($4,409\text{ seq/s}$) |
| **Hypothesis Clustering & NMS** | [`grouping.py`](./packages/detection/src/blazzid_detection/grouping.py) | [`test_detection_grouping.py`](./tests/unit/test_detection_grouping.py) | **$1.19\text{ms}$** ($836\text{ ops/s}$) |
| **End-to-End Gameplay Detection** | [`detector.py`](./packages/detection/src/blazzid_detection/detector.py) | [`test_gameplay_detector.py`](./tests/integration/test_gameplay_detector.py) | **$127.35\text{ms}$** (30s match, ~92x realtime) |
| **Candidate Utility Ranking** | [`ranking.py`](./packages/assembly/src/blazzid_assembly/ranking.py) | [`test_assembly_ranking.py`](./tests/unit/test_assembly_ranking.py) | **$562.29\text{ }\mu\text{s}$** ($1,778\text{ ops/s}$) |
| **Constrained Highlight Selection** | [`selection.py`](./packages/assembly/src/blazzid_assembly/selection.py) | [`test_assembly_selection.py`](./tests/unit/test_assembly_selection.py) | **$1.93\text{ms}$** ($518\text{ ops/s}$) |
| **Clip Boundary Planning** | [`planning.py`](./packages/assembly/src/blazzid_assembly/planning.py) | [`test_assembly_planning.py`](./tests/unit/test_assembly_planning.py) | **$139.74\text{ }\mu\text{s}$** ($7,156\text{ ops/s}$) |
| **Highlight Reel Montage Assembly** | [`pipeline.py`](./packages/assembly/src/blazzid_assembly/pipeline.py) | [`test_highlight_assembly_pipeline.py`](./tests/integration/test_highlight_assembly_pipeline.py) | **$\approx 1.8\text{s}$** (Real-time MP4 render & verify) |

---

## 6. Architecture & Engineering Documentation Index

- [**docs/highlight-assembly.md**](./docs/highlight-assembly.md): Stage 4 highlight ranking, duration-budgeted selection & montage assembly.
- [**docs/gameplay-event-detection.md**](./docs/gameplay-event-detection.md): Stage 3 gameplay event detection and candidate generation.
- [**docs/media-pipeline.md**](./docs/media-pipeline.md): Stage 2 media ingestion, preprocessing, and fast video analysis.
- [**docs/development-setup.md**](./docs/development-setup.md): Complete local setup and quality gate guide.
- [**docs/algorithm-implementation.md**](./docs/algorithm-implementation.md): Algorithmic proofs, invariants, and benchmark record.
- [**docs/requirements.md**](./docs/requirements.md): System goals, NFRs, and domain boundaries.
- [**docs/system-architecture.md**](./docs/system-architecture.md): C4 models, sequence workflows, and distributed patterns.
- [**docs/service-boundaries.md**](./docs/service-boundaries.md): 17 logical domains mapped to deployable units.
- [**docs/data-architecture.md**](./docs/data-architecture.md): PostgreSQL DDL, ER diagrams, and S3 object storage policies.
- [**docs/api-and-event-contracts.md**](./docs/api-and-event-contracts.md): Versioned REST, SSE, and Redis Streams schemas.
- [**docs/algorithm-design.md**](./docs/algorithm-design.md): Mathematical algorithm specifications.
- [**docs/ai-and-media-pipeline.md**](./docs/ai-and-media-pipeline.md): Adaptive sampling, Brawl Stars heuristics, and hardware matrix.
- [**docs/job-lifecycle.md**](./docs/job-lifecycle.md): FSM, heartbeats, crash recovery, and cancellation.
- [**docs/kubernetes-deployment-design.md**](./docs/kubernetes-deployment-design.md): KEDA queue-depth scaling and cluster architecture.
- [**docs/security-threat-model.md**](./docs/security-threat-model.md): STRIDE threat analysis and defensive execution wrappers.
- [**docs/testing-and-evaluation.md**](./docs/testing-and-evaluation.md): Testing pyramid, ground-truth metrics (IoU, precision, recall).
- [**docs/performance-and-capacity.md**](./docs/performance-and-capacity.md): Mathematical capacity planning and queuing theory.
- [**docs/roadmap.md**](./docs/roadmap.md): Stages 1 through 9 engineering sequence.
- [**docs/adr/**](./docs/adr/): Architecture Decision Records (ADR 0001 through 0004).
