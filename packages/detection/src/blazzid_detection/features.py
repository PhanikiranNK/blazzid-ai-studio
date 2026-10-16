"""Timestamp-aware visual feature extraction from sparse video frames."""

from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

from blazzid_detection.models import FrameFeatureRecord


def compute_single_frame_features(
    image: np.ndarray[Any, Any],
    frame_index: int,
    timestamp_seconds: float,
    file_path: Optional[Path] = None,
    previous_gray: Optional[np.ndarray[Any, Any]] = None,
    previous_hist: Optional[np.ndarray[Any, Any]] = None,
) -> tuple[FrameFeatureRecord, np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    """Extracts normalized visual metrics from a BGR image array.

    Args:
        image: BGR uint8 NumPy image array.
        frame_index: Sequential frame index.
        timestamp_seconds: Source-relative presentation timestamp.
        file_path: Optional path to the image file on disk.
        previous_gray: Optional grayscale array of the immediately preceding frame.
        previous_hist: Optional normalized 16-bin histogram of the prior frame.

    Returns:
        Tuple of (FrameFeatureRecord, current_gray, current_hist).
    """
    h, w = int(image.shape[0]), int(image.shape[1])
    if h == 0 or w == 0:
        record = FrameFeatureRecord(
            frame_index=frame_index,
            timestamp_seconds=timestamp_seconds,
            file_path=file_path,
            width=max(1, w),
            height=max(1, h),
            is_valid=False,
            error_message="Empty frame dimensions.",
        )
        dummy_gray = np.zeros((1, 1), dtype=np.uint8)
        dummy_hist = np.zeros((16,), dtype=np.float32)
        return record, dummy_gray, dummy_hist

    # 1. Grayscale conversion
    gray: Any
    if len(image.shape) == 3 and image.shape[2] == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    elif len(image.shape) == 2:
        gray = image
    else:
        gray = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)

    # 2. Luminance statistics
    mean_lum = float(np.mean(gray))
    std_lum = float(np.std(gray))

    # 3. 16-bin normalized luminance histogram
    hist_raw = cv2.calcHist([gray], [0], None, [16], [0, 256])
    hist: np.ndarray[Any, Any] = (
        np.asarray(cv2.normalize(hist_raw, None, alpha=1.0, norm_type=cv2.NORM_L1))
        .flatten()
        .astype(np.float32)
    )  # sums to 1.0
    hist_list = [float(val) for val in hist]

    # 4. Temporal frame difference & histogram distance
    frame_diff = 0.0
    hist_dist = 0.0

    if previous_gray is not None and previous_hist is not None:
        # Match dimensions if resolution changed dynamically
        if previous_gray.shape != gray.shape:
            prev_aligned: np.ndarray[Any, Any] = np.asarray(
                cv2.resize(previous_gray, (w, h), interpolation=cv2.INTER_NEAREST)
            )
        else:
            prev_aligned = previous_gray

        diff_abs = np.abs(gray.astype(np.float32) - prev_aligned.astype(np.float32))
        frame_diff = float(np.mean(diff_abs) / 255.0)

        # Bhattacharyya distance between probability distributions [0.0, 1.0]
        # (0.0 = identical, 1.0 = completely disjoint)
        dist_bhatt = float(cv2.compareHist(hist, previous_hist, cv2.HISTCMP_BHATTACHARYYA))
        hist_dist = max(0.0, min(1.0, dist_bhatt if math.isfinite(dist_bhatt) else 0.0))

    # 5. Spatial edge gradient density via Sobel operator
    # Measures the proportion of high-frequency texture / edge energy
    sobel_x = cv2.Sobel(gray, cv2.CV_16S, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_16S, 0, 1, ksize=3)
    abs_sobel = cv2.convertScaleAbs(
        cv2.addWeighted(cv2.convertScaleAbs(sobel_x), 0.5, cv2.convertScaleAbs(sobel_y), 0.5, 0)
    )
    edge_density = float(np.mean(abs_sobel) / 255.0)

    record = FrameFeatureRecord(
        frame_index=frame_index,
        timestamp_seconds=timestamp_seconds,
        file_path=file_path,
        width=w,
        height=h,
        mean_luminance=round(mean_lum, 2),
        std_luminance=round(std_lum, 2),
        histogram=[round(x, 4) for x in hist_list],
        frame_difference=round(min(1.0, max(0.0, frame_diff)), 4),
        histogram_distance=round(hist_dist, 4),
        edge_density=round(min(1.0, max(0.0, edge_density)), 4),
        is_valid=True,
    )
    return record, gray, hist


def extract_features_from_path(
    file_path: Path,
    frame_index: int,
    timestamp_seconds: float,
    previous_gray: Optional[np.ndarray[Any, Any]] = None,
    previous_hist: Optional[np.ndarray[Any, Any]] = None,
) -> tuple[FrameFeatureRecord, Optional[np.ndarray[Any, Any]], Optional[np.ndarray[Any, Any]]]:
    """Decodes a single frame from disk and extracts visual features.

    If file is missing or corrupted, returns an invalid FrameFeatureRecord without raising.
    """
    if not file_path.is_file():
        record = FrameFeatureRecord(
            frame_index=frame_index,
            timestamp_seconds=timestamp_seconds,
            file_path=file_path,
            width=1,
            height=1,
            is_valid=False,
            error_message=f"Frame file not found: '{file_path.name}'",
        )
        return record, previous_gray, previous_hist

    try:
        img = cv2.imread(str(file_path))
    except Exception as err:
        record = FrameFeatureRecord(
            frame_index=frame_index,
            timestamp_seconds=timestamp_seconds,
            file_path=file_path,
            width=1,
            height=1,
            is_valid=False,
            error_message=f"Exception decoding frame: {err}",
        )
        return record, previous_gray, previous_hist

    if img is None:
        record = FrameFeatureRecord(
            frame_index=frame_index,
            timestamp_seconds=timestamp_seconds,
            file_path=file_path,
            width=1,
            height=1,
            is_valid=False,
            error_message=f"OpenCV failed to decode image '{file_path.name}'",
        )
        return record, previous_gray, previous_hist

    rec, gray, hist = compute_single_frame_features(
        img,
        frame_index=frame_index,
        timestamp_seconds=timestamp_seconds,
        file_path=file_path,
        previous_gray=previous_gray,
        previous_hist=previous_hist,
    )
    return rec, gray, hist


def extract_sequence_features(
    frame_entries: Sequence[tuple[Path | np.ndarray[Any, Any], float]],
) -> list[FrameFeatureRecord]:
    """Incrementally extracts visual features across an ordered sequence of frames.

    Args:
        frame_entries: List of (image_path_or_array, timestamp_seconds) tuples.

    Returns:
        List of FrameFeatureRecord objects in chronological order.
    """
    records: list[FrameFeatureRecord] = []
    prev_gray: Optional[np.ndarray[Any, Any]] = None
    prev_hist: Optional[np.ndarray[Any, Any]] = None

    for idx, (source, ts) in enumerate(frame_entries):
        if isinstance(source, Path):
            rec, gray, hist = extract_features_from_path(
                file_path=source,
                frame_index=idx,
                timestamp_seconds=ts,
                previous_gray=prev_gray,
                previous_hist=prev_hist,
            )
            if rec.is_valid:
                prev_gray = gray
                prev_hist = hist
            records.append(rec)
        elif isinstance(source, np.ndarray):
            rec, gray, hist = compute_single_frame_features(
                image=source,
                frame_index=idx,
                timestamp_seconds=ts,
                previous_gray=prev_gray,
                previous_hist=prev_hist,
            )
            if rec.is_valid:
                prev_gray = gray
                prev_hist = hist
            records.append(rec)
        else:
            records.append(
                FrameFeatureRecord(
                    frame_index=idx,
                    timestamp_seconds=ts,
                    width=1,
                    height=1,
                    is_valid=False,
                    error_message=f"Unsupported frame source type: {type(source)}",
                )
            )

    return records
