"""Synthetic gameplay fixture generators with known ground-truth event intervals.

Enables reproducible evaluation of visual activity, bursts, sustained combat,
and scene cuts without requiring external copyrighted video assets.
"""

from __future__ import annotations

import cv2
import numpy as np

from blazzid_core.contracts.time import TimeInterval


def create_solid_frame(
    width: int = 640,
    height: int = 360,
    color: tuple[int, int, int] = (40, 40, 40),
) -> np.ndarray[int, np.dtype[np.uint8]]:
    """Generates a solid color BGR frame (e.g. static UI or background)."""
    frame = np.full((height, width, 3), color, dtype=np.uint8)
    return frame


def create_action_frame(
    width: int = 640,
    height: int = 360,
    intensity: float = 0.5,
    seed: int = 42,
) -> np.ndarray[int, np.dtype[np.uint8]]:
    """Generates a high-contrast procedural combat frame with simulated projectile sparks.

    Args:
        width: Frame width.
        height: Frame height.
        intensity: Normalized action magnitude in [0.0, 1.0].
        seed: Random seed for deterministic geometric shapes.

    Returns:
        BGR uint8 image array.
    """
    rng = np.random.RandomState(seed)
    # Base terrain
    frame = np.full((height, width, 3), (35, 75, 45), dtype=np.uint8)

    num_bursts = int(round(5 + intensity * 40))
    for _ in range(num_bursts):
        cx = rng.randint(50, width - 50)
        cy = rng.randint(50, height - 50)
        r = int(rng.randint(10, 30 + int(intensity * 40)))
        # Saturated colors (yellows, purples, cyans simulating super abilities)
        color = (int(rng.randint(180, 255)), int(rng.randint(100, 255)), int(rng.randint(20, 220)))
        cv2.circle(frame, (cx, cy), r, color, -1)

    return frame


def generate_synthetic_gameplay_sequence(
    duration_seconds: float = 30.0,
    fps: float = 1.0,
    combat_intervals: list[tuple[float, float]] | None = None,
    cut_timestamps: list[float] | None = None,
    width: int = 640,
    height: int = 360,
) -> tuple[list[tuple[np.ndarray[int, np.dtype[np.uint8]], float]], list[TimeInterval]]:
    """Synthesizes a timeline of frames with explicit known ground-truth events.

    Args:
        duration_seconds: Total recording length.
        fps: Sampling rate (e.g. 1 frame per second).
        combat_intervals: List of [start, end] seconds where intense combat occurs.
        cut_timestamps: Instantaneous timestamps where scene cuts occur.
        width: Video width.
        height: Video height.

    Returns:
        Tuple of (frame_entries, ground_truth_intervals).
    """
    combats = combat_intervals or [(10.0, 16.0)]
    cuts = cut_timestamps or [22.0]

    timestamps = list(np.arange(0.0, duration_seconds, 1.0 / fps))
    entries: list[tuple[np.ndarray[int, np.dtype[np.uint8]], float]] = []

    for idx, t in enumerate(timestamps):
        # Check if in a combat interval
        is_combat = any(start <= t <= end for start, end in combats)
        is_cut = any(abs(t - cut_t) < (0.5 / fps) for cut_t in cuts)

        if is_cut:
            # Flashes white/bright screen transition
            frame = create_solid_frame(width, height, color=(240, 240, 240))
        elif is_combat:
            frame = create_action_frame(width, height, intensity=0.8, seed=idx + 100)
        else:
            # Calm gameplay with subtle drifting noise
            base_col = (int(40 + (idx % 5) * 2), 40, 40)
            frame = create_solid_frame(width, height, color=base_col)

        entries.append((frame, round(float(t), 3)))

    gt_intervals = [TimeInterval(start=start, end=end) for start, end in combats]
    return entries, gt_intervals
