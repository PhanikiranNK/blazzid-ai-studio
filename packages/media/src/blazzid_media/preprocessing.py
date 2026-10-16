"""Deterministic preprocessing: analysis proxy transcode and 16kHz mono audio extraction."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from blazzid_media.errors import AudioExtractionError, PreprocessingError
from blazzid_media.models import (
    MediaInspectionResult,
    PreprocessingConfig,
    PreprocessingResult,
)
from blazzid_media.probe import probe_media
from blazzid_media.validation import ensure_safe_directory


def _find_ffmpeg_executable() -> str:
    """Locates ffmpeg on system PATH or raises PreprocessingError."""
    exe = shutil.which("ffmpeg")
    if exe is None:
        raise PreprocessingError(
            "ffmpeg executable not found on PATH. Install FFmpeg 7.x/8.x to enable media processing."
        )
    return exe


def extract_audio_wav(
    source_path: Path,
    output_wav_path: Path,
    *,
    sample_rate: int = 16000,
    channels: int = 1,
    timeout_seconds: int = 180,
) -> Path:
    """Extracts a normalized 16kHz mono PCM WAV stream from the source media.

    Args:
        source_path: Path to source media file.
        output_wav_path: Destination path for extracted .wav file.
        sample_rate: PCM sampling frequency (Hz). Default 16,000.
        channels: Audio channels (1 = mono). Default 1.
        timeout_seconds: Subprocess execution deadline.

    Returns:
        Path to the verified extracted WAV file.

    Raises:
        PreprocessingError: If extraction fails or times out.
    """
    ffmpeg_exe = _find_ffmpeg_executable()
    ensure_safe_directory(output_wav_path.parent)

    cmd = [
        ffmpeg_exe,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source_path),
        "-vn",  # disable video
        "-acodec",
        "pcm_s16le",
        "-ar",
        str(sample_rate),
        "-ac",
        str(channels),
        str(output_wav_path),
    ]

    try:
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=True,
        )
    except subprocess.TimeoutExpired as err:
        if output_wav_path.exists():
            output_wav_path.unlink(missing_ok=True)
        raise AudioExtractionError(f"Audio extraction timed out after {timeout_seconds}s") from err
    except subprocess.CalledProcessError as err:
        if output_wav_path.exists():
            output_wav_path.unlink(missing_ok=True)
        raise AudioExtractionError(f"Audio extraction failed: {err.stderr.strip()}") from err

    # Verify that file was created and is larger than standard 44-byte WAV header
    if not output_wav_path.exists() or output_wav_path.stat().st_size <= 44:
        if output_wav_path.exists():
            output_wav_path.unlink(missing_ok=True)
        raise AudioExtractionError(
            f"Extracted audio file is missing or contains no samples: {output_wav_path.name}"
        )

    return output_wav_path


def generate_analysis_proxy(
    source_path: Path,
    output_proxy_path: Path,
    inspection: MediaInspectionResult,
    config: Optional[PreprocessingConfig] = None,
) -> tuple[Path, MediaInspectionResult]:
    """Generates a standardized 720p 30fps H.264 analysis proxy video.

    Scaling Policy:
    - Downscales source video to fit within config bounds (e.g. 1280x720) while preserving aspect ratio.
    - Does not upscale sources smaller than target resolution ('min(w, iw)').
    - Enforces even dimensions required by H.264 codecs ('trunc(iw/2)*2').
    - Normalizes frame pacing to constant 30 fps for deterministic seeking.

    Args:
        source_path: Path to source media file.
        output_proxy_path: Destination path for .mp4 proxy.
        inspection: Pre-computed ffprobe inspection of the source file.
        config: Preprocessing configuration overrides.

    Returns:
        Tuple of (proxy_path, verified_proxy_inspection).

    Raises:
        PreprocessingError: If transcode fails, times out, or output cannot be probed.
    """
    cfg = config or PreprocessingConfig()
    ffmpeg_exe = _find_ffmpeg_executable()
    ensure_safe_directory(output_proxy_path.parent)

    # Scale filter preserving aspect ratio without upscaling, ensuring even dimensions:
    # scale='min(1280,iw)':'-2' or proportional clamp
    w = cfg.proxy_width
    h = cfg.proxy_height
    scale_filter = (
        f"scale='min({w},iw)':'min({h},ih)':force_original_aspect_ratio=decrease,"
        f"scale='trunc(iw/2)*2':'trunc(ih/2)*2'"
    )

    cmd = [
        ffmpeg_exe,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source_path),
        "-vf",
        scale_filter,
        "-r",
        str(cfg.proxy_fps),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "fast",
        "-crf",
        str(cfg.proxy_crf),
    ]

    # Include audio in proxy if source has audio, otherwise mute
    if inspection.has_audio:
        cmd += ["-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2"]
    else:
        cmd += ["-an"]

    cmd.append(str(output_proxy_path))

    try:
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=cfg.timeout_seconds,
            check=True,
        )
    except subprocess.TimeoutExpired as err:
        if output_proxy_path.exists():
            output_proxy_path.unlink(missing_ok=True)
        raise PreprocessingError(f"Proxy transcode timed out after {cfg.timeout_seconds}s") from err
    except subprocess.CalledProcessError as err:
        if output_proxy_path.exists():
            output_proxy_path.unlink(missing_ok=True)
        raise PreprocessingError(f"Proxy transcode failed: {err.stderr.strip()}") from err

    # Verify generated proxy by probing it
    if not output_proxy_path.exists() or output_proxy_path.stat().st_size == 0:
        if output_proxy_path.exists():
            output_proxy_path.unlink(missing_ok=True)
        raise PreprocessingError(f"Generated proxy is missing or empty: {output_proxy_path.name}")

    try:
        proxy_inspection = probe_media(output_proxy_path, timeout_seconds=15)
    except Exception as err:
        if output_proxy_path.exists():
            output_proxy_path.unlink(missing_ok=True)
        raise PreprocessingError(f"Generated proxy failed metadata verification: {err}") from err

    return output_proxy_path, proxy_inspection


def preprocess_media(
    source_path: Path | str,
    work_dir: Path | str,
    *,
    config: Optional[PreprocessingConfig] = None,
    inspection: Optional[MediaInspectionResult] = None,
) -> PreprocessingResult:
    """Orchestrates proxy generation and audio extraction for a validated media file.

    Args:
        source_path: Target video file path.
        work_dir: Directory where proxy.mp4 and audio.wav will be generated.
        config: Preprocessing operational configuration.
        inspection: Optional existing inspection; if None, runs probe_media.

    Returns:
        PreprocessingResult containing paths and verified metadata.
    """
    src = Path(source_path).resolve()
    w_dir = ensure_safe_directory(work_dir)
    cfg = config or PreprocessingConfig()

    ins = inspection or probe_media(src)

    proxy_out = w_dir / "proxy.mp4"
    audio_out = w_dir / "audio.wav"

    # 1. Generate Proxy Video
    proxy_path, proxy_meta = generate_analysis_proxy(src, proxy_out, ins, cfg)

    # 2. Extract Audio if stream is present
    audio_path: Optional[Path] = None
    if ins.has_audio:
        audio_path = extract_audio_wav(
            src,
            audio_out,
            sample_rate=cfg.audio_sample_rate,
            channels=cfg.audio_channels,
            timeout_seconds=cfg.timeout_seconds,
        )

    return PreprocessingResult(
        proxy_path=proxy_path,
        proxy_metadata=proxy_meta,
        audio_path=audio_path,
        has_audio=ins.has_audio,
        duration_seconds=proxy_meta.container.duration_seconds,
    )
