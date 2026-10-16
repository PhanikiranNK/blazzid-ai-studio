# ADR 0001: Modular Monolith with Separately Deployed Workers

## Status
Accepted

## Date
2026-10-16

## Context
BLAZZID AI Studio requires high developer velocity to build and refine multimodal AI and media algorithms, while simultaneously demanding strict runtime isolation for compute-intensive, memory-heavy video decoding and neural network inference.

A single unified monolith risks catastrophic failures: an FFmpeg transcode crash or an out-of-memory (OOM) error from a machine learning model would terminate the entire web server, dropping active user sessions and HTTP connections.

Conversely, decomposing the application into 15+ independent microservices from day one introduces severe operational complexity: distributed transactions, network latency across video frame transfers, continuous API contract synchronization across dozens of repositories, and complex deployment pipelines.

## Decision
We adopt a **Modular Monolith codebase with Separately Deployed Runtime Workers**:

1. **Single Monorepo & Codebase:** The entire application lives in a single repository with strict internal module boundaries (`/packages/core`, `/packages/algorithms`, `/services/api`, `/services/worker`). Modules communicate via strongly typed in-process interfaces and DTOs.
2. **Two Primary Deployable Artifacts:**
   - **Studio API Service:** Lightweight asynchronous HTTP/WebSocket server (FastAPI) handling user authentication, project CRUD, timeline queries, and job coordination.
   - **Media & AI Worker Pool:** Stateless asynchronous background workers consuming tasks from Redis Streams. Workers execute video probing, audio analysis, OCR, and FFmpeg rendering.
3. **Hardware-Targeted Worker Pools:** In production Kubernetes, the worker image is deployed across separate node pools:
   - **CPU Worker Pool:** Optimized for multi-threaded FFmpeg decoding, audio FFTs, and proxy generation.
   - **GPU Worker Pool:** Equipped with GPU tolerations for neural inference and batch OCR.
   - **Render Worker Pool:** Sized for heavy multi-track video assembly and transcode I/O.

```
       [ Git Monorepo: Modular Domain Architecture ]
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
    [ Deployable Container:     [ Deployable Container:
       Studio API Service ]        Media Worker Pool ]
             │                           │
             ▼                           ▼
    (HTTP / API Node Pool)      (Compute / GPU Node Pool)
```

## Consequences

### Positive
- **Fault Isolation:** A crash or OOM during video processing cannot bring down the API server or creator editing sessions.
- **Independent Scaling:** Web pods scale based on HTTP requests per second (RPS); worker pods scale dynamically based on Redis Stream backlog depth via KEDA.
- **High Development Velocity:** Shared domain types, zero inter-service serialization boilerplate, and single-command local development via Docker Compose (`docker compose up`).
- **Pragmatic Evolutionary Path:** Internal domain modules are decoupled and can be extracted into true standalone microservices in the future if team or organizational scale demands it.

### Negative / Trade-offs
- Deployment requires managing at least two distinct container configurations (API vs. Worker) even in early stages.
- Developers must maintain discipline against circular dependencies between internal domain packages.
