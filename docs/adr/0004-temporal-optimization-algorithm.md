# ADR 0004: Temporal Optimization Algorithm (Weighted Interval Scheduling)

## Status
Accepted

## Date
2026-10-16

## Context
Once gameplay events are detected, the system must assemble an optimal highlight reel of a user-specified total duration (e.g., exactly 180 seconds for a 3-minute montage).

Candidate clips vary in length (e.g., 6 seconds to 20 seconds), utility score, and overlap. A candidate "Double Kill" interval $[120\text{s}, 132\text{s})$ may overlap with a subsequent "Team Wipe" interval $[128\text{s}, 145\text{s})$.

We evaluated two algorithmic paradigms:
- **Alternative A: Greedy Interval Selection.** Pick the highest-scoring candidate, remove all overlapping candidates, and repeat until the duration budget is filled.
  - *Defect:* Greedy selection is provably sub-optimal when intervals have heterogeneous weights and durations. A moderately high-scoring 25-second clip can block two compact 8-second clips whose combined score and narrative pacing are significantly superior.
- **Alternative B: Mixed Integer Linear Programming (MILP).** Continuous optimization via branch-and-bound.
  - *Defect:* High computational overhead, requires external solver libraries (C/C++ dependencies), non-deterministic execution times.
- **Alternative C: Dynamic Programming (Weighted Interval Scheduling with 0/1 Knapsack Discretization).** Discretize time into quantum bins (e.g., $\Delta t = 0.5\text{s}$) and compute exact optimal subset using a 2D dynamic programming recurrence.

## Decision
We select **Alternative C: Two-Dimensional Dynamic Programming (Weighted Interval Scheduling with Knapsack Capacity)**:

1. **End-Time Sorting:** Sort all candidate intervals by end time in $O(N \log N)$.
2. **Binary Search Predecessors:** Compute non-overlapping predecessor indices $p(i)$ in $O(N \log N)$.
3. **Time Quantum Discretization:** Discretize the reel duration budget into $B = \lfloor D_{\text{target}} / 0.5\text{s} \rfloor$ bins.
4. **Optimal Recurrence:**
   $$DP[i][b] = \max(DP[i - 1][b], \, DP[p(i)][b - d_i] + w_i)$$
5. **Backtracking:** Trace back to reconstruct the exact optimal, non-overlapping subset of clips.

## Consequences

### Positive
- **Guaranteed Global Optimality:** Finds the provably maximum-score non-overlapping combination of highlights within the time budget.
- **Ultra-Fast Deterministic Execution:** For $N = 100$ candidates and $B = 360$ bins ($180\text{s}$ at $0.5\text{s}$ resolution), the DP matrix has only 36,000 entries. Computes in $< 2\text{ms}$ in pure Python without external solver dependencies.
- **Strict Invariants:** Mathematical guarantee of zero pairwise clip overlaps and total duration $\le D_{\text{target}}$.

### Negative / Trade-offs
- Discretization to 0.5-second quanta introduces a maximum potential rounding slack of 0.5 seconds on the reel duration, which is imperceptible in video editing.
