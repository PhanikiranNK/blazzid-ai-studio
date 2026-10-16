# ADR 0002: Queue and Event Infrastructure Selection (Redis Streams)

## Status
Accepted

## Date
2026-10-16

## Context
Asynchronous processing of long gaming recordings requires a message broker capable of handling:
1. Task dispatching to worker pools with consumer groups.
2. At-least-once message delivery and explicit acknowledgment (`ACK`).
3. Message inspection, dead-lettering, and delayed task scheduling.
4. Ephemeral pub/sub for real-time progress streaming (Server-Sent Events) to the creator studio frontend.
5. Distributed locking and worker heartbeat tracking.

We evaluated three primary alternatives:
- **Alternative A: Apache Kafka.** Industry standard for massive event streams, but introduces severe operational complexity (ZooKeeper/KRaft, partition management, high JVM memory footprint) that is unwarranted for task queue workloads.
- **Alternative B: RabbitMQ (AMQP).** Mature, feature-rich message broker with complex routing topologies. However, introduces an additional stateful infrastructure dependency alongside Redis (which is already required for session caching and pub/sub).
- **Alternative C: Redis 7 (Redis Streams & Pub/Sub).** Provides persistent, log-based streams with Consumer Groups (`XREADGROUP`, `XACK`, `XPENDING`), sub-millisecond in-memory throughput, native pub/sub for SSE broadcasting, distributed locking via Redlock, and minimal operational overhead.

## Decision
We select **Redis 7 (Redis Streams + Pub/Sub)** as the unified message broker and state coordination backbone for BLAZZID AI Studio.

1. **Task Queues:** Managed via Redis Streams (`queue:preprocess`, `queue:audio_analysis`, `queue:visual_analysis`, `queue:render`). Workers belong to named Consumer Groups and explicitly acknowledge task completion via `XACK`.
2. **Crash Recovery & Pending Tasks:** Unacknowledged tasks from dead workers are inspected and claimed via `XPENDING` and `XCLAIM` by the reconciliation supervisor.
3. **Live Progress:** Workers publish progress percentages (`10%`, `50%`, `100%`) to ephemeral Redis pub/sub channels (`channel:job:{job_id}`), which the API bridges to the web frontend using Server-Sent Events.
4. **Heartbeats & Locks:** Worker heartbeats and single-job mutual exclusion are managed via standard Redis keys with TTLs.

## Consequences

### Positive
- **Single Infrastructure Component:** Redis fulfills caching, queueing, locking, and pub/sub requirements without deploying multiple broker clusters.
- **Developer Simplicity:** Trivially runnable locally via Docker or native binary; low memory footprint ($< 100\text{MB}$ idle).
- **High Observability:** Queue depth, pending messages, and consumer latency are inspectable with standard Redis CLI commands (`XLEN`, `XINFO`).
- **Seamless KEDA Integration:** Native KEDA triggers exist for scaling Kubernetes pods based on Redis Stream pending entries count.

### Negative / Trade-offs
- Redis Streams store payloads in RAM. Payloads must contain references to Object Storage keys rather than large binary blobs.
- Redis persistence (AOF/RDB) must be configured correctly to guarantee durability across node reboots.
