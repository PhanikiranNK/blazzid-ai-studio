# BLAZZID AI Studio — Algorithm Design & Performance Engineering

## 1. Algorithmic Overview & Principles

Every algorithm in BLAZZID AI Studio directly addresses a concrete product challenge: transforming hours of continuous gameplay into an optimal, non-overlapping sequence of high-utility video highlights subject to strict temporal constraints.

We adhere to the **Pragmatic Complexity Principle**:
> *Prefer the simplest provably correct algorithm that satisfies performance requirements. Avoid exotic data structures (e.g., dynamic segment trees) when an $O(N \log N)$ sweep-line or array-backed dynamic programming solution meets memory and throughput targets.*

---

## 2. Algorithm 1: Top-$K$ Candidate Selection

### 1. Concrete Problem
A 2-hour recording may generate $M \approx 500$ to $2,000$ preliminary candidate events across audio, visual, and OCR detectors. The system must select the top $K$ candidates ($K \ll M$, typically $K \in [20, 50]$) to enter the dynamic programming optimizer, filtering out low-utility noise without the overhead of sorting the entire candidate array.

### 2. Input and Output Data Structures
- **Input:** Unordered array of Candidate objects: `Array<Candidate>` where each candidate has a `score: float64` and metadata.
- **Output:** Array of $K$ highest-scoring candidates sorted in descending order: `Array<Candidate>`.

### 3. Baseline Solution
Full array sort (Timsort / Quicksort): sort all $M$ elements in descending order and slice the first $K$ elements.
- Time Complexity: $O(M \log M)$
- Space Complexity: $O(M)$ auxiliary memory.

### 4. Preferred Algorithm & Justification
**Min-Heap of Size $K$ (Online Selection):**
Maintain a binary min-heap bounded at capacity $K$. For each candidate in the stream:
1. If heap size $< K$, push candidate.
2. If candidate score $>$ heap root (`min_element`), pop root and push candidate.
3. At the end of the stream, extract all $K$ elements and reverse them.

**Justification:** When $K \ll M$ (e.g., $K=30, M=2000$), $M \log K \approx 2000 \times 5 = 10,000$ operations, compared to $M \log M \approx 2000 \times 11 = 22,000$ operations. More importantly, it operates as an **online streaming algorithm** with bounded $O(K)$ auxiliary memory, allowing candidates to be filtered as detectors emit them without accumulating the entire stream in memory.

### 5. Time and Space Complexity
- **Time Complexity:** $O(M \log K)$ worst-case. In practice, after the first $K$ elements, most elements are rejected with an $O(1)$ comparison against the root, yielding average time $O(M + K \log K)$.
- **Space Complexity:** $O(K)$ auxiliary space for the heap.

### 6. Edge Cases
- $M \le K$: Return all elements sorted ($O(M \log M)$).
- $K = 0$: Return empty array immediately.
- Identical scores: Use tie-breaking by candidate confidence, then earlier timestamp to maintain determinism.

### 7. Correctness Invariants
- At any step $i$ ($i \ge K$), the min-heap contains the $K$ largest elements seen among the first $i$ elements.
- The root of the min-heap is always the minimum among the current top $K$ elements.

### 8. Unit & Property-Based Test Ideas
- **Property:** For any random array of $M$ floats and random $K \in [1, M]$, the output of `TopKMinHeap` must set-equal the top $K$ elements of `sort(array)[::-1][:K]`.
- **Property:** Idempotency and stability on identical inputs.

### 9. Performance Benchmarks
- Benchmark $M=10,000$, $K=50$: Expected throughput $> 5,000,000\text{ candidates/sec}$ in pure Python/C.

### 10. Conditions Justifying Advanced Alternatives
If $M > 100,000$ and $K > 1,000$, an in-place `Quickselect` ($O(M)$ average time) followed by a sort of the top $K$ elements ($O(K \log K)$) would be faster, but for our workload ($M \le 5,000$), the min-heap has lower constant factors and streaming compatibility.

---

## 3. Algorithm 2: Constrained Highlight Selection via Weighted Interval Scheduling (Dynamic Programming)

### 1. Concrete Problem
Given $N$ candidate highlight clips, each with an interval $[s_i, e_i)$ where $s_i < e_i$, duration $d_i = e_i - s_i$, utility score $w_i > 0$, and a target total reel duration $D_{\text{target}}$ (e.g., 180 seconds), select a subset of non-overlapping clips that maximizes total score $\sum w_i$ without exceeding $D_{\text{target}}$.

### 2. Input and Output Data Structures
- **Input:** 
  - List of intervals $C = [c_1, c_2, \dots, c_N]$ where $c_i = (s_i, e_i, d_i, w_i)$.
  - Maximum total reel duration budget $D_{\text{target}} \in \mathbb{R}^+$.
  - Maximum allowable pairwise overlap threshold $\theta \in [0.0, 1.0]$ (default $\theta = 0.0$ for zero overlap).
- **Output:** 
  - Subset $S \subseteq C$ such that no two intervals overlap and $\sum_{c \in S} d_c \le D_{\text{target}}$, maximizing $\sum_{c \in S} w_c$.

### 3. Baseline Solution
Greedy interval scheduling by score ($w_i$) or score density ($w_i / d_i$).
- Greedy fails to find the optimal solution when interval weights and durations vary (it is only optimal for unweighted unit-interval scheduling).

### 4. Preferred Algorithm & Justification
**Two-Dimensional Dynamic Programming (Weighted Interval Scheduling with Knapsack Capacity):**
1. **Sort:** Sort all intervals by end time $e_i$: $e_1 \le e_2 \le \dots \le e_N$.
2. **Precompute Predecessors:** For each interval $i$, find the latest compatible predecessor $p(i)$ using binary search:
   $$p(i) = \max \{ j < i \mid e_j \le s_i \}$$
   Precomputation takes $O(N \log N)$ total time.
3. **Discretize Budget:** Discretize $D_{\text{target}}$ into $B = \lfloor D_{\text{target}} / \Delta t \rfloor$ time quantum bins (e.g., $\Delta t = 0.5\text{s}$, for $D=180\text{s}$, $B = 360$).
4. **DP Recurrence:**
   Let $DP[i][b]$ be the maximum weight achievable considering a subset of intervals from $\{1, \dots, i\}$ with total duration at most $b \cdot \Delta t$:
   $$DP[i][b] = \max \begin{cases} 
   DP[i - 1][b] & \text{(Exclude interval } i\text{)} \\
   DP[p(i)][b - \lceil d_i / \Delta t \rceil] + w_i & \text{(Include interval } i\text{, if } b \ge \lceil d_i / \Delta t \rceil\text{)} 
   \end{cases}$$
5. **Backtracking:** Trace backwards from $DP[N][B]$ to reconstruct the optimal set of intervals $S$.

### 5. Time and Space Complexity
- **Time Complexity:** $O(N \log N + N \cdot B)$. For $N = 100$ and $B = 360$, $N \cdot B = 36,000$ operations ($< 2\text{ms}$ execution time).
- **Space Complexity:** $O(N \cdot B)$ matrix, which can be optimized to $O(B)$ space if only the maximum score is needed, or $O(N \cdot B)$ with bitmasks for backtracking. At $100 \times 360 \times 4\text{ bytes} \approx 144\text{ KB}$, memory footprint is negligible.

### 6. Edge Cases
- No compatible intervals fit in budget $D_{\text{target}}$: Return highest-scoring single clip that fits, or empty list if all $d_i > D_{\text{target}}$.
- All intervals mutually disjoint: Reduces to standard 0/1 Knapsack.
- Identical interval bounds with different scores: Prune all but the highest-scoring candidate during preprocessing.

### 7. Correctness Invariants
- For any subproblem $(i, b)$, $DP[i][b]$ is monotonically non-decreasing with respect to $b$:
  $$DP[i][b] \ge DP[i][b - 1]$$
- No two selected clips $j, k \in S$ have overlapping intervals: $[s_j, e_j) \cap [s_k, e_k) = \emptyset$.

### 8. Unit & Property-Based Test Ideas
- **Unit Test:** Handcrafted intervals where greedy choice fails (e.g., long clip with moderate score vs two short clips with higher combined score).
- **Property:** Overlap invariant: for all pairs in $S$, $\max(0, \min(e_a, e_b) - \max(s_a, s_b)) == 0$.
- **Property:** Budget invariant: $\sum_{c \in S} d_c \le D_{\text{target}}$.

### 9. Performance Benchmarks
- Benchmark with $N = 500$ candidates, $B = 720$ bins ($D=360\text{s}$ at 0.5s resolution): DP table solve $< 15\text{ms}$ in Python.

### 10. Conditions Justifying Advanced Alternatives
If duration budget discretization is unacceptable (e.g., continuous millisecond precision required) and $N > 1,000$, we would formulate this as a Mixed-Integer Linear Program (MILP) solved via HiGHS or CBC solver. However, 0.5s discretization error is visually imperceptible in video editing.

---

## 4. Algorithm 3: Sweep-Line Multimodal Evidence Aggregation

### 1. Concrete Problem
Audio detectors emit continuous energy spikes $[s_a, e_a)$, visual detectors emit HUD state transitions $[s_v, e_v)$, and OCR emits text detections at discrete timestamps $t_{\text{ocr}}$. The system must correlate these disparate signals into unified multimodal event clusters without an $O(N_a \cdot N_v \cdot N_{\text{ocr}})$ nested loop comparison.

### 2. Input and Output Data Structures
- **Input:** Heterogeneous list of temporal events:
  - Audio spikes: $(s, e, \text{type}=\text{AUDIO}, \text{weight})$
  - Visual detections: $(s, e, \text{type}=\text{VISUAL}, \text{weight})$
  - OCR observations: $(t, t, \text{type}=\text{OCR}, \text{weight})$
- **Output:** Unified cluster intervals $[t_{\text{start}}, t_{\text{end}})$ with aggregated evidence vectors.

### 3. Baseline Solution
Pairwise cross-comparison: for each visual event, scan all audio events and all OCR events within window $\pm \Delta t$.
- Time Complexity: $O(N^2)$ where $N$ is total observation count. For $N=10,000$, $N^2 = 10^8$ operations.

### 4. Preferred Algorithm & Justification
**Sweep-Line (Event-Point) Algorithm:**
1. Transform each interval $[s_i, e_i)$ into two discrete event points:
   - `START` event at $t = s_i$
   - `END` event at $t = e_i$
2. For instantaneous events (OCR at $t$), create a temporal tolerance interval $[t - \delta, t + \delta)$ (e.g., $\delta = 1.5\text{s}$).
3. Sort all $2N$ event points by timestamp $t$. Ties broken by placing `START` events before `END` events.
4. Sweep a vertical line from left to right across time:
   - Maintain an active multiset (hash map) of active detectors and their current feature values.
   - When active evidence surpasses a composite confidence threshold $\Gamma_{\text{trigger}}$, open a new `GameplayEvent`.
   - When active evidence drops below $\Gamma_{\text{exit}}$ and remains low for cooldown $\tau_{\text{cooldown}}$, close the `GameplayEvent` and record its boundaries.

### 5. Time and Space Complexity
- **Time Complexity:** $O(N \log N)$ to sort $2N$ endpoints; $O(N)$ linear pass for the sweep line. Overall: $O(N \log N)$.
- **Space Complexity:** $O(N)$ to store endpoints and active multiset.

### 6. Edge Cases
- Rapid successive events within cooldown window: Merged into a compound multi-kill event.
- Zero audio or zero visual events: Fallback to single-modality scoring with penalized confidence.

### 7. Correctness Invariants
- At any timestamp $t$ during the sweep, the active multiset contains exactly those observations whose original interval satisfies $s_i \le t < e_i$.

### 8. Unit & Property-Based Test Ideas
- Synthetic event generator with known ground-truth overlapping intervals.
- Verify that shifting all input timestamps by a constant $C$ produces identically shifted output intervals.

---

## 5. Algorithm 4: Rolling Statistics & Adaptive Energy Thresholding

### 1. Concrete Problem
Raw audio RMS energy and visual frame difference metrics have non-stationary baselines across different recordings (e.g., quiet commentator vs. loud background music). The system must compute rolling mean $\mu(t)$ and rolling standard deviation $\sigma(t)$ over a sliding window of length $W$ (e.g., $W = 10\text{s}$) to compute dynamic z-score spikes:
$$z(t) = \frac{x(t) - \mu(t)}{\sigma(t)}$$
Computing this naively over $L = 108,000$ audio frames ($1\text{ hour}$ at $30\text{ fps}$) would take $O(L \cdot W)$ operations.

### 2. Preferred Algorithm & Justification
**Prefix Sums & Welford's Streaming Algorithm:**
1. Compute prefix sum array $P_1[i] = \sum_{j=1}^i x[j]$ and squared prefix sum array $P_2[i] = \sum_{j=1}^i x[j]^2$.
2. For any arbitrary window $[a, b]$ of length $k = b - a + 1$:
   $$\text{Sum} = P_1[b] - P_1[a - 1]$$
   $$\text{SumSq} = P_2[b] - P_2[a - 1]$$
   $$\mu = \frac{\text{Sum}}{k}, \quad \sigma^2 = \frac{\text{SumSq}}{k} - \mu^2$$
3. Query time is strictly **$O(1)$** per window.

### 3. Complexity
- **Time:** $O(L)$ preprocessing, $O(1)$ query per frame. Total time for 1 hour of audio: $< 5\text{ms}$.
- **Space:** $O(L)$ for the prefix arrays (can be computed in streaming $O(W)$ memory if processed online).

---

## 6. Algorithm 5: Visual Deduplication via Perceptual Hashing & Hamming Distance

### 1. Concrete Problem
In Brawl Stars, games frequently cycle between the battle arena, loading screens, defeat/victory screens, and matchmaking lobbies. Multiple candidate clips may accidentally capture identical static menus or repetitive respawn scenes. The system must cluster and deduplicate near-identical visual clips.

### 2. Preferred Algorithm & Justification
**Difference Hash (dHash) with BK-Tree or Bitwise XOR Popcount:**
1. Downscale keyframe to $9 \times 8$ grayscale (72 pixels).
2. Compute relative intensity differences between adjacent horizontal pixels:
   $$b_{i,j} = \begin{cases} 1 & \text{if } P(i+1, j) > P(i, j) \\ 0 & \text{otherwise} \end{cases}$$
   This produces a compact **64-bit integer hash** per keyframe.
3. Compute Hamming distance between two frame hashes $H_1, H_2$ using native bitwise CPU instructions:
   $$\text{Distance}(H_1, H_2) = \text{popcount}(H_1 \oplus H_2)$$
4. If $\text{Distance} \le 5$, the frames are visually equivalent (menu/loading screen or identical perspective).

### 3. Complexity & Performance
- **Time Complexity:** 64-bit XOR and `popcount` executes in a single CPU instruction ($< 1\text{ nanosecond}$).
- **Space Complexity:** 8 bytes per keyframe hash. Storing 10,000 keyframe hashes requires only $80\text{ KB}$ of RAM.

---

## 7. Algorithm 6: Directed Acyclic Graph (DAG) Job Orchestration

### 1. Concrete Problem
Processing a recording requires executing multiple tasks with strict dependency order (e.g., Audio Extraction must precede Audio Analysis; Visual Analysis and Audio Analysis must both complete before Evidence Fusion can run). The system must detect cycles, compute execution order, and track parallel task execution.

```
          [ Ingest Video ]
                 │
        ┌────────┴────────┐
        ▼                 ▼
 [ Audio Extract ]  [ Proxy Transcode ]
        │                 │
        ▼                 ▼
 [ Audio Analysis]  [ Visual Analysis ]
        │                 │
        │                 ▼
        │            [ OCR Parse ]
        │                 │
        └────────┬────────┘
                 ▼
         [ Evidence Fusion ]
                 │
                 ▼
         [ Highlight Ranking ]
                 │
                 ▼
         [ EDL Generation ]
```

### 2. Preferred Algorithm: Topological Sort (Kahn's Algorithm)
1. Represent tasks as nodes $V$ and dependencies as directed edges $E = (u, v)$ indicating $u$ must finish before $v$.
2. Maintain `in_degree[v]` for all nodes.
3. Initialize queue $Q$ with all nodes having `in_degree == 0` (e.g., Ingest).
4. While $Q$ is not empty:
   - Dequeue task $u$, dispatch to worker pool.
   - Upon task $u$ completion, for each successor $v$: decrement `in_degree[v]`.
   - If `in_degree[v] == 0`, enqueue $v$ to $Q$.
5. If processed nodes $< |V|$, a dependency cycle exists (fatal configuration error).

### 3. Complexity
- **Time:** $O(|V| + |E|)$, which for $|V| \approx 10$ and $|E| \approx 12$ runs in $< 50\text{ microseconds}$.
- **Space:** $O(|V|)$ memory.
