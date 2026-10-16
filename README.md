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
- [x] **Stage 1: Repository Foundation, Contracts & Core Algorithms** (Complete)
- [ ] **Stage 2: Media Ingestion, Preprocessing & Fast Video Analysis** (Pending explicit approval)

---

## 3. Quickstart & Developer Workflow

### Environment Setup
```bash
# 1. Create and activate a Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install editable packages and development dependencies
pip install --upgrade pip
pip install -e packages/core -e packages/algorithms
pip install -r pyproject.toml --extra dev || pip install "pytest>=8.0.0" "hypothesis>=6.98.0" "pytest-benchmark>=4.0.0" "ruff>=0.3.0" "mypy>=1.9.0"
```

### Quality Gate Commands (From Repository Root)
```bash
# Formatting & Linting
.venv/bin/ruff format --check .
.venv/bin/ruff check .

# Strict Type Checking (mypy --strict)
.venv/bin/mypy packages/core/src packages/algorithms/src tests benchmarks

# Unit & Property-Based Test Suites
.venv/bin/pytest -v tests

# Repeatable Performance Benchmarks
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
│   └── algorithms/                        # blazzid-algorithms: pure mathematical primitives
│       ├── pyproject.toml
│       └── src/blazzid_algorithms/
│           ├── top_k.py                   # Bounded min-heap streaming selector (O(M log K))
│           ├── interval_selection.py      # 2D DP Weighted Interval Scheduling & Exhaustive Oracle
│           ├── rolling_statistics.py      # Numerically stabilized rolling stats & z-scores
│           └── perceptual_hash.py         # 64-bit Hamming distance & visual similarity
├── tests/
│   ├── unit/                              # Isolated component & boundary tests (53 tests)
│   ├── property/                          # Hypothesis mathematical invariant tests (11 tests)
│   └── fixtures/                          # Synthetic FFmpeg video & audio test fixtures
├── benchmarks/                            # pytest-benchmark performance test suite
└── docs/                                  # Complete Stage 0 & Stage 1 architecture records
```

---

## 5. Stage 1 Deliverables & Acceptance Verification

| Stage 1 Requirement | Implementation File | Verification Test Suite | Benchmark Performance |
| :--- | :--- | :--- | :--- |
| **Top-$K$ Selection** | [`top_k.py`](./packages/algorithms/src/blazzid_algorithms/top_k.py) | [`test_top_k.py`](./tests/unit/test_top_k.py)<br>[`test_top_k_properties.py`](./tests/property/test_top_k_properties.py) | **$1,627,000\text{ items/s}$** ($6.14\text{ms}$ per 10k items) |
| **Weighted Interval Scheduling** | [`interval_selection.py`](./packages/algorithms/src/blazzid_algorithms/interval_selection.py) | [`test_interval_selection.py`](./tests/unit/test_interval_selection.py)<br>[`test_interval_selection_properties.py`](./tests/property/test_interval_selection_properties.py) | **$10.78\text{ms}$** ($100$ clips, $360$ capacity bins) |
| **Rolling Statistics** | [`rolling_statistics.py`](./packages/algorithms/src/blazzid_algorithms/rolling_statistics.py) | [`test_rolling_statistics.py`](./tests/unit/test_rolling_statistics.py)<br>[`test_rolling_statistics_properties.py`](./tests/property/test_rolling_statistics_properties.py) | **$893,000\text{ samples/s}$** ($55.93\text{ms}$ per 50k samples) |
| **64-bit Hash Distance** | [`perceptual_hash.py`](./packages/algorithms/src/blazzid_algorithms/perceptual_hash.py) | [`test_perceptual_hash.py`](./tests/unit/test_perceptual_hash.py)<br>[`test_perceptual_hash_properties.py`](./tests/property/test_perceptual_hash_properties.py) | **$1,515,000\text{ comparisons/s}$** ($6.59\text{ms}$ per 10k pairs) |
| **Domain Contracts** | [`contracts/`](./packages/core/src/blazzid_core/contracts/) | [`test_contracts.py`](./tests/unit/test_contracts.py) | Fully validated Pydantic v2 models |
| **Synthetic Media** | [`synthetic_media.py`](./tests/fixtures/synthetic_media.py) | [`test_synthetic_media.py`](./tests/fixtures/test_synthetic_media.py) | Deterministic FFmpeg fixtures |

---

## 6. Architecture & Engineering Documentation Index

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
