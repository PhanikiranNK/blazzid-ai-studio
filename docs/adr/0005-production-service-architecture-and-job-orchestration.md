# ADR 0005: Production Service Architecture & Distributed Job Orchestration

## Status
Accepted

## Context
Stages 1 through 4 of BLAZZID AI Studio implemented core domain algorithms, media preprocessing, gameplay detection, and highlight montage assembly as local-first modular Python packages. In Stage 5, the system required transformation into an asynchronous, production-oriented service architecture capable of:
1. Exposing a high-performance REST API for submitting video-processing requests.
2. Managing durable job lifecycle records across defined state transitions.
3. Distributing long-running media processing tasks to background workers without blocking HTTP request handlers.
4. Guaranteeing reliable job dispatch even across process crashes between database commits and queue publications.
5. Tracking monotonic job progress through real pipeline stages.
6. Supporting bounded retries, worker lease renewals, and responsive cancellation.
7. Managing media storage safely (protecting against directory traversal, unbounded memory consumption during uploads, and orphaned scratch artifacts).

## Decision

### 1. Service Boundaries and Runtime Packaging
We established two standalone runtime artifacts alongside the domain packages:
- **`blazzid-api` (`apps/api`):** FastAPI HTTP service handling job submissions (streaming multipart uploads or storage references), status retrieval, pagination, cancellation, artifact downloads, and health checks (`/health/live`, `/health/ready`).
- **`blazzid-worker` (`apps/worker`):** Autonomous background daemon that consumes job dispatch events, atomically claims jobs via leases, coordinates the Stages 2–4 media processing pipeline, and writes output artifacts and manifests.

Shared capabilities are cleanly modularized into reusable libraries:
- **`blazzid-storage` (`packages/storage`):** Storage backend abstraction (`StorageBackend`) with `LocalStorageBackend` enforcing path traversal guards, chunked streaming to disk, SHA-256 verification, and scratch isolation.
- **`blazzid-jobs` (`packages/jobs`):** SQLAlchemy 2.0 ORM persistence models (`JobRecord`, `JobAttemptRecord`, `OutboxRecord`), finite state machine validation, outbox dispatcher, and queue adapters.

### 2. Transactional Outbox Pattern for Zero Lost Work
To avoid the dual-write hazard where a database transaction commits but network failure causes queue publishing to fail (leaving jobs permanently orphaned in `QUEUED` state), we implemented a Transactional Outbox:
1. `JobRecord` and `OutboxRecord` are inserted in the exact same atomic database transaction.
2. An `OutboxDispatcher` reads unpublished outbox events, delivers them to the queue, and marks them `published_at = now()`.
3. If publishing fails or the API process terminates abruptly, the outbox record remains unpublished and is reliably dispatched on subsequent recovery sweeps.

### 3. Queue Technology and At-Least-Once Delivery
We selected Redis Streams (`XADD`, `XREADGROUP`, `XACK`) with consumer groups as the primary distributed queue backend:
- Workers join consumer group `blazzid:workers` and consume individual events with `XREADGROUP`.
- Once a job finishes processing (or encounters a terminal error/cancellation), the worker explicitly acknowledges the stream entry via `XACK`.
- To support hermetic offline test suites and developer environments without requiring active Docker containers, we introduced `InMemoryJobQueue` implementing the same `JobQueue` protocol.

### 4. Concurrency Control and Worker Leases
- Workers claim jobs atomically with optimistic locking and worker lease deadlines (`worker_lease_until`).
- If another worker attempts to claim an active job, the claim returns `False`, safely handling duplicate queue deliveries.
- Active workers run an asynchronous background heartbeat thread that continually extends the lease deadline while processing continues.
- If a worker crashes or drops offline, `JobRecoveryService` reclaims abandoned jobs once their lease expires, incrementing the attempt count up to `max_retries`.

### 5. Monotonic 9-Stage Progress Model
We defined 9 explicit, non-decreasing pipeline stages with calibrated progress metrics:
1. `VALIDATING_INPUT` (5%)
2. `PROBING_MEDIA` (10%)
3. `PREPROCESSING` (25%)
4. `DETECTING_EVENTS` (50%)
5. `RANKING_HIGHLIGHTS` (65%)
6. `PLANNING_EDIT` (75%)
7. `RENDERING` (90%)
8. `VALIDATING_OUTPUT` (95%)
9. `FINALIZING` (100%)

Progress values are strictly enforced as monotonically non-decreasing within an execution attempt.

### 6. Media Storage Safety and Chunked Streaming
- Media uploads are streamed directly to disk in bounded 64 KB buffers, ensuring constant memory overhead regardless of source recording size.
- Upload sizes are capped by `MAX_UPLOAD_SIZE_BYTES` (default 500 MB).
- Input filenames are sanitized and stored under isolated job directories (`jobs/{job_id}/source/`, `jobs/{job_id}/scratch/`, `jobs/{job_id}/artifacts/`).
- Scratch directories are deterministically purged upon job termination (success, failure, or cancellation).

## Consequences

### Positive
- Strict separation between HTTP request processing and heavy FFmpeg computation.
- Resilient against crashes: zero lost work via transactional outbox.
- Idempotent API job submission using `X-Idempotency-Key`.
- Clean local developer experience with Docker Compose (`PostgreSQL` + `Redis` + `API` + `Worker`), with full test suite execution supported offline on SQLite and in-memory queue.
- Complete auditability of execution history through `JobAttemptRecord`.

### Trade-offs & Mitigations
- *At-least-once queue delivery:* Handled via atomic database claim check; duplicate deliveries are discarded without re-running media pipeline.
- *Local filesystem storage:* Prepared behind `StorageBackend` interface for simple drop-in addition of S3/GCS object storage backends in future stages.
