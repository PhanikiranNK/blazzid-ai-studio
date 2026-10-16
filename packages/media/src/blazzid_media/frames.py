"""Timestamp-aware sparse frame extraction using OpenCV."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from blazzid_media.errors import FrameExtractionError
from blazzid_media.models import ExtractedFrame, FrameExtractionResult
from blazzid_media.validation import ensure_safe_directory


def extract_sparse_frames(
    video_path: Path | str,
    output_dir: Path | str,
    *,
    target_interval_seconds: float = 1.0,
    max_frames: Optional[int] = None,
    image_format: str = "jpg",
    jpeg_quality: int = 85,
) -> FrameExtractionResult:
    """Extracts timestamp-aware video frames at regular temporal intervals.

    Reads presentation timestamps directly from the container via OpenCV (CAP_PROP_POS_MSEC)
    and saves each sampled frame to disk immediately, avoiding unbounded memory growth.

    Filename format:
        frame_{index:06d}_{timestamp_ms:08d}.jpg

    Args:
        video_path: Path to input video file (source or proxy).
        output_dir: Destination folder for extracted frame images.
        target_interval_seconds: Sampling step in seconds (default 1.0s).
        max_frames: Optional upper bound on extracted frames count.
        image_format: File format extension ('jpg' or 'png').
        jpeg_quality: Compression quality (1-100) if format is jpg.

    Returns:
        FrameExtractionResult containing metadata for all extracted frames.

    Raises:
        FrameExtractionError: If video cannot be opened or decoded.
    """
    if (
        target_interval_seconds <= 0.0
        or math.isnan(target_interval_seconds)
        or math.isinf(target_interval_seconds)
    ):
        raise FrameExtractionError(
            f"target_interval_seconds must be a positive finite float, got {target_interval_seconds}"
        )

    v_path = Path(video_path).resolve()
    out_dir = ensure_safe_directory(output_dir)

    cap = cv2.VideoCapture(str(v_path))
    if not cap.isOpened():
        raise FrameExtractionError(f"OpenCV failed to open video file: '{v_path.name}'")

    extracted: list[ExtractedFrame] = []
    sample_index = 0
    last_saved_pts_sec = -1.0

    encode_params: list[int] = []
    if image_format.lower() in ("jpg", "jpeg"):
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), max(1, min(100, jpeg_quality))]

    try:
        # Determine total duration or approximate frame count if available
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        approx_duration = (total_frames / fps) if fps and fps > 0 and total_frames > 0 else 36000.0

        current_target_sec = 0.0

        while current_target_sec <= approx_duration:
            if max_frames is not None and sample_index >= max_frames:
                break

            target_msec = current_target_sec * 1000.0
            cap.set(cv2.CAP_PROP_POS_MSEC, target_msec)

            ret, frame = cap.read()
            if not ret or frame is None:
                # Reached end of stream
                break

            actual_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
            actual_sec = actual_msec / 1000.0 if actual_msec >= 0.0 else current_target_sec

            # Avoid storing exact duplicate timestamps if seeking didn't advance
            if actual_sec <= last_saved_pts_sec:
                # Step forward sequentially until timestamp advances or stream ends
                while ret and actual_sec <= last_saved_pts_sec:
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        break
                    actual_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
                    actual_sec = (
                        actual_msec / 1000.0
                        if actual_msec >= 0.0
                        else actual_sec + (1.0 / (fps or 30.0))
                    )

            if not ret or frame is None:
                break

            frame_arr = np.asarray(frame)
            h, w = int(frame_arr.shape[0]), int(frame_arr.shape[1])
            ts_ms = int(round(actual_sec * 1000.0))
            frame_filename = f"frame_{sample_index:06d}_{ts_ms:08d}.{image_format}"
            frame_path = out_dir / frame_filename

            success = cv2.imwrite(str(frame_path), frame, encode_params)
            if not success:
                raise FrameExtractionError(
                    f"Failed to write extracted frame to '{frame_path.name}'"
                )

            extracted.append(
                ExtractedFrame(
                    frame_index=sample_index,
                    timestamp_seconds=round(actual_sec, 4),
                    file_path=frame_path,
                    width=w,
                    height=h,
                )
            )

            last_saved_pts_sec = actual_sec
            sample_index += 1
            current_target_sec += target_interval_seconds

    finally:
        cap.release()

    return FrameExtractionResult(
        frames=extracted,
        target_interval_seconds=target_interval_seconds,
        total_frames_extracted=len(extracted),
    )
