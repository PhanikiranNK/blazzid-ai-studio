# BLAZZID AI Studio — Kubernetes Deployment & Infrastructure Design

## 1. Local Development vs. Production Kubernetes

| Dimension | Local Development (Docker Compose) | Production (Kubernetes) |
| :--- | :--- | :--- |
| **Orchestrator** | Docker Compose v2 | Kubernetes 1.29+ (EKS / GKE / Self-managed) |
| **Compute Units** | 1 API container, 1 unified Worker container | Dedicated Web Deployment, separate CPU/GPU Worker Deployments |
| **Object Storage** | MinIO (single node container) | AWS S3 / Google Cloud Storage with IAM Roles (IRSA / Workload Identity) |
| **Queue / Cache** | Redis 7 standalone container | Managed Redis (ElastiCache / Cloud Memorystore) or Redis Cluster StatefulSet |
| **Database** | PostgreSQL 16 container with local volume | Managed RDS / Cloud SQL with automated failover and read replicas |
| **Scaling Mechanism** | Static container count | KEDA (Queue-depth based) + Horizontal Pod Autoscaler (HPA) |
| **Ingress & TLS** | Traefik / Nginx reverse proxy, self-signed TLS | Gateway API / Ingress-NGINX with cert-manager and AWS ALB / Cloud Load Balancer |
| **Operational Burden** | Very Low: `docker compose up -d` handles entire environment | High: Requires network policies, pod disruption budgets, node pools, secrets management |

**Operational Boundary:** Docker Compose is the default environment for day-to-day feature development, unit testing, and integration verification. Kubernetes manifests are maintained as Helm charts or Kustomize overlays for staging and production environments.

---

## 2. Kubernetes Topology & Workload Mapping

```
                                  [ Ingress Controller / ALB ]
                                                │
                                    (HTTPS / W3C TraceContext)
                                                │
                                                ▼
                                    [ Service: studio-api-svc ]
                                                │
                                  ┌─────────────┴─────────────┐
                                  ▼                           ▼
                     [ Pod: studio-api ]             [ Pod: studio-api ]
                     (Requests: 500m / 512MB)        (Requests: 500m / 512MB)
                                  │                           │
                   ┌──────────────┴───────────────┐           │
                   ▼                              ▼           ▼
        [ Managed PostgreSQL 16 ]            [ Managed Redis 7 Streams ]
                   ▲                              ▲     ▲     ▲
                   │                              │     │     │
                   │               ┌──────────────┘     │     └──────────────┐
                   │               ▼                    ▼                    ▼
                   │        [ Pod: worker-cpu ]  [ Pod: worker-gpu ]  [ Pod: worker-render ]
                   │        • Preprocess & Audio • Visual & OCR       • FFmpeg Render
                   │        (CPU Node Pool)      (GPU/G4dn Node Pool) (Compute Node Pool)
                   │               │                    │                    │
                   └───────────────┴────────────────────┴────────────────────┘
                                           │
                                           ▼
                             [ S3 / MinIO Object Storage ]
```

---

## 3. Workload Sizing: Resource Requests, Limits & Probes

| Workload | Container Image | CPU Request | CPU Limit | RAM Request | RAM Limit | Ephemeral Storage | Probes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **studio-api** | `blazzid/studio-api:latest` | 500m | 1000m | 512Mi | 1Gi | 2Gi | Startup: `/health/startup`<br>Liveness: `/health/liveness`<br>Readiness: `/health/readiness` |
| **worker-cpu** | `blazzid/media-worker:latest` | 1000m | 2000m | 2Gi | 4Gi | 20Gi (scratch) | Liveness: File touch `/tmp/healthy` by worker loop |
| **worker-gpu** | `blazzid/infer-worker:latest` | 2000m | 4000m | 4Gi | 8Gi (+ 1 NVIDIA GPU) | 10Gi | Liveness: Model inference health check |
| **worker-render** | `blazzid/media-worker:latest` | 2000m | 4000m | 4Gi | 8Gi | 50Gi (scratch) | Liveness: File touch `/tmp/healthy` by render loop |

### Pod Probe Configuration Example (Studio API):
```yaml
livenessProbe:
  httpGet:
    path: /health/liveness
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3
readinessProbe:
  httpGet:
    path: /health/readiness
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
  timeoutSeconds: 2
  failureThreshold: 2
startupProbe:
  httpGet:
    path: /health/startup
    port: 8000
  initialDelaySeconds: 2
  periodSeconds: 5
  failureThreshold: 12 # 60s total startup grace window
```

---

## 4. Autoscaling Strategy: KEDA & Queue-Depth Scaling

Standard Kubernetes HPA scales on CPU or memory percentage. **This fails completely for asynchronous workers:**
- If 10 long render jobs arrive in the queue, CPU usage remains low until workers pick them up; standard HPA will not scale up.
- Conversely, when workers are rendering at 100% CPU, scaling them up won't help if no more jobs are in the queue.

### Solution: KEDA (Kubernetes Event-driven Autoscaling)
We deploy KEDA ScaledObjects that scale worker pods directly based on the backlog depth of Redis Streams.

#### KEDA ScaledObject Specification:
```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: render-worker-scaler
  namespace: blazzid-studio
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: worker-render
  minReplicaCount: 1
  maxReplicaCount: 12
  cooldownPeriod: 300 # 5 minutes cooldown before scale-down
  pollingInterval: 15 # Poll Redis every 15s
  triggers:
    - type: redis-streams
      metadata:
        address: redis-broker.blazzid-studio.svc.cluster.local:6379
        stream: queue:render
        consumerGroup: render-workers
        pendingEntriesCount: "1" # Scale 1 pod per pending render job
```

---

## 5. Node Affinity, Taints & Tolerations for GPU Scheduling

Visual analysis and VLM inference require dedicated GPU capacity. We separate GPU workers from general web workloads using Kubernetes taints and node affinity.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: worker-gpu
  namespace: blazzid-studio
spec:
  replicas: 1
  template:
    metadata:
      labels:
        app: worker-gpu
    spec:
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: node.kubernetes.io/instance-type
                    operator: In
                    values: ["g4dn.xlarge", "g5.xlarge"]
      tolerations:
        - key: "nvidia.com/gpu"
          operator: "Exists"
          effect: "NoSchedule"
      containers:
        - name: inference-worker
          image: blazzid/infer-worker:latest
          resources:
            limits:
              nvidia.com/gpu: 1
              memory: 8Gi
              cpu: "4000m"
            requests:
              nvidia.com/gpu: 1
              memory: 4Gi
              cpu: "2000m"
```

---

## 6. Network Policies & Least-Privilege Security

Pods communicate only over authorized paths. By default, all ingress and egress are denied unless explicitly allowed.

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-network-policy
  namespace: blazzid-studio
spec:
  podSelector:
    matchLabels:
      app: studio-api
  policyTypes:
    - Ingress
    - Egress
  ingress:
    # Allow traffic only from Ingress Controller
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
      ports:
        - protocol: TCP
          port: 8000
  egress:
    # Allow traffic to PostgreSQL, Redis, and DNS
    - to:
        - podSelector:
            matchLabels:
              app: postgresql
        - podSelector:
            matchLabels:
              app: redis
      ports:
        - protocol: TCP
          port: 5432
        - protocol: TCP
          port: 6379
    # CoreDNS
    - to:
        - namespaceSelector: {}
      ports:
        - protocol: UDP
          port: 53
```

---

## 7. Graceful Termination & Pod Disruption

- **Termination Grace Period:** Worker pods handling long FFmpeg renders or video chunk processing specify `terminationGracePeriodSeconds: 60`.
- **PreStop Hook:** Upon receiving `SIGTERM`, workers cease claiming new tasks from Redis and gracefully flush active chunk buffers.
- **Pod Disruption Budget (PDB):** Enforces that at least 1 `studio-api` pod remains available during voluntary node drains or rolling upgrades:
  ```yaml
  apiVersion: policy/v1
  kind: PodDisruptionBudget
  metadata:
    name: studio-api-pdb
    namespace: blazzid-studio
  spec:
    minAvailable: 1
    selector:
      matchLabels:
        app: studio-api
  ```

---

## 8. Rollout, Rollback & Database Migration Procedure

1. **Pre-Deployment Migration Job:** Before deploying new application pods, a Kubernetes `Job` runs Alembic database migrations. If the migration fails, deployment halts immediately.
2. **Rolling Update:** Kubernetes updates pods with `maxSurge: 25%` and `maxUnavailable: 0`.
3. **Automated Rollback:** If newly deployed pods fail their startup or readiness probes, Kubernetes pauses the rollout and reverts to the previous revision.
