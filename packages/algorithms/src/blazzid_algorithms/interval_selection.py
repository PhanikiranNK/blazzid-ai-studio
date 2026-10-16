"""Weighted Interval Scheduling with Duration Budget (Dynamic Programming).

Selects an optimal, non-overlapping subset of highlight candidates that maximizes
cumulative rank score subject to a maximum reel duration budget.

Complexity:
- Time: O(N log N + N * B) where N is the number of valid candidate intervals
  and B = floor(budget / quantum_step) is the number of discretized capacity bins.
- Space: O(N * B) for the dynamic programming table and backtracking decisions.
"""

from __future__ import annotations

import bisect
import math
import time
from collections.abc import Sequence

from blazzid_core.contracts.candidates import HighlightCandidate
from blazzid_core.contracts.selection import SelectionConstraints, SelectionResult
from blazzid_core.errors import BudgetConstraintError, IntervalError


def select_highlights_dp(
    candidates: Sequence[HighlightCandidate],
    constraints: SelectionConstraints,
) -> SelectionResult:
    """Selects an optimal non-overlapping subset of candidates within the duration budget.

    Uses a 2-dimensional Dynamic Programming algorithm:
    DP[i][b] = max(
        DP[i - 1][b],                              # Exclude candidate i
        DP[p(i)][b - cost_i] + rank_score_i       # Include candidate i (if b >= cost_i)
    )
    where p(i) is the latest compatible predecessor of interval i (found via binary search).

    Duration is quantized into integer bins: cost_i = ceil(duration_i / quantum_step).
    Using ceiling guarantees that total selected duration never exceeds the continuous budget.

    Args:
        candidates: Sequence of highlight candidates with half-open intervals [start, end).
        constraints: Selection constraints defining duration budget, clip bounds, and quantum step.

    Returns:
        SelectionResult containing selected candidates, total duration, score, and diagnostics.

    Raises:
        BudgetConstraintError: If constraints are invalid.
        IntervalError: If any candidate interval is malformed.
    """
    start_time = time.perf_counter()

    if constraints.target_duration_seconds <= 0.0:
        raise BudgetConstraintError("target_duration_seconds must be strictly positive.")

    quantum = constraints.quantum_bin_seconds
    if quantum <= 0.0 or math.isnan(quantum) or math.isinf(quantum):
        raise BudgetConstraintError("quantum_bin_seconds must be a finite positive float.")

    budget_bins = int(math.floor(constraints.target_duration_seconds / quantum))
    if budget_bins <= 0:
        return SelectionResult(
            selected_candidates=[],
            total_duration_seconds=0.0,
            total_score=0.0,
            discarded_count=len(candidates),
            quantum_step=quantum,
            solver_diagnostics={"reason": "target_duration_less_than_quantum_bin"},
        )

    # 1. Filter candidates violating duration limits or budget
    valid: list[HighlightCandidate] = []
    for c in candidates:
        dur = c.duration
        if dur <= 0.0:
            raise IntervalError(f"Candidate {c.candidate_id} has non-positive duration {dur}s")
        if dur < constraints.min_clip_duration_seconds:
            continue
        if (
            constraints.max_clip_duration_seconds is not None
            and dur > constraints.max_clip_duration_seconds
        ):
            continue
        if dur > constraints.target_duration_seconds:
            continue
        valid.append(c)

    if not valid:
        return SelectionResult(
            selected_candidates=[],
            total_duration_seconds=0.0,
            total_score=0.0,
            discarded_count=len(candidates),
            quantum_step=quantum,
            solver_diagnostics={"evaluated": 0, "reason": "no_valid_candidates_fit_constraints"},
        )

    # 2. Sort candidates by end time (deterministic tie-breaking: earlier start, then higher score, then candidate_id)
    valid.sort(key=lambda c: (c.interval.end, c.interval.start, -c.rank_score, c.candidate_id))
    n = len(valid)

    # 3. Precompute predecessor p(i) for each candidate using binary search
    end_times = [c.interval.end for c in valid]
    predecessors: list[int] = []
    for i in range(n):
        # Find latest interval j < i with end_j <= start_i (half-open compatibility)
        # bisect_right finds index where start_i could be inserted after existing end times <= start_i
        idx = bisect.bisect_right(end_times, valid[i].interval.start) - 1
        # idx must be < i because valid is sorted by end_time and end_i > start_i
        predecessors.append(idx)

    # Quantized duration costs
    costs = [int(math.ceil(c.duration / quantum)) for c in valid]

    # 4. DP Table: DP[i][b] = (best_score, -clip_count, -used_bins)
    # Using a 2D table of size (n + 1) x (budget_bins + 1)
    # Row index 0 represents the empty prefix (no intervals available)
    # Row index i + 1 corresponds to candidate i (0-indexed)
    dp: list[list[tuple[float, int, int]]] = [
        [(0.0, 0, 0) for _ in range(budget_bins + 1)] for _ in range(n + 1)
    ]
    # Decision table: True if candidate i was included, False otherwise
    take: list[list[bool]] = [[False for _ in range(budget_bins + 1)] for _ in range(n + 1)]

    for i in range(n):
        cand = valid[i]
        cost = costs[i]
        weight = cand.rank_score
        pred_row = predecessors[i] + 1  # 1-indexed for dp table (0 if pred == -1)

        for b in range(budget_bins + 1):
            # Option A: Exclude candidate i
            best_val = dp[i][b]
            chosen_take = False

            # Option B: Include candidate i (if capacity permits)
            if b >= cost:
                prev_val, prev_count, prev_cost = dp[pred_row][b - cost]
                cand_val = (
                    prev_val + weight,
                    prev_count - 1,  # Fewer clips preferred on tie
                    prev_cost - cost,  # Less duration used preferred on tie
                )
                if cand_val > best_val:
                    best_val = cand_val
                    chosen_take = True

            dp[i + 1][b] = best_val
            take[i + 1][b] = chosen_take

    # 5. Backtracking to reconstruct optimal subset
    selected_indices: list[int] = []
    curr_i = n
    curr_b = budget_bins

    while curr_i > 0 and curr_b > 0:
        if take[curr_i][curr_b]:
            idx = curr_i - 1
            selected_indices.append(idx)
            curr_b -= costs[idx]
            curr_i = predecessors[idx] + 1
        else:
            curr_i -= 1

    selected_indices.reverse()
    selected = [valid[idx] for idx in selected_indices]

    total_duration = sum(c.duration for c in selected)
    total_score = sum(c.rank_score for c in selected)
    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    return SelectionResult(
        selected_candidates=selected,
        total_duration_seconds=round(total_duration, 4),
        total_score=round(total_score, 4),
        discarded_count=len(candidates) - len(selected),
        quantum_step=quantum,
        solver_diagnostics={
            "candidates_input": len(candidates),
            "candidates_valid": n,
            "budget_bins": budget_bins,
            "solve_time_ms": round(elapsed_ms, 3),
            "theoretical_optimality": "exact_under_duration_discretization",
        },
    )


def exhaustive_interval_selection(
    candidates: Sequence[HighlightCandidate],
    constraints: SelectionConstraints,
) -> list[HighlightCandidate]:
    """Exhaustive brute-force oracle for testing and validation on small inputs (N <= 16).

    Evaluates all 2^N subsets to find the combination of mutually disjoint intervals
    that maximizes cumulative rank score while strictly satisfying the duration budget.
    """
    # Filter valid
    valid: list[HighlightCandidate] = []
    for c in candidates:
        if c.duration < constraints.min_clip_duration_seconds:
            continue
        if (
            constraints.max_clip_duration_seconds is not None
            and c.duration > constraints.max_clip_duration_seconds
        ):
            continue
        if c.duration > constraints.target_duration_seconds:
            continue
        valid.append(c)

    n = len(valid)
    if n > 18:
        raise ValueError(f"Exhaustive search only feasible for N <= 18, got {n} valid candidates.")

    best_score = -1.0
    best_subset: list[HighlightCandidate] = []

    # Iterate over all 2^n subsets
    for mask in range(1 << n):
        subset = [valid[i] for i in range(n) if (mask & (1 << i))]
        # Sort chronologically by start time
        subset.sort(key=lambda c: c.interval.start)

        # Check total duration
        total_dur = sum(c.duration for c in subset)
        if total_dur > constraints.target_duration_seconds + 1e-9:
            continue

        # Check disjointness (no overlap between consecutive sorted intervals)
        is_disjoint = True
        for i in range(len(subset) - 1):
            if subset[i].interval.end > subset[i + 1].interval.start:
                is_disjoint = False
                break

        if not is_disjoint:
            continue

        score = sum(c.rank_score for c in subset)
        if score > best_score:
            best_score = score
            best_subset = subset

    return best_subset
