# BLAZZID AI Studio — Testing & Quality Evaluation Framework

## 1. Quality Assurance Philosophy & The Test Pyramid

In an AI-assisted media intelligence system, traditional unit tests are necessary but insufficient. Code correctness does not guarantee video quality, audio synchronization, or meaningful highlight selection. 

BLAZZID AI Studio enforces a comprehensive testing pyramid combining deterministic software verification with empirical ground-truth benchmark evaluation:

```
                      ▲
                     / \
                    /   \     Stage 9: Quality & Creator Acceptance Evaluation
                   / E2E \    (Ground-Truth Gameplay Benchmark Dataset)
                  /-------\
                 / Chaos & \   Stage 8: Failure Injection & Worker Crash Recovery
                / Benchmark \  (Chaos tests, synthetic OOM, network latency)
               /-------------\
              /  Integration  \ Stage 5: DB, Queue, S3, & Contract Testing
             /   & Contracts   \ (Testcontainers PostgreSQL, Redis, MinIO)
            /-------------------\
           /   Property-Based    \ Stage 1-4: Mathematical Invariant Verification
          /    & Algorithm Tests  \ (Hypothesis: interval overlap, DP, FSM)
         /-------------------------\
        /        Unit Tests         \ Fast, Isolated Component Tests
       / (Detectors, Filters, DTOs)  \ (< 50ms per test, mocked external I/O)
      /───────────────────────────────\
```

---

## 2. Testing Levels & Tooling Matrix

| Level | Primary Objective | Key Tools & Frameworks | Execution Target | Frequency |
| :--- | :--- | :--- | :--- | :--- |
| **Unit Tests** | Verify isolated algorithms, mathematical transforms, data parsers, and DTOs. | `pytest`, `pytest-cov`, `unittest.mock` | Local / CI | Every Git commit |
| **Property-Based Tests** | Fuzz interval algebra, timestamp arithmetic, and state transitions across 10,000+ random inputs. | `Hypothesis` (Python) | Local / CI | Every PR |
| **Integration Tests** | Validate database queries, Redis consumer groups, and S3 multipart upload flows against real services. | `Testcontainers` (PostgreSQL 16, Redis 7, MinIO) | Docker / CI | Nightly / Pre-merge |
| **Contract Tests** | Verify REST responses match OpenAPI schemas and SSE events match JSON schemas. | `Schemathesis`, `Pydantic v2` | CI | Every PR |
| **Media Fixture Tests** | Process small synthetic video/audio files (1s–5s generated via FFmpeg) to test codecs, crops, and filters. | `FFmpeg`, `OpenCV`, `SoundFile` | Local / CI | Every PR |
| **Chaos & Failure Tests** | Kill worker processes mid-render; inject Redis network timeouts; simulate corrupted S3 parts. | Custom Chaos harnesses, `toxiproxy` | Staging cluster | Weekly |
| **Performance Benchmarks** | Profile top-$K$ selection, sweep-line aggregation, and DP solver throughput. | `pytest-benchmark`, `cProfile` | Dedicated runner | Milestone releases |
| **Quality Evaluation** | Benchmark highlight precision, recall, and boundary accuracy against human-annotated video ground truth. | Custom evaluation CLI, IoU scoring scripts | Offline evaluation | Algorithm releases |

---

## 3. Property-Based Testing with Hypothesis

Testing temporal algorithms with handcrafted inputs leaves blind spots in boundary arithmetic. We use `Hypothesis` to prove algorithmic invariants over thousands of generated intervals:

```python
from hypothesis import given, strategies as st
from blazzid.algorithms.interval_scheduling import weighted_interval_scheduling, Interval

interval_strategy = st.builds(
    Interval,
    start=st.floats(min_value=0.0, max_value=3600.0, allow_nan=False),
    duration=st.floats(min_value=1.0, max_value=30.0, allow_nan=False),
    weight=st.floats(min_value=0.1, max_value=100.0, allow_nan=False)
).filter(lambda x: x.start + x.duration <= 3600.0)

@given(st.lists(interval_strategy, min_size=1, max_size=100), st.floats(min_value=10.0, max_value=300.0))
def test_weighted_interval_scheduling_invariants(intervals, max_budget):
    selected = weighted_interval_scheduling(intervals, max_budget=max_budget)
    
    # Invariant 1: Budget limit is never exceeded
    total_duration = sum(item.duration for item in selected)
    assert total_duration <= max_budget + 1e-4
    
    # Invariant 2: Zero pairwise overlap among selected intervals
    sorted_selected = sorted(selected, key=lambda x: x.start)
    for i in range(len(sorted_selected) - 1):
        curr = sorted_selected[i]
        next_item = sorted_selected[i + 1]
        assert curr.start + curr.duration <= next_item.start, (
            f"Overlap detected: {curr} overlaps with {next_item}"
        )
```

---

## 4. Synthetic Media Fixtures for Fast CI

Real video files are gigabytes in size and cannot be committed to Git. We generate minimal, reproducible synthetic test fixtures on the fly in test setups using FFmpeg:

```python
import subprocess
import tempfile
from pathlib import Path

def generate_synthetic_gameplay_fixture(duration_seconds: int = 5, has_audio: bool = True) -> Path:
    """
    Generates a 5-second 1280x720 30fps H.264 video with synthetic audio tones
    and test patterns for instant deterministic testing.
    """
    tmp_path = Path(tempfile.mktemp(suffix=".mp4"))
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={duration_seconds}:size=1280x720:rate=30",
    ]
    if has_audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=1000:duration={duration_seconds}"]
        cmd += ["-c:a", "aac", "-b:a", "128k"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(tmp_path)]
    
    subprocess.run(cmd, check=True, capture_output=True)
    return tmp_path
```

---

## 5. Highlight Quality Evaluation Metrics (Ground-Truth Benchmark)

To quantitatively evaluate whether BLAZZID AI Studio selects genuine highlights, we construct a curated **Evaluation Dataset**:
- **Dataset Size:** 20 full-length Brawl Stars recordings (15–20 hours total footage across Gem Grab, Brawl Ball, Bounty, and Showdown).
- **Ground Truth:** Each recording is manually annotated by 3 independent competitive players, marking the exact ground-truth highlight intervals $[s_g, e_g)$ and event labels (e.g., "Triple Kill", "Clutch Goal Save").

### 5.1 Temporal Intersection-over-Union (tIoU)
For a predicted candidate interval $I_p = [s_p, e_p)$ and a ground truth interval $I_g = [s_g, e_g)$:

$$\text{tIoU}(I_p, I_g) = \frac{\max(0, \min(e_p, e_g) - \max(s_p, s_g))}{\max(e_p, e_g) - \min(s_p, s_g)}$$

A predicted highlight is counted as a **True Positive (TP)** if:
1. $\text{tIoU}(I_p, I_g) \ge \tau$ (standard threshold $\tau = 0.50$, strict threshold $\tau = 0.75$).
2. Event category matches ground truth.

### 5.2 Target Quality Evaluation Metrics

| Metric | Definition | Minimum Acceptance Target (Stage 0 Baseline) | Production Target (Stage 9) |
| :--- | :--- | :--- | :--- |
| **Precision @ $\tau = 0.5$** | $\frac{\text{TP}}{\text{TP} + \text{FP}}$ (Percentage of detected highlights that are genuine) | $\ge 70.0\%$ | $\ge 85.0\%$ |
| **Recall @ $\tau = 0.5$** | $\frac{\text{TP}}{\text{TP} + \text{FN}}$ (Percentage of genuine highlights successfully detected) | $\ge 65.0\%$ | $\ge 80.0\%$ |
| **F1 Score** | $2 \cdot \frac{\text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}}$ | $\ge 67.4\%$ | $\ge 82.4\%$ |
| **Boundary IoU** | Average tIoU of True Positive intervals | $\ge 0.60$ | $\ge 0.75$ |
| **Duplicate Rate** | Percentage of selected highlights that duplicate the same in-game sequence | $\le 2.0\%$ | $\le 0.5\%$ |
| **Creator Acceptance Rate** | Percentage of auto-selected candidates retained by creators without manual deletion | $\ge 75.0\%$ | $\ge 90.0\%$ |
| **Audio/Video Sync Drift** | Temporal offset between audio claps/stingers and visual frame changes | $\le 25\text{ms}$ | $\le 10\text{ms}$ |

---

## 6. Continuous Evaluation & Regression Gating

In our CI/CD pipeline, every algorithm modification triggers a regression run against a 2-hour mini-benchmark dataset. If an algorithm update increases F1 score but drops Recall below the acceptable threshold (or increases processing latency by $> 15\%$), the pull request is blocked automatically.
