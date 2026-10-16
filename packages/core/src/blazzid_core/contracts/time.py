"""Time and temporal interval domain contracts.

All timestamps are represented as media-relative seconds (float) with millisecond
precision. All temporal intervals are strictly half-open: [start, end).
"""

from __future__ import annotations

import math
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from blazzid_core.errors import IntervalError


class TimeInterval(BaseModel):
    """Immutable half-open temporal interval [start, end) in media seconds.

    Invariants:
    - start is finite and >= 0.0
    - end is finite and > start
    - duration is strictly positive (end - start > 0.0)
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    start: float = Field(
        ...,
        description="Inclusive start timestamp in seconds (>= 0.0).",
    )
    end: float = Field(
        ...,
        description="Exclusive end timestamp in seconds (> start).",
    )

    @model_validator(mode="after")
    def validate_interval_semantics(self) -> TimeInterval:
        if math.isnan(self.start) or math.isinf(self.start):
            raise IntervalError(f"Start timestamp must be a finite float, got {self.start}")
        if math.isnan(self.end) or math.isinf(self.end):
            raise IntervalError(f"End timestamp must be a finite float, got {self.end}")
        if self.start < 0.0:
            raise IntervalError(f"Start timestamp cannot be negative, got {self.start}")
        if self.end <= self.start:
            raise IntervalError(
                f"Invalid half-open interval: end ({self.end}) must be strictly greater "
                f"than start ({self.start})"
            )
        return self

    @property
    def duration(self) -> float:
        """Duration of the half-open interval in seconds."""
        return self.end - self.start

    def overlaps(self, other: TimeInterval) -> bool:
        """Determines whether two half-open intervals [s1, e1) and [s2, e2) intersect.

        Two half-open intervals overlap iff max(s1, s2) < min(e1, e2).
        Note: [0, 5) and [5, 10) do NOT overlap (touching boundaries are disjoint).
        """
        return max(self.start, other.start) < min(self.end, other.end)

    def intersection(self, other: TimeInterval) -> Optional[TimeInterval]:
        """Returns the intersecting sub-interval, or None if disjoint."""
        s = max(self.start, other.start)
        e = min(self.end, other.end)
        if s < e:
            return TimeInterval(start=s, end=e)
        return None

    def contains_timestamp(self, t: float) -> bool:
        """Returns True if timestamp t lies within half-open interval [start, end)."""
        if math.isnan(t) or math.isinf(t):
            return False
        return self.start <= t < self.end

    def contains_interval(self, other: TimeInterval) -> bool:
        """Returns True if other interval is entirely contained within this interval."""
        return self.start <= other.start and other.end <= self.end

    def overlap_duration(self, other: TimeInterval) -> float:
        """Calculates the duration of overlap in seconds (0.0 if disjoint)."""
        inter = self.intersection(other)
        return inter.duration if inter is not None else 0.0

    def intersection_over_union(self, other: TimeInterval) -> float:
        """Computes temporal Intersection over Union (Jaccard index) in [0.0, 1.0]."""
        overlap = self.overlap_duration(other)
        if overlap <= 0.0:
            return 0.0
        union = self.duration + other.duration - overlap
        return overlap / union if union > 0.0 else 0.0
