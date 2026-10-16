# BLAZZID AI Studio — Service Boundaries & Domain Decomposition

## 1. Architectural Boundary Strategy

BLAZZID AI Studio decomposes the business domain into 17 distinct **Logical Domains**. However, creating 17 separate Kubernetes microservices on day one would introduce catastrophic operational overhead without functional justification.

Instead, we map these 17 logical domains into **4 Deployable Compute Units (Services)** and **3 Managed Infrastructure Components**:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        LOGICAL DOMAIN MAPPING                          │
├────────────────────────────────┬───────────────────────────────────────┤
│ Deployable Runtime Unit        │ Included Logical Domains              │
├────────────────────────────────┼───────────────────────────────────────┤
│ 1. Studio Web & API Service    │ • Ingress / API Gateway (1)           │
│    (Lightweight Async HTTP)    │ • Frontend Studio Web Server (2)      │
│                                │ • Identity & Access Management (3)    │
│                                │ • Project & Media Management (4)      │
│                                │ • Job Orchestration Controller (12)   │
│                                │ • Export Management Facade (13)       │
├────────────────────────────────┼───────────────────────────────────────┤
│ 2. Preprocessing & Audio       │ • Media Ingest & Preprocessing (5)    │
│    Worker Pool (CPU-bound)     │ • Audio Analysis & Stinger Match (6)  │
├────────────────────────────────┼───────────────────────────────────────┤
│ 3. Visual & AI Inference       │ • Visual Analysis & Frame Sampler (7) │
│    Worker Pool (CPU/GPU)       │ • Game OCR Engine (7)                 │
│                                │ • AI / VLM Inference (8)              │
│                                │ • Evidence Fusion & Detection (9)     │
│                                │ • Highlight Ranking & Opt (10)        │
├────────────────────────────────┼───────────────────────────────────────┤
│ 4. FFmpeg Render Worker        │ • Video Editing & Filter Graph (11)   │
│    Pool (I/O & Multi-core CPU) │ • Transcode & Bitstream Check (11)    │
├────────────────────────────────┼───────────────────────────────────────┤
│ 5. Managed Infrastructure      │ • PostgreSQL Persistence (14)         │
│                                │ • Object Storage - S3/MinIO (15)      │
│                                │ • Redis Queue & State Broker (16)     │
│                                │ • Observability & Telemetry (17)      │
└────────────────────────────────┴───────────────────────────────────────┘
```

This decomposition provides strict failure isolation where it matters (preventing an FFmpeg OOM or GPU driver stall from affecting user API requests) while maintaining a unified, easily refactored codebase.

---

## 2. Comprehensive Domain Analysis (17 Logical Domains)

### Domain 1: API Gateway and Ingress
- **Primary Responsibility:** TLS termination, path routing, rate limiting, request tracing (W3C TraceContext `traceparent`), CORS handling, and proxying requests to internal services.
- **API / Event Contracts:** Exposes public HTTPS `/api/v1/*` and WebSocket/SSE `/api/v1/ws/*`.
- **Data Ownership:** None (stateless).
- **Resource Profile:** Low CPU, low memory (250m CPU, 256MB RAM per pod).
- **Dependencies:** Studio API Service.
- **Failure Modes:** TLS certificate expiration, upstream socket timeout, connection flood.
- **Scaling Metric:** HTTP requests per second (RPS) and active TCP connections.
- **Deployment Justification:** Handled at the Kubernetes Ingress / Gateway API layer (e.g., Ingress-NGINX or Envoy).

### Domain 2: Frontend Studio
- **Primary Responsibility:** User-facing single-page application (SPA). Timeline scrubbing, multi-track audio/video preview, confidence score visualization, drag-and-drop clip adjustment, and export triggers.
- **API / Event Contracts:** Consumes REST API and SSE events emitted by Studio API.
- **Data Ownership:** In-browser reactive state (Zustand/Redux).
- **Resource Profile:** Static asset hosting; client-side execution.
- **Dependencies:** Studio API endpoints, Object Storage CDN for video proxies and waveforms.
- **Failure Modes:** Network disconnection, video decoder incompatibility on client browser.
- **Scaling Metric:** Static file egress / CDN requests.
- **Deployment Justification:** Served as static assets via NGINX or bundled within the API container in development.

### Domain 3: Identity and Access Management (IAM)
- **Primary Responsibility:** User authentication, password hashing (Argon2id), session management, JWT issuance, API key validation, and project-level role-based access control (RBAC).
- **API / Event Contracts:** `/api/v1/auth/login`, `/api/v1/auth/refresh`, `/api/v1/auth/me`.
- **Data Ownership:** PostgreSQL tables: `users`, `sessions`, `api_keys`, `project_memberships`.
- **Resource Profile:** Low CPU (intermittent Argon2 spikes), low memory (500m CPU, 512MB RAM).
- **Dependencies:** PostgreSQL, Redis (session revocation blacklist).
- **Failure Modes:** Auth service unavailable blocks all logins; token verification fallback to public keys.
- **Scaling Metric:** Login RPS and active sessions.
- **Deployment Justification:** Integrated into Studio API Service in initial stages; easily extractable to dedicated service if enterprise SSO (OIDC/SAML) is introduced.

### Domain 4: Project and Media Management
- **Primary Responsibility:** CRUD operations for video editing projects, uploaded raw assets, metadata tagging, game mode identification, and soft deletion.
- **API / Event Contracts:** `/api/v1/projects/*`, `/api/v1/assets/*`.
- **Data Ownership:** PostgreSQL tables: `projects`, `media_assets`.
- **Resource Profile:** Standard REST API profile (250m CPU, 512MB RAM).
- **Dependencies:** PostgreSQL, Object Storage.
- **Failure Modes:** Database connection pool exhaustion, S3 metadata sync lag.
- **Scaling Metric:** Database query latency and HTTP request rate.
- **Deployment Justification:** Core business logic inside Studio API Service.

### Domain 5: Media Ingestion and Preprocessing
- **Primary Responsibility:** Container header inspection (`ffprobe`), stream integrity checks, variable frame rate (VFR) detection, 720p H.264 proxy generation, and 16kHz mono audio extraction.
- **API / Event Contracts:** Consumes `asset.uploaded` event; produces `asset.preprocessed` and `asset.corrupted` events.
- **Data Ownership:** Temporary local disk scratch files; creates proxy video and audio objects in Object Storage.
- **Resource Profile:** High CPU (video decoding & downscaling), high disk I/O (2000m CPU, 2GB RAM, 20GB local scratch per worker).
- **Dependencies:** Object Storage, FFmpeg / ffprobe binaries.
- **Failure Modes:** Corrupt container, unsupported codec, disk space exhaustion.
- **Scaling Metric:** Queue backlog size of `queue:preprocess`.
- **Deployment Justification:** **Must be deployed independently** to prevent high CPU/disk I/O from starving web requests.

### Domain 6: Audio Analysis
- **Primary Responsibility:** Extract audio waveforms, compute sliding-window Root-Mean-Square (RMS) energy, spectral centroid, spectral flux, and match acoustic game stingers (countdown sounds, overtime alarms).
- **API / Event Contracts:** Consumes `asset.preprocessed`; produces `AudioObservation` records.
- **Data Ownership:** Writes `audio_observations` to PostgreSQL; writes waveform JSON to Object Storage.
- **Resource Profile:** Moderate CPU, vector math (1000m CPU, 1GB RAM).
- **Dependencies:** Python `numpy`, `scipy`, `soundfile`.
- **Failure Modes:** Truncated audio stream, silent audio track (no microphones/game sound).
- **Scaling Metric:** Queue backlog size of `queue:audio_analysis`.
- **Deployment Justification:** Grouped with Preprocessing Worker pool to optimize local file caching of extracted WAVs.

### Domain 7: Visual Analysis and OCR
- **Primary Responsibility:** Scene cut detection, sparse/dense frame sampling, game HUD detection, bounding-box cropping, and text extraction for kill notifications, player nicknames, and match scores.
- **API / Event Contracts:** Consumes `asset.preprocessed`; produces `VisualObservation` and `OCRObservation` records.
- **Data Ownership:** Writes observations to PostgreSQL; writes thumbnail crops to Object Storage.
- **Resource Profile:** High CPU, high RAM, benefits significantly from GPU/Apple Silicon Metal (2000m CPU, 4GB RAM).
- **Dependencies:** OpenCV, lightweight OCR model (PaddleOCR / Tesseract / EasyOCR).
- **Failure Modes:** Obscured HUD, dynamic UI layout changes, OCR misreadings.
- **Scaling Metric:** Queue backlog size of `queue:visual_analysis`.
- **Deployment Justification:** **Isolated in Visual Worker Pool** to allow targeted GPU node scheduling in Kubernetes.

### Domain 8: AI Inference
- **Primary Responsibility:** Higher-level vision-language model (VLM) or multimodal embedding inference on candidate video clips to verify complex gameplay context (e.g., verifying a clutch play or miraculous dodge).
- **API / Event Contracts:** Consumes candidate intervals; produces semantic classification tags and verification scores.
- **Data Ownership:** None (stateless inference).
- **Resource Profile:** Very high memory, GPU mandatory for acceptable throughput (1 GPU or 4000m CPU, 8GB RAM).
- **Dependencies:** PyTorch, ONNX Runtime, HuggingFace Transformers.
- **Failure Modes:** CUDA OOM, inference timeout, model loading failure.
- **Scaling Metric:** Model request queue depth and GPU memory utilization.
- **Deployment Justification:** **Isolated deployment** with specialized GPU tolerations and resource limits in Kubernetes.

### Domain 9: Gameplay Event Detection and Evidence Fusion
- **Primary Responsibility:** Temporal correlation of multimodal observations (Audio + Visual + OCR), confidence calibration, Bayesian evidence combination, and generation of raw gameplay events.
- **API / Event Contracts:** Consumes observation streams; emits `GameplayEvent` records.
- **Data Ownership:** PostgreSQL table: `gameplay_events`.
- **Resource Profile:** Moderate CPU, high memory for in-memory interval correlation (1000m CPU, 2GB RAM).
- **Dependencies:** PostgreSQL.
- **Failure Modes:** Inconsistent timestamps across modalities, clock skew.
- **Scaling Metric:** Event count per recording.
- **Deployment Justification:** Executed within the Worker pipeline immediately following visual/audio extraction.

### Domain 10: Highlight Ranking and Temporal Optimization
- **Primary Responsibility:** Dynamic Programming-based Weighted Interval Scheduling, boundary refinement (lead-in setup, climax, payoff), clip deduplication, and game mode constraint enforcement.
- **API / Event Contracts:** Consumes `GameplayEvent` records; produces `HighlightCandidate` records and initial EDL.
- **Data Ownership:** PostgreSQL tables: `highlight_candidates`, `edit_decision_lists`.
- **Resource Profile:** Low to moderate CPU (1000m CPU, 1GB RAM); execution time $< 5$ seconds per 1-hour recording.
- **Dependencies:** PostgreSQL.
- **Failure Modes:** No events detected (empty reel fallback), over-constrained duration.
- **Scaling Metric:** Total candidate count.
- **Deployment Justification:** Algorithmic module executed inside the Worker pipeline or Studio API Service.

### Domain 11: Editing and Rendering
- **Primary Responsibility:** Compiling deterministic Edit Decision Lists (EDLs) into complex FFmpeg filter graphs, trimming segments, applying crossfades, video scaling/cropping (16:9 to 9:16), audio normalization (EBU R128), and final MP4 encoding.
- **API / Event Contracts:** Consumes `export.requested`; produces `export.completed` and `export.failed`.
- **Data Ownership:** Final rendered MP4 binaries written to Object Storage; status written to `export_jobs`.
- **Resource Profile:** Extremely high CPU (multi-core transcode) and high disk I/O (4000m CPU, 4GB RAM, 50GB scratch storage).
- **Dependencies:** FFmpeg 8.x with `libx264`, `libx265`, `aac`.
- **Failure Modes:** Codec mismatch, corrupt source segment, render process crash, disk exhaustion.
- **Scaling Metric:** Render queue backlog and average render execution duration.
- **Deployment Justification:** **Dedicated Render Worker Pool** to prevent rendering jobs from starving analysis and API services.

### Domain 12: Job Orchestration
- **Primary Responsibility:** Managing state transitions of multi-step processing DAGs (Ingest $\to$ Preprocess $\to$ Analysis $\to$ Fusion $\to$ Ranking $\to$ EDL $\to$ Render), tracking worker heartbeats, detecting orphaned tasks, and enforcing timeouts.
- **API / Event Contracts:** Exposes internal job state queries and task dispatching.
- **Data Ownership:** PostgreSQL table: `jobs`; Redis stream keys.
- **Resource Profile:** Low CPU, low memory (500m CPU, 512MB RAM).
- **Dependencies:** PostgreSQL, Redis.
- **Failure Modes:** Brain-split worker reconciliation, stale heartbeat detection.
- **Scaling Metric:** Active job count.
- **Deployment Justification:** Hosted inside Studio API Service using a robust internal state machine.

### Domain 13: Export Management
- **Primary Responsibility:** Managing export presets (resolution, bitrate, social media formats), generating download authorization tokens, and tracking export analytics.
- **API / Event Contracts:** `/api/v1/projects/{id}/exports`, `/api/v1/exports/{id}/download`.
- **Data Ownership:** PostgreSQL table: `export_jobs`.
- **Resource Profile:** Low CPU (250m CPU, 256MB RAM).
- **Dependencies:** PostgreSQL, Object Storage.
- **Failure Modes:** Expired presigned URLs.
- **Scaling Metric:** Export download requests.
- **Deployment Justification:** Integrated into Studio API Service.

### Domain 14: PostgreSQL Persistence
- **Primary Responsibility:** ACID transactional storage for all relational state: users, projects, media metadata, observations, events, candidates, EDLs, and job histories.
- **API / Event Contracts:** Standard PostgreSQL wire protocol (TCP port 5432).
- **Data Ownership:** All relational schemas and tables.
- **Resource Profile:** High memory (buffer pool), moderate CPU, fast SSD storage (I/O bound).
- **Dependencies:** Persistent block storage (EBS / Ceph / local NVMe).
- **Failure Modes:** Connection pool starvation, disk full, unindexed slow queries.
- **Scaling Metric:** Active connections, query latency, disk IOPS.
- **Deployment Justification:** Managed Cloud Service (AWS RDS / GCP Cloud SQL) or StatefulSet in Kubernetes with PgBouncer connection pooling.

### Domain 15: Object Storage
- **Primary Responsibility:** High-durability storage for large binary payloads: raw video recordings, proxy streams, audio WAVs, thumbnail images, and rendered highlight reels.
- **API / Event Contracts:** S3 REST API (GET, PUT, Multipart Upload, Presigned URLs).
- **Data Ownership:** Binary blobs organized by bucket and prefix.
- **Resource Profile:** High network bandwidth, virtually unlimited storage capacity.
- **Dependencies:** Network infrastructure.
- **Failure Modes:** Network partition, bandwidth throttling, bucket permission misconfiguration.
- **Scaling Metric:** Ingress/egress bandwidth (Gbps) and request rate.
- **Deployment Justification:** MinIO for local development; AWS S3 or Google Cloud Storage in production.

### Domain 16: Queue & State Broker (Redis)
- **Primary Responsibility:** High-throughput task queues (Redis Streams / Lists), distributed locks (Redlock for single-worker tasks), ephemeral pub/sub for SSE progress events, and caching.
- **API / Event Contracts:** Redis RESP protocol (TCP port 6379).
- **Data Ownership:** Ephemeral queue state, cache keys, worker heartbeat hashes.
- **Resource Profile:** High memory, low to moderate CPU (in-memory operations).
- **Dependencies:** Persistent volume for AOF/RDB snapshots.
- **Failure Modes:** Memory exhaustion (OOM), replication lag in Redis Sentinel/Cluster.
- **Scaling Metric:** Memory usage, connected clients, operations per second.
- **Deployment Justification:** Managed Redis (AWS ElastiCache / Redis Cloud) or Redis StatefulSet with Sentinel in Kubernetes.

### Domain 17: Observability and Operational Tooling
- **Primary Responsibility:** Collecting structured JSON logs, Prometheus metrics, distributed traces (OpenTelemetry), and alerting on SLA breaches (queue backlog, failed jobs).
- **API / Event Contracts:** OTLP gRPC/HTTP endpoints, `/metrics` Prometheus scraping endpoints.
- **Data Ownership:** Metric time-series and log retention volumes.
- **Resource Profile:** Moderate CPU and storage.
- **Dependencies:** OpenTelemetry Collector, Prometheus, Grafana, Loki/Elasticsearch.
- **Failure Modes:** Telemetry backpressure impacting application performance (mitigated via async batch exporters).
- **Scaling Metric:** Telemetry events per second.
- **Deployment Justification:** Standard Kubernetes cluster add-on stack.
