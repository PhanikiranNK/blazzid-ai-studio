# BLAZZID AI Studio — System Architecture

## 1. Architectural Strategy & Evaluation

Selecting the right system architecture requires balancing operational simplicity, developmental velocity, resource isolation, and horizontal scalability. Media intelligence platforms have an extreme disparity between lightweight CRUD operations and compute-intensive, memory-heavy video decoding and neural inference.

### 1.1 Evaluation of Architectural Topologies

| Evaluation Criteria | Alternative A: Single Modular Monolith | Alternative B (Recommended): Modular Monolith with Separately Deployed Workers | Alternative C: Fully Distributed Microservices (15+ Services) |
| :--- | :--- | :--- | :--- |
| **Topology** | Single binary/container hosting API, UI server, and video/ML processing. | Unified modular codebase deployed as two primary runtime artifacts: (1) API/Gateway Service, (2) Media/ML Worker Pool. | 15+ independent services each with dedicated git repos, CI/CD, and databases. |
| **Operational Complexity** | Very Low: Single deployment, single log stream, minimal network configuration. | Low to Moderate: Docker Compose for local dev; identical images with different entrypoints in Kubernetes. | High: Complex service mesh, distributed tracing overhead, network partition handling, inter-service contracts. |
| **Resource Isolation** | **Unacceptable:** A single FFmpeg 4K transcode or OOM crash from a vision model kills the entire API server and user sessions. | **High:** Web API pods run on memory-optimized nodes; Worker pods run on compute/GPU nodes with isolated cgroups. | **High:** Each domain isolated into its own deployment. |
| **Development Velocity** | High initially, deteriorates as team scales. | **Very High:** Shared domain models, types, and DTOs; zero inter-service serialization boilerplate; rapid refactoring. | Low initially: Distributed consensus, schema synchronization, contract management overhead. |
| **Horizontal Scalability** | Poor: Scaling the API requires scaling the heavy media runtime dependencies. | **High:** Scale web pods based on HTTP RPS; scale worker pods independently based on queue depth. | **High:** Independent scaling per microservice. |
| **Recommendation** | Prototyping only. | **Target Pragmatic Implementation Path** | Long-term target if organizational scale warrants. |

### 1.2 Decision: Modular Monolith with Separately Deployed Workers
BLAZZID AI Studio adopts **Alternative B**. 
1. The codebase is organized as a strict modular monorepo with well-defined bounded contexts (domain modules).
2. The runtime environment is divided into:
   - **Studio API Service:** Lightweight, highly responsive HTTP/WebSocket server handling user authentication, project management, timeline queries, and job orchestration.
   - **Media & AI Processing Workers:** Stateless, asynchronous background workers consuming tasks from Redis/RabbitMQ queues. Workers execute video probing, audio analysis, visual feature extraction, OCR, evidence fusion, and FFmpeg rendering.
   - **Shared Datastores:** Managed PostgreSQL for transactional metadata and state; S3-compatible Object Storage (MinIO locally, AWS S3/GCS in cloud) for media binaries and intermediate artifacts.

---

## 2. C4 Architecture Models

### 2.1 C4 Level 1: System Context Diagram

```mermaid
C4Context
    title System Context Diagram - BLAZZID AI Studio

    Person(creator, "Content Creator / Editor", "Uploads long gaming footage, reviews highlight reels, adjusts timeline cuts, and exports videos.")
    System(blazzid, "BLAZZID AI Studio", "Ingests raw recordings, extracts multimodal evidence, ranks highlights, and renders deterministic edits.")
    System_Ext(s3, "Object Storage", "S3 / MinIO storing raw video footage, proxy clips, audio waveforms, and rendered outputs.")
    System_Ext(social, "Publishing Platforms", "YouTube, TikTok, Instagram Reels (Future integrations for direct publish).")

    Rel(creator, blazzid, "Uploads videos, edits EDL, previews clips, triggers renders", "HTTPS / WebSocket")
    Rel(blazzid, s3, "Reads/writes video streams, audio files, and proxy frames", "S3 API / Presigned URLs")
    Rel(blazzid, social, "Exports and uploads highlight packages", "REST APIs")
```

### 2.2 C4 Level 2: Container Diagram

```mermaid
C4Container
    title Container Diagram - BLAZZID AI Studio Runtime Topologies

    Person(creator, "Content Creator")

    Container(spa, "Creator Studio Frontend", "React / Vite / Canvas", "Timeline editor, video scrubbing, confidence overlays, clip adjustments")
    Container(api, "Studio API Gateway", "Python / FastAPI", "Authentication, project CRUD, EDL generation, job dispatch, SSE progress")
    ContainerDb(postgres, "PostgreSQL Persistence", "PostgreSQL 16", "Stores projects, media metadata, detected events, ranked highlights, EDLs")
    ContainerDb(redis, "Queue & State Broker", "Redis 7", "Job queues, worker heartbeats, task progress pub/sub, caching")
    Container(worker_cpu, "Media Preprocess & Audio Worker", "Python, FFmpeg, Librosa", "Container validation, proxy generation, audio energy & spectral analysis")
    Container(worker_gpu, "Visual & Inference Worker", "Python, OpenCV, OCR, PyTorch", "Dense frame sampling, HUD OCR, vision embeddings, evidence fusion")
    Container(worker_render, "FFmpeg Render Worker", "Python, FFmpeg 8.x", "Deterministic EDL filter graph execution, video assembly, audio ducking")
    ContainerDb(storage, "Media Storage", "S3-Compatible (MinIO / AWS S3)", "Raw VODs, proxy files, waveforms, visual thumbnails, rendered MP4s")

    Rel(creator, spa, "Interacts with UI", "HTTPS")
    Rel(spa, api, "REST API & SSE / WebSocket", "JSON / HTTPS")
    Rel(spa, storage, "Direct resumable chunk upload & proxy streaming", "HTTPS Presigned URLs")

    Rel(api, postgres, "Queries and updates project & event state", "SQL (asyncpg)")
    Rel(api, redis, "Enqueues jobs, listens to status updates", "Redis Streams / BullMQ")

    Rel(redis, worker_cpu, "Consumes preprocessing & audio tasks", "Redis Consumer Groups")
    Rel(redis, worker_gpu, "Consumes visual & fusion tasks", "Redis Consumer Groups")
    Rel(redis, worker_render, "Consumes rendering tasks", "Redis Consumer Groups")

    Rel(worker_cpu, storage, "Downloads raw VOD, uploads proxy & audio files", "S3 API")
    Rel(worker_gpu, storage, "Reads proxy frames, writes feature vectors", "S3 API")
    Rel(worker_render, storage, "Reads source clips, writes final export MP4", "S3 API")

    Rel(worker_cpu, postgres, "Writes media metadata & audio events", "SQL")
    Rel(worker_gpu, postgres, "Writes detected gameplay events & candidate scores", "SQL")
    Rel(worker_render, postgres, "Updates export status & metrics", "SQL")
```

### 2.3 C4 Level 3: Component Diagram (Media Intelligence Pipeline)

```mermaid
C4Component
    title Component Diagram - Processing & Intelligence Pipeline

    Component(ingest_mgr, "Ingest Coordinator", "Validates media headers with ffprobe, orchestrates proxy generation")
    Component(audio_pipe, "Audio Analyzer", "Sliding-window RMS, spectral centroid, stinger sound matching")
    Component(vis_pipe, "Visual Analyzer", "Keyframe extractor, scene change detection, HUD detector")
    Component(ocr_pipe, "Game OCR Engine", "Bbox cropping, text normalization, kill feed & gem parsing")
    Component(fusion_eng, "Evidence Fusion Engine", "Multimodal temporal correlation, confidence calibration, Bayesian aggregation")
    Component(ranking_opt, "Temporal Optimizer & Ranker", "Weighted interval scheduling (DP), context window expander, deduplicator")
    Component(edl_gen, "EDL Compiler", "Translates ranked highlights into deterministic FFmpeg filter graphs")

    Rel(ingest_mgr, audio_pipe, "Dispatches extracted audio track")
    Rel(ingest_mgr, vis_pipe, "Dispatches proxy video stream")
    Rel(vis_pipe, ocr_pipe, "Routes HUD candidate frames")
    Rel(audio_pipe, fusion_eng, "Emits AudioEvent observations")
    Rel(vis_pipe, fusion_eng, "Emits VisualEvent observations")
    Rel(ocr_pipe, fusion_eng, "Emits OCREvent observations")
    Rel(fusion_eng, ranking_opt, "Feeds raw fused gameplay events")
    Rel(ranking_opt, edl_gen, "Feeds optimal non-overlapping highlight intervals")
```

---

## 3. End-to-End Sequence Workflows

### 3.1 Media Upload & Ingestion Flow

```mermaid
sequenceDiagram
    autonumber
    actor Creator as Content Creator
    participant UI as Studio Frontend
    participant API as Studio API
    participant S3 as Object Storage
    participant Queue as Redis Queue
    participant Worker as Preprocess Worker

    Creator->>UI: Selects 2-hour Brawl Stars MP4
    UI->>API: POST /api/v1/projects/{id}/assets (filesize, filename, hash)
    API->>API: Validate file extension & user quota
    API->>S3: Generate multipart presigned upload URLs
    API-->>UI: Return asset_id + Presigned Part URLs
    UI->>S3: Direct upload binary parts (bypassing API)
    UI->>API: POST /api/v1/assets/{id}/complete-upload
    API->>Queue: Enqueue JOB_ASSET_INGEST (asset_id)
    API-->>UI: Asset status: PROCESSING
    Queue->>Worker: Dequeue JOB_ASSET_INGEST
    Worker->>S3: Stream first 10MB (probe headers via ffprobe)
    Worker->>Worker: Validate container, codec (H.264), duration, CFR
    Worker->>Worker: Transcode 720p 30fps Proxy + 16kHz Mono WAV (FFmpeg)
    Worker->>S3: Upload proxy.mp4 and audio.wav
    Worker->>API: Update asset metadata (width, height, fps, duration, proxy_url)
    Worker->>Queue: Enqueue JOB_ANALYSIS_DISPATCH (asset_id)
```

### 3.2 Multimodal Analysis & Evidence Fusion Flow

```mermaid
sequenceDiagram
    autonumber
    participant Queue as Redis Queue
    participant AudioW as Audio Worker
    participant VisW as Visual/OCR Worker
    participant FusionW as Fusion Worker
    participant DB as PostgreSQL
    participant API as Studio API
    participant UI as Studio Frontend

    Queue->>AudioW: Dequeue JOB_AUDIO_ANALYSIS
    Queue->>VisW: Dequeue JOB_VISUAL_ANALYSIS

    par Concurrent Analysis
        AudioW->>AudioW: Sliding window FFT, RMS energy spike detection
        AudioW->>DB: Bulk insert AudioObservations (timestamps, energy, zcr)
    and
        VisW->>VisW: Sparse sampling (1 fps) -> Detect HUD elimination banner
        VisW->>VisW: Dense sampling (15 fps) on candidate windows
        VisW->>VisW: Bbox OCR on Kill Feed & Score Tracker
        VisW->>DB: Bulk insert VisualObservations & OCRObservations
    end

    AudioW->>Queue: Emit AUDIO_ANALYSIS_COMPLETED
    VisW->>Queue: Emit VISUAL_ANALYSIS_COMPLETED
    Queue->>FusionW: Trigger JOB_EVIDENCE_FUSION
    FusionW->>DB: Fetch time-indexed observations
    FusionW->>FusionW: Sweep-line interval correlation & confidence calibration
    FusionW->>FusionW: Dynamic Programming Weighted Interval Scheduling
    FusionW->>DB: Persist HighlightCandidates & Initial EDL
    FusionW->>API: Notify job completion
    API->>UI: SSE event: ANALYSIS_COMPLETED (candidate_count: 8)
```

### 3.3 Creator Review & Interactive Editing Flow

```mermaid
sequenceDiagram
    autonumber
    actor Creator as Content Creator
    participant UI as Studio Frontend
    participant API as Studio API
    participant DB as PostgreSQL
    participant S3 as Object Storage

    Creator->>UI: Opens Project Timeline
    UI->>API: GET /api/v1/projects/{id}/timeline
    API->>DB: Query assets, candidates, and current EDL
    API-->>UI: Return Timeline JSON (candidates, confidence, proxy URLs)
    UI->>S3: Fetch audio waveform data & video proxy stream
    Creator->>UI: Scrubs timeline, inspects Candidate #3 (Triple Kill, conf: 0.92)
    Creator->>UI: Trims clip in-point (+2.0s) and out-point (-1.0s)
    Creator->>UI: Rejects Candidate #5 (False positive gem collection)
    UI->>API: PUT /api/v1/projects/{id}/edl (updated clips array)
    API->>DB: Update EDL record (optimistic locking via version token)
    API-->>UI: EDL saved (version: 2)
```

### 3.4 Deterministic Rendering & Export Validation Flow

```mermaid
sequenceDiagram
    autonumber
    actor Creator as Content Creator
    participant UI as Studio Frontend
    participant API as Studio API
    participant Queue as Redis Queue
    participant RenderW as Render Worker
    participant S3 as Object Storage
    participant DB as PostgreSQL

    Creator->>UI: Clicks "Export Reel" (Preset: YouTube Shorts 1080x1920)
    UI->>API: POST /api/v1/projects/{id}/exports (preset, edl_version)
    API->>DB: Insert ExportJob (status: PENDING)
    API->>Queue: Enqueue JOB_RENDER_EXPORT (export_id)
    Queue->>RenderW: Dequeue JOB_RENDER_EXPORT
    RenderW->>DB: Fetch source asset URL & validated EDL
    RenderW->>RenderW: Compile FFmpeg complex filter graph:
    Note over RenderW: concat demuxer -> trim -> scale/crop -> crossfade -> loudnorm
    RenderW->>S3: Download source segments (streamed or chunked)
    RenderW->>RenderW: Execute FFmpeg render process (stream progress via stdout)
    RenderW->>API: Report progress percentage (25%, 50%, 75%)
    RenderW->>RenderW: Post-render validation: ffprobe verify sync & duration
    RenderW->>S3: Upload final export_reel.mp4
    RenderW->>DB: Update ExportJob (status: COMPLETED, artifact_url, duration, size)
    RenderW->>API: Publish EXPORT_COMPLETED
    API->>UI: SSE notify Creator: Download Ready
```

---

## 4. Distributed Systems Principles

### 4.1 Synchronous vs. Asynchronous Communication
- **Synchronous (HTTP/REST):** Restricted to fast control-plane operations ($< 200\text{ms}$), including project CRUD, timeline queries, EDL modifications, and presigned URL generation.
- **Asynchronous (Queues & Events):** All data-plane operations (probing, transcoding, OCR, inference, rendering) execute asynchronously via message queues. Long-running tasks publish progress updates to Redis channels, which the API bridges to the web frontend using Server-Sent Events (SSE).

### 4.2 At-Least-Once Delivery & Idempotency
- Message brokers guarantee **at-least-once** delivery. Network partitions or worker timeouts may cause a job to be delivered multiple times.
- All worker consumers are strictly **idempotent**:
  - Each job contains a deterministic `idempotency_key` (e.g., `job:analysis:{asset_id}:{pipeline_version}`).
  - Before execution, workers check if the expected output artifact or database record already exists.
  - Database writes use `ON CONFLICT (idempotency_key) DO UPDATE` or atomic status transitions (`UPDATE jobs SET status = 'RUNNING' WHERE id = :id AND status = 'QUEUED'`).

### 4.3 Retries, Exponential Backoff & Dead-Letter Queues (DLQ)
- **Retry Policy:** Transient errors (network blips to S3, brief database pool exhaustion) trigger retries with exponential backoff and full jitter:
  $$T_{\text{wait}} = \min(T_{\text{max}}, T_{\text{base}} \times 2^{\text{attempt}}) \pm \text{jitter}$$
- **Non-Retryable Errors:** Deterministic failures (unsupported video codec, corrupted media header, invalid user input) immediately fail without retry.
- **Dead-Letter Queue:** Jobs failing $N=3$ consecutive retries are moved to a dead-letter queue (`queue:dead_letter`), preserving the original job payload, exception stack trace, and worker execution metadata for operational triage.

### 4.4 Backpressure & Bounded Concurrency
- To prevent Out-Of-Memory (OOM) crashes and system instability, worker concurrency is tightly bounded:
  - FFmpeg rendering workers enforce a concurrency cap per node ($N_{\text{render}} = \lfloor \frac{\text{CPU Cores}}{2} \rfloor$).
  - Neural inference workers limit concurrency to $N_{\text{inference}} = 1$ per GPU or $N_{\text{inference}} = 2$ per CPU node.
- Workers use Redis Consumer Groups with explicit prefetch limits (`COUNT 1`) so that unacknowledged tasks remain in the queue rather than flooding worker memory.

### 4.5 Timeouts & Graceful Shutdown
- **Job-Level Timeouts:** Each task has an explicit budget (e.g., Media Probe: 60s; Audio Analysis: 300s; Video Render: 900s). Exceeding the deadline triggers a SIGTERM, followed by SIGKILL after a 10s grace window.
- **Pod Shutdown:** When Kubernetes sends `SIGTERM`, workers cease accepting new tasks from Redis, wait up to 30s for the current processing chunk to flush state, checkpoint their progress, and exit cleanly.
