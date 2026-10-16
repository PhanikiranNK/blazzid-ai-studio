"""Synthetic media fixture generator using FFmpeg lavfi test sources.

Generates small (1s to 5s) deterministic video and audio fixtures for media pipeline testing.
Never requires external downloads or copyrighted footage.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional


def is_ffmpeg_available() -> bool:
    """Checks whether ffmpeg executable is available on PATH."""
    return shutil.which("ffmpeg") is not None


def generate_synthetic_video(
    duration_seconds: float = 3.0,
    width: int = 640,
    height: int = 360,
    fps: int = 30,
    has_audio: bool = True,
    output_path: Optional[Path] = None,
) -> Path:
    """Generates a synthetic MP4 video file using lavfi testsrc and sine audio.

    Args:
        duration_seconds: Length of generated fixture in seconds.
        width: Video frame width.
        height: Video frame height.
        fps: Video frame rate.
        has_audio: Whether to synthesize a 1000Hz test audio tone.
        output_path: Destination file path. If None, a tempfile is created.

    Returns:
        Path to the generated MP4 file.

    Raises:
        RuntimeError: If FFmpeg fails or is not available.
    """
    if not is_ffmpeg_available():
        raise RuntimeError("FFmpeg is not installed or not available on PATH.")

    target = output_path or Path(tempfile.mktemp(suffix=".mp4"))

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=duration={duration_seconds}:size={width}x{height}:rate={fps}",
    ]
    if has_audio:
        cmd += [
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=1000:duration={duration_seconds}",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
        ]
    cmd += [
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(target),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed to generate fixture: {result.stderr}")

    return target


def generate_synthetic_audio(
    duration_seconds: float = 3.0,
    sample_rate: int = 16000,
    frequency: int = 440,
    output_path: Optional[Path] = None,
) -> Path:
    """Generates a synthetic mono WAV audio file using a sine wave.

    Args:
        duration_seconds: Length in seconds.
        sample_rate: PCM sample rate (Hz).
        frequency: Audio tone frequency (Hz).
        output_path: Destination file path. If None, a tempfile is created.

    Returns:
        Path to the generated WAV file.
    """
    if not is_ffmpeg_available():
        raise RuntimeError("FFmpeg is not installed or not available on PATH.")

    target = output_path or Path(tempfile.mktemp(suffix=".wav"))

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency={frequency}:sample_rate={sample_rate}:duration={duration_seconds}",
        "-c:a",
        "pcm_s16le",
        "-ac",
        "1",
        str(target),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed to generate audio fixture: {result.stderr}")

    return target


def generate_portrait_video(
    duration_seconds: float = 2.0,
    width: int = 360,
    height: int = 640,
    fps: int = 30,
    has_audio: bool = True,
    output_path: Optional[Path] = None,
) -> Path:
    """Generates a synthetic portrait (vertical) video fixture."""
    return generate_synthetic_video(
        duration_seconds=duration_seconds,
        width=width,
        height=height,
        fps=fps,
        has_audio=has_audio,
        output_path=output_path,
    )


def generate_vfr_video(
    duration_seconds: float = 3.0,
    width: int = 320,
    height: int = 240,
    output_path: Optional[Path] = None,
) -> Path:
    """Generates a synthetic video with intentionally variable frame timestamps."""
    if not is_ffmpeg_available():
        raise RuntimeError("FFmpeg is not installed or not available on PATH.")

    target = output_path or Path(tempfile.mktemp(suffix=".mp4"))

    # Select filter drops non-matching frames, creating real variable frame deltas
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=duration={duration_seconds}:size={width}x{height}:rate=30",
        "-vf",
        "select='not(mod(n\\,3))+not(mod(n\\,5))'",
        "-fps_mode",
        "vfr",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(target),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed to generate VFR fixture: {result.stderr}")

    return target


def generate_corrupt_media(output_path: Optional[Path] = None) -> Path:
    """Generates a corrupted, non-decodable media fixture larger than min file size."""
    target = output_path or Path(tempfile.mktemp(suffix=".mp4"))
    # Write invalid MP4 header followed by random garbage (2048 bytes)
    header = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00"
    garbage = b"corrupted_media_payload_garbage_data_" * 60
    target.write_bytes(header + garbage)
    return target
