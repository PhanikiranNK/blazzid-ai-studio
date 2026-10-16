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
