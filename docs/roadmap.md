# BLAZZID AI Studio — Engineering Stage Roadmap

## 1. Roadmap Strategy & Dependency Order

The engineering roadmap follows a strict **Inside-Out, Dependency-Driven Sequence**. We establish mathematical and algorithmic foundations first, followed by media processing, domain business logic, rendering, UI presentation, and finally production Kubernetes deployment.

```
Stage 0: Architecture & Design (CURRENT)
   │
   ▼
Stage 1: Foundation, Tooling, Core Algorithm Prototypes
   │
   ▼
Stage 2: Media Ingestion, Preprocessing & Fast Analysis
   │
   ▼
Stage 3: Gameplay Event Detection & Multimodal Fusion
   │
   ▼
Stage 4: Highlight Ranking, Temporal Optimization & Deduplication
   │
   ▼
Stage 5: Backend APIs, Persistence & Background Job Execution
   │
   ▼
Stage 6: Deterministic Rendering Engine & Quality Assurance
   │
   ▼
Stage 7: Creator Studio Frontend & Interactive Review
   │
   ▼
Stage 8: Kubernetes Deployment, Autoscaling & Telemetry
   │
   ▼
Stage 9: Performance Optimization, Hardening & Production Validation
```

---

## 2. Detailed Stage Specifications

---

### Stage 1: Repository Foundation, Development Tooling, Contracts & Core Algorithm Prototype
- **Prerequisites:** Stage 0 architecture approval.
- **Core Deliverables:**
  1. Monorepo structure setup (`/packages/core`, `/packages/algorithms`, `/services/api`, `/services/worker`, `/apps/studio`).
  2. Python 3.9+ environment with `poetry` or `uv`, `ruff` linting, `mypy` strict typing, and `pytest`.
  3. Pydantic v2 data contracts and schema validators for all DTOs and events.
  4. Core algorithmic prototypes in `/packages/algorithms`:
     - Top-$K$ Min-Heap candidate selector.
     - Weighted Interval Scheduling Dynamic Programming solver.
     - Rolling prefix-sum z-score calculator.
     - Perceptual hash bitwise distance calculator.
- **Tests:**
  - 100% unit test coverage on core algorithms.
  - Property-based tests via `Hypothesis` proving zero interval overlap and duration budget constraints.
- **Acceptance Criteria:**
  - All algorithm benchmarks pass: DP table solve $< 15\text{ms}$ for $N=500$ candidates; Top-$K$ selector throughput $> 1,000,000\text{ items/s}$.
  - Strict type checking (`mypy --strict`) passes with zero errors.
- **Risks:** Scope creep into media decoding before pure algorithms are verified.
- **Exit Condition:** Core algorithmic engine verified against mathematical invariants and benchmarked on host hardware.

---

### Stage 2: Media Ingestion, Preprocessing & Efficient Video Analysis
- **Prerequisites:** Stage 1 completion.
- **Core Deliverables:**
  1. Defensive `ffprobe` wrapper extracting duration, streams, codec, pixel format, and CFR/VFR status.
  2. Dual-stream extractor producing 720p 30fps H.264 proxy and 16kHz mono WAV.
  3. Sparse visual frame sampler (1 fps) using OpenCV.
  4. Waveform peak JSON generator for frontend timeline display.
  5. Synthetic media fixture generator for CI test suite.
- **Tests:**
  - Header inspection tests with corrupted, truncated, and valid media fixtures.
  - Synthetic video proxy transcode verification.
  - Audio waveform peak extraction verification.
- **Acceptance Criteria:**
  - 1-hour 1080p60 synthetic recording transcodes to proxy + WAV in $\le 6$ minutes on host CPU ($> 10\times$ speed factor).
  - Corrupted media headers trigger deterministic `MediaValidationError`.
- **Risks:** Codec and container edge cases on mobile screen captures (VFR audio drift).
- **Exit Condition:** Validated media ingestion pipeline capable of ingesting raw videos and producing standard proxies.

---

### Stage 3: Gameplay Event Detection & Multimodal Evidence Fusion
- **Prerequisites:** Stage 2 completion.
- **Core Deliverables:**
  1. Audio feature extractor (rolling RMS energy, spectral centroid, stinger frequency matching).
  2. Brawl Stars visual detector (HUD crop, template matching for elimination banner and Showdown skull).
  3. Game OCR parser using PaddleOCR for Kill Feed text and gem counts.
  4. Sweep-line multimodal evidence aggregator.
  5. Bayesian confidence calibration module.
- **Tests:**
  - Unit tests for OCR text normalization and regex patterns.
  - Audio stinger detection on synthetic audio signals.
  - Multimodal sweep-line correlation tests.
- **Acceptance Criteria:**
  - Audio and visual detectors emit calibrated observations with full provenance payloads.
  - Evidence fusion correctly aggregates audio spike + visual HUD elimination into a single `TEAM_WIPE` event.
- **Risks:** OCR false positive readings on low-contrast mobile video.
- **Exit Condition:** Multimodal detection pipeline producing verified `GameplayEvent` records from sample gameplay clips.

---

### Stage 4: Highlight Ranking, Temporal Optimization & Deduplication
- **Prerequisites:** Stage 3 completion.
- **Core Deliverables:**
  1. Context-aware boundary expansion engine (Setup $\to$ Climax $\to$ Payoff).
  2. Perceptual hash visual deduplicator to eliminate identical menu/respawn clips.
  3. Constrained Weighted Interval Scheduling DP integration.
  4. Deterministic Edit Decision List (EDL) compiler (JSON output).
- **Tests:**
  - Context expansion tests verifying boundary expansion and scene-cut snapping.
  - Visual deduplication tests with near-duplicate frames.
  - End-to-end highlight selection tests over 50+ candidate events.
- **Acceptance Criteria:**
  - Selected highlights fit strictly within target duration budget without overlap.
  - EDL compiler generates valid, human-readable JSON specifying source cuts and transitions.
- **Risks:** Over-expansion of candidate boundaries creating clips that exceed individual duration limits.
- **Exit Condition:** End-to-end algorithmic pipeline that takes raw events and outputs an optimal, deduplicated EDL.

---

### Stage 5: Backend APIs, Persistence & Background Job Execution
- **Prerequisites:** Stage 4 completion.
- **Core Deliverables:**
  1. FastAPI application providing REST endpoints for projects, assets, analysis, and EDLs.
  2. PostgreSQL 16 schema migrations via Alembic.
  3. Redis Streams job queue integration with Consumer Groups.
  4. Worker process loop with distributed heartbeats, orphan reconciliation, and cancellation hooks.
  5. S3/MinIO client supporting presigned multipart uploads.
  6. Server-Sent Events (SSE) progress broadcasting.
- **Tests:**
  - Integration tests using Testcontainers (PostgreSQL, Redis, MinIO).
  - API contract validation via Schemathesis.
  - Worker crash and recovery integration test.
- **Acceptance Criteria:**
  - Complete project upload, analysis dispatch, and status polling functional over HTTP/SSE.
  - Database migrations execute cleanly up and down.
  - Worker crashes automatically recover without stuck jobs.
- **Risks:** Redis connection pool leaks or asynchronous event loop blocking.
- **Exit Condition:** Fully functional headless backend capable of end-to-end background media processing.

---

### Stage 6: Deterministic Rendering Engine & Quality Assurance
- **Prerequisites:** Stage 5 completion.
- **Core Deliverables:**
  1. FFmpeg complex filter graph compiler translating EDL into deterministic rendering commands.
  2. Video transformation pipeline: segment cutting, crossfade transitions, 16:9 to 9:16 portrait crop.
  3. Audio mastering filter: EBU R128 loudness normalization (`loudnorm`) and ducking.
  4. Post-render validation module: ffprobe audio/video sync drift check, duration validation.
- **Tests:**
  - Multi-clip rendering tests using synthetic fixtures.
  - Audio loudness compliance verification ($\pm 1.0\text{ LUFS}$).
  - Aspect ratio transformation tests (1080x1920 portrait output).
- **Acceptance Criteria:**
  - Highlight reel renders at $\ge 2.0\times$ real-time speed.
  - Rendered MP4 audio/video sync drift $\le 20\text{ms}$.
- **Risks:** FFmpeg filter graph syntax errors on edge-case clip transitions.
- **Exit Condition:** Production-ready rendering worker producing validated MP4 highlight reels from EDLs.

---

### Stage 7: Creator Studio Frontend & Review Workflow
- **Prerequisites:** Stage 6 completion.
- **Core Deliverables:**
  1. Modern React / Vite / TypeScript single-page application.
  2. Interactive multi-track timeline component (video scrub, audio waveform, candidate markers).
  3. Clip boundary adjustment handles (in-point, out-point dragging).
  4. Candidate review panel (accept, reject, reorder, confidence breakdown).
  5. Real-time video preview player with synchronized EDL cuts.
  6. Export preset modal (YouTube Shorts, TikTok, Standard 16:9).
- **Tests:**
  - Component unit tests with Vitest / React Testing Library.
  - E2E browser tests with Playwright (upload $\to$ timeline scrub $\to$ edit EDL $\to$ trigger export).
- **Acceptance Criteria:**
  - Fluid 60fps timeline scrubbing without audio/video stuttering.
  - Edits to EDL save optimistically and synchronize with backend.
- **Risks:** Browser video player frame-seeking inaccuracies across varying codecs.
- **Exit Condition:** Fully interactive web studio enabling creators to review and customize AI-generated highlights.

---

### Stage 8: Kubernetes Deployment, Autoscaling & Telemetry
- **Prerequisites:** Stage 7 completion.
- **Core Deliverables:**
  1. Production Dockerfiles with multi-stage builds and non-root security context.
  2. Kubernetes manifests / Helm chart for API, CPU Workers, GPU Workers, and Render Workers.
  3. KEDA ScaledObjects for Redis Stream queue-depth autoscaling.
  4. NetworkPolicies, PodDisruptionBudgets, and Ingress routing.
  5. OpenTelemetry tracing, Prometheus `/metrics` scraping, and Grafana dashboard.
- **Tests:**
  - Deployment validation on local Kind / Minikube cluster.
  - Queue-depth autoscaling stress tests (scaling 1 to 8 worker pods).
  - NetworkPolicy isolation verification.
- **Acceptance Criteria:**
  - KEDA successfully scales worker pods up when queue depth increases and scales down cleanly.
  - Distributed trace propagates from API to asynchronous workers via W3C `traceparent`.
- **Risks:** Kubernetes node auto-provisioning delay for GPU instances.
- **Exit Condition:** Kubernetes-deployable platform with verified autoscaling and observability.

---

### Stage 9: Performance Optimization, Hardening & Production Validation
- **Prerequisites:** Stage 8 completion.
- **Core Deliverables:**
  1. Full ground-truth benchmark evaluation against 20 labeled Brawl Stars recordings.
  2. Quantized model inference (ONNX / TensorRT / Apple Silicon CoreML).
  3. End-to-end chaos testing (simulating S3 downtime, DB disconnects, worker kills).
  4. Security audit (container scanning with Trivy, penetration testing for BOLA and SSRF).
  5. Production operational runbooks (disaster recovery, backup restoration).
- **Tests:**
  - Automated benchmark suite verifying Precision $\ge 85\%$, Recall $\ge 80\%$, tIoU $\ge 0.75$.
  - End-to-end stress test under 50 concurrent video uploads.
- **Acceptance Criteria:**
  - All Stage 0 NFR targets verified with production measurements.
  - Zero critical/high vulnerabilities in Trivy container scan.
- **Risks:** Overfitting heuristic rules to specific Brawler characters or game updates.
- **Exit Condition:** Production-ready BLAZZID AI Studio validated against real-world creator workloads.
