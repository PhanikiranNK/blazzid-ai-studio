# BLAZZID AI Studio — Algorithm Implementation & Evaluation Record

This document records the exact implementation details, mathematical guarantees, empirical benchmarks, and test coverage for the four pure algorithmic primitives implemented in **Stage 1**.

---

## 1. Algorithm A: Top-$K$ Candidate Selection (`top_k.py`)

### 1.1 Problem Statement
Given an unbounded or streaming iterable of $M$ candidate events, select the top $K$ items ranked by utility score without materializing the full stream into memory.

### 1.2 Input and Output Contracts
- **Input:** `stream: Iterable[T]`, `k: int >= 0`, optional `key: Callable[[T], float]`, optional `tie_breaker: Callable[[T], Any]`.
- **Output:** `list[T]` containing at most $K$ items sorted in descending order of score.

### 1.3 Preconditions & Invariants
- $k \ge 0$ (raises `ValueError` if $k < 0$).
- All scores must be finite (`math.isnan(score)` or `math.isinf(score)` raises `ValueError`).
- **Invariant:** Output length is $\min(K, M)$.
- **Invariant:** For all $0 \le i < j < \text{len(result)}$, $\text{score}_i \ge \text{score}_j$.

### 1.4 Algorithmic Details & Complexity
- Implemented using a **bounded min-heap** of size $K$.
- For each item in the stream:
  - If heap size $< K$, push $(score, tie\_key, seq, item)$.
  - If heap size $== K$, compare against the minimum element at root. If strictly greater, perform `heapreplace`.
- Post-processing: sorts the $K$ extracted elements in $O(K \log K)$ descending.
- **Time Complexity:** $O(M \log K)$ worst-case; $O(M + K \log K)$ average (early rejection at root without heap mutation).
- **Space Complexity:** $O(K)$ auxiliary space.

### 1.5 Limitations
- Unbounded streaming assumes the item generator can be iterated once; generator cannot be rewound.

### 1.6 Measured Benchmarks (Apple Silicon Darwin arm64)
- **Workload:** $M = 10,000$ random float candidates, $K = 50$.
- **Measured Latency:** $6.14\text{ ms}$ mean ($162.8\text{ ops/sec}$, $> 1,600,000\text{ candidates/sec}$).

---

## 2. Algorithm B: Weighted Interval Scheduling with Duration Budget (`interval_selection.py`)

### 2.1 Problem Statement
Given $N$ candidate highlight clips with half-open intervals $[s_i, e_i)$, duration $d_i = e_i - s_i$, and utility score $w_i$, select a subset of mutually disjoint clips that maximizes total score $\sum w_i$ subject to total duration $\sum d_i \le D_{\text{target}}$.

### 2.2 Input and Output Contracts
- **Input:** `candidates: Sequence[HighlightCandidate]`, `constraints: SelectionConstraints`.
- **Output:** `SelectionResult` with `selected_candidates`, `total_duration_seconds`, `total_score`, `discarded_count`, and solver diagnostics.

### 2.3 Mathematical Formulation & Invariants
- Let quantum $\Delta t$ be `quantum_bin_seconds` (default 0.5s or 0.1s).
- Total capacity bins: $B = \lfloor D_{\text{target}} / \Delta t \rfloor$.
- Discretized clip cost: $cost_i = \lceil d_i / \Delta t \rceil$.
- Candidates sorted by end time: $e_1 \le e_2 \le \dots \le e_N$.
- Binary search predecessor: $p(i) = \max \{ j < i \mid e_j \le s_i \}$ or $-1$.
- 2D Dynamic Programming Recurrence:
  $$DP[i + 1][b] = \max \begin{cases} 
  DP[i][b] & \text{(Exclude candidate } i\text{)} \\
  DP[p(i) + 1][b - cost_i] + w_i & \text{(Include candidate } i\text{, if } b \ge cost_i\text{)}
  \end{cases}$$
- **Invariant:** Zero pairwise overlap ($\max(s_a, s_b) \ge \min(e_a, e_b)$ for all selected pairs).
- **Invariant:** Total continuous duration $\le D_{\text{target}}$ (guaranteed because $\sum d_i \le \sum (cost_i \cdot \Delta t) \le B \cdot \Delta t \le D_{\text{target}}$).

### 2.4 Comparison Against Exhaustive Brute-Force Oracle
- An exact oracle `exhaustive_interval_selection` evaluates all $2^N$ subsets for $N \le 18$.
- Property tests verify that the DP algorithm achieves $\ge 85\%$ of the continuous theoretical maximum, and on fine quantum discretization ($\Delta t = 0.1\text{s}$) achieves $100\%$ score match with the exhaustive oracle.

### 2.5 Complexity
- **Time:** $O(N \log N + N \cdot B)$.
- **Space:** $O(N \cdot B)$ for table and backtracking matrix.

### 2.6 Measured Benchmarks
- **Workload:** $N = 100$ candidate clips, budget $D_{\text{target}} = 180\text{s}$, quantum $\Delta t = 0.5\text{s}$ ($B = 360$ capacity bins, 36,000 cells).
- **Measured Latency:** $10.78\text{ ms}$ mean ($92.8\text{ ops/sec}$).

---

## 3. Algorithm C: Rolling Feature Statistics (`rolling_statistics.py`)

### 3.1 Problem Statement
Continuously compute rolling mean $\mu$, rolling variance $\sigma^2$, and dynamic z-score spikes $z = (x - \mu) / (\sigma + \epsilon)$ over a sliding window $W$ of continuous media features (e.g., audio RMS energy, frame difference).

### 3.2 Numerical Stability & Drift Correction
- **Catastrophic Cancellation Hazard:** When values have high magnitude ($x \approx 10^9$) but low variance, naive single-pass prefix sums $\sum x^2 - (\sum x)^2 / W$ produce severe floating-point rounding errors and negative variances.
- **Mitigation:**
  1. Variance is clamped: $\sigma^2 = \max(0.0, \text{raw\_var})$.
  2. Bounded ring buffer (`collections.deque(maxlen=window_size)`).
  3. Periodic exact re-accumulation every 1,024 updates resets accumulated float precision drift to zero.
  4. Division by zero in z-score is guarded by $\epsilon > 0$.

### 3.3 Complexity
- **Time:** $O(1)$ amortized per sample update.
- **Space:** $O(W)$ bounded buffer memory.

### 3.4 Measured Benchmarks
- **Workload:** 50,000 continuous Gaussian float samples with window $W = 100$.
- **Measured Latency:** $55.93\text{ ms}$ mean ($> 890,000\text{ samples/sec}$).

---

## 4. Algorithm D: 64-bit Perceptual Hash Distance (`perceptual_hash.py`)

### 4.1 Problem Statement
Compute the exact Hamming distance (number of differing bits) between two 64-bit perceptual image hashes (e.g., dHash or pHash) to determine screen state equivalence.

### 4.2 Representation & Input Normalization
- Accepts:
  - `int`: $0 \le h \le 2^{64} - 1$.
  - `str`: 16-character hexadecimal string (with optional `0x`/`0X` prefix).
  - `bytes` / `bytearray`: exactly 8 bytes (big-endian).
- Rejects negative integers, integers $\ge 2^{64}$, invalid hex strings, or byte sequences with length $\neq 8$.

### 4.3 Implementation & Metric Properties
- Formula: $\text{popcount}(h_1 \oplus h_2)$.
- Hardware acceleration via native `int.bit_count()` on Python 3.10+, with portable fallback on Python 3.9 (`bin(diff).count("1")`).
- **Mathematical Invariants Verified via Hypothesis:**
  1. Identity: $d(x, x) = 0$.
  2. Range: $0 \le d(x, y) \le 64$.
  3. Symmetry: $d(x, y) = d(y, x)$.
  4. Triangle Inequality: $d(x, z) \le d(x, y) + d(y, z)$.

### 4.4 Measured Benchmarks
- **Workload:** 10,000 pairwise 64-bit hash Hamming comparisons.
- **Measured Latency:** $6.59\text{ ms}$ mean ($> 1,510,000\text{ comparisons/sec}$).
