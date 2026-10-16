"""Metadata inspection and stream characterization using ffprobe."""

from __future__ import annotations

import contextlib
import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from blazzid_media.errors import MissingVideoStreamError, ProbeError
from blazzid_media.models import (
    AudioStreamMetadata,
    ContainerMetadata,
    FrameRateMode,
    MediaInspectionResult,
    VideoStreamMetadata,
)
from blazzid_media.validation import validate_input_media_file


def _parse_fraction(frac_str: Optional[str]) -> Optional[float]:
    """Safely converts a rational string like '30/1' or '30000/1001' into a float."""
    if not frac_str or "/" not in frac_str:
        return None
    try:
        num, den = frac_str.split("/", 1)
        n = float(num)
        d = float(den)
        if d == 0.0 or n == 0.0:
            return None
        val = n / d
        return val if math.isfinite(val) and val > 0.0 else None
    except (ValueError, ZeroDivisionError):
        return None


def _find_ffprobe_executable() -> str:
    """Locates ffprobe on system PATH or raises ProbeError."""
    exe = shutil.which("ffprobe")
    if exe is None:
        raise ProbeError(
            "ffprobe executable not found on PATH. Install FFmpeg 7.x/8.x to enable media inspection."
        )
    return exe


def _classify_frame_rate_mode(
    file_path: Path,
    avg_fps: Optional[float],
    r_fps: Optional[float],
    video_stream_idx: int,
    timeout_seconds: int = 15,
) -> FrameRateMode:
    """Conservatively classifies frame rate pacing as CFR, VFR, or UNKNOWN.

    Inspects a bounded initial window of presentation timestamps (up to 3 seconds)
    rather than relying solely on container header ratios.
    """
    ffprobe_exe = _find_ffprobe_executable()

    cmd = [
        ffprobe_exe,
        "-v",
        "error",
        "-read_intervals",
        "%+3",  # Read only the first 3 seconds
        "-select_streams",
        f"v:{video_stream_idx}",
        "-show_entries",
        "packet=pts_time,duration_time",
        "-print_format",
        "json",
        str(file_path),
    ]

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_seconds, check=True
        )
        data = json.loads(proc.stdout)
        packets = data.get("packets", [])
    except Exception:
        # Fallback to header ratio comparison if packet probing fails
        if avg_fps is not None and r_fps is not None:
            if abs(avg_fps - r_fps) < 0.05:
                return FrameRateMode.CFR
            return FrameRateMode.VFR
        return FrameRateMode.UNKNOWN

    pts_times: list[float] = []
    for pkt in packets:
        t_str = pkt.get("pts_time")
        if t_str is not None:
            try:
                t = float(t_str)
                if math.isfinite(t):
                    pts_times.append(t)
            except ValueError:
                continue

    pts_times.sort()

    if len(pts_times) < 5:
        # Insufficient packets in window
        if avg_fps is not None and r_fps is not None:
            return FrameRateMode.CFR if abs(avg_fps - r_fps) < 0.05 else FrameRateMode.VFR
        return FrameRateMode.UNKNOWN

    deltas = [pts_times[i + 1] - pts_times[i] for i in range(len(pts_times) - 1)]
    # Filter non-positive deltas if packets were out of order
    valid_deltas = [d for d in deltas if d > 0.0]
    if len(valid_deltas) < 4:
        return FrameRateMode.UNKNOWN

    max_delta = max(valid_deltas)
    min_delta = min(valid_deltas)

    # If packet delta spread is within 2.5 milliseconds, pacing is strictly constant
    if (max_delta - min_delta) <= 0.0025:
        return FrameRateMode.CFR

    # If deltas vary noticeably, classify as VFR
    if (max_delta - min_delta) > 0.008:
        return FrameRateMode.VFR

    return FrameRateMode.UNKNOWN


def probe_media(
    file_path: Path | str,
    *,
    timeout_seconds: int = 30,
    check_file_exists: bool = True,
) -> MediaInspectionResult:
    """Inspects a media file using ffprobe and produces structured, validated metadata.

    Args:
        file_path: Path to the target media file.
        timeout_seconds: Subprocess execution deadline in seconds.
        check_file_exists: Whether to run pre-probe filesystem validation.

    Returns:
        MediaInspectionResult containing container, video, and audio metadata.

    Raises:
        MediaInputError: If file is missing or unreadable.
        MissingVideoStreamError: If container has no video stream.
        ProbeError: If ffprobe execution, JSON parsing, or validation fails.
    """
    if check_file_exists:
        resolved_path = validate_input_media_file(file_path)
    else:
        resolved_path = Path(file_path).resolve()

    ffprobe_exe = _find_ffprobe_executable()

    cmd = [
        ffprobe_exe,
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(resolved_path),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=True,
        )
    except subprocess.TimeoutExpired as err:
        raise ProbeError(
            f"ffprobe timed out after {timeout_seconds}s inspecting '{resolved_path.name}'"
        ) from err
    except subprocess.CalledProcessError as err:
        stderr_msg = err.stderr.strip() if err.stderr else "Unknown ffprobe error"
        raise ProbeError(f"ffprobe failed on '{resolved_path.name}': {stderr_msg}") from err

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as err:
        raise ProbeError(f"Failed to parse ffprobe JSON output for '{resolved_path.name}'") from err

    raw_format = payload.get("format", {})
    raw_streams = payload.get("streams", [])

    if not raw_format:
        raise ProbeError(f"Missing format block in ffprobe output for '{resolved_path.name}'")

    # 1. Parse Container Metadata
    duration_str = raw_format.get("duration")
    if duration_str is None:
        raise ProbeError(f"Unable to determine duration for '{resolved_path.name}'")
    try:
        container_duration = float(duration_str)
    except ValueError as err:
        raise ProbeError(f"Invalid container duration '{duration_str}'") from err

    container_size = int(raw_format.get("size", resolved_path.stat().st_size))
    raw_bitrate = raw_format.get("bit_rate")
    bit_rate = int(raw_bitrate) if raw_bitrate is not None and str(raw_bitrate).isdigit() else None

    container_meta = ContainerMetadata(
        format_name=str(raw_format.get("format_name", "unknown")),
        format_long_name=raw_format.get("format_long_name"),
        duration_seconds=container_duration,
        size_bytes=container_size,
        bit_rate=bit_rate,
        tags={k: str(v) for k, v in raw_format.get("tags", {}).items()},
    )

    # 2. Parse Video Stream
    video_streams = [s for s in raw_streams if s.get("codec_type") == "video"]
    if not video_streams:
        raise MissingVideoStreamError(f"No video stream found in container '{resolved_path.name}'")

    v = video_streams[0]
    v_idx = int(v.get("index", 0))
    v_width = int(v.get("width", 0))
    v_height = int(v.get("height", 0))
    if v_width <= 0 or v_height <= 0:
        raise ProbeError(
            f"Invalid video dimensions {v_width}x{v_height} for '{resolved_path.name}'"
        )

    avg_fps = _parse_fraction(v.get("avg_frame_rate"))
    r_fps = _parse_fraction(v.get("r_frame_rate"))

    v_dur = float(v["duration"]) if "duration" in v and v["duration"] is not None else None
    v_start = float(v["start_time"]) if "start_time" in v and v["start_time"] is not None else None
    v_frames = int(v["nb_frames"]) if "nb_frames" in v and str(v["nb_frames"]).isdigit() else None

    # Detect rotation from side data or tags
    rotation: Optional[int] = None
    for side in v.get("side_data_list", []):
        if "rotation" in side:
            with contextlib.suppress(ValueError, TypeError):
                rotation = int(side["rotation"])
                break
    if rotation is None and "tags" in v and "rotate" in v["tags"]:
        with contextlib.suppress(ValueError, TypeError):
            rotation = int(v["tags"]["rotate"])

    frame_rate_mode = _classify_frame_rate_mode(
        resolved_path,
        avg_fps=avg_fps,
        r_fps=r_fps,
        video_stream_idx=v_idx,
    )

    video_meta = VideoStreamMetadata(
        index=v_idx,
        codec_name=str(v.get("codec_name", "unknown")),
        profile=v.get("profile"),
        width=v_width,
        height=v_height,
        pixel_format=str(v.get("pix_fmt", "unknown")),
        avg_frame_rate=avg_fps,
        r_frame_rate=r_fps,
        time_base=v.get("time_base"),
        frame_count=v_frames,
        duration_seconds=v_dur,
        start_time_seconds=v_start,
        sample_aspect_ratio=v.get("sample_aspect_ratio"),
        display_aspect_ratio=v.get("display_aspect_ratio"),
        rotation=rotation,
        frame_rate_mode=frame_rate_mode,
    )

    # 3. Parse Audio Stream (Optional)
    audio_streams = [s for s in raw_streams if s.get("codec_type") == "audio"]
    audio_meta: Optional[AudioStreamMetadata] = None

    if audio_streams:
        a = audio_streams[0]
        a_dur = float(a["duration"]) if "duration" in a and a["duration"] is not None else None
        a_start = (
            float(a["start_time"]) if "start_time" in a and a["start_time"] is not None else None
        )
        audio_meta = AudioStreamMetadata(
            index=int(a.get("index", 1)),
            codec_name=str(a.get("codec_name", "unknown")),
            sample_rate=int(a.get("sample_rate", 44100)),
            channels=int(a.get("channels", 2)),
            channel_layout=a.get("channel_layout"),
            duration_seconds=a_dur,
            start_time_seconds=a_start,
        )

    return MediaInspectionResult(
        source_path=resolved_path,
        container=container_meta,
        video=video_meta,
        audio=audio_meta,
        has_audio=audio_meta is not None,
    )
