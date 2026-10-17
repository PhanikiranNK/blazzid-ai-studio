"""Deterministic clip extraction and montage assembly using FFmpeg."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from blazzid_assembly.config import AssemblyConfig
from blazzid_assembly.errors import AssemblyRenderError
from blazzid_assembly.models import EditPlan
from blazzid_media.validation import ensure_safe_directory


def _find_ffmpeg_executable() -> str:
    """Locates the ffmpeg executable on system PATH."""
    exe = shutil.which("ffmpeg")
    if exe is None:
        raise AssemblyRenderError(
            "ffmpeg executable not found on PATH. Install FFmpeg to enable video rendering."
        )
    return exe


def render_montage(
    source_path: Path,
    edit_plan: EditPlan,
    output_path: Path,
    config: AssemblyConfig,
    *,
    source_has_audio: bool = True,
    temp_dir: Optional[Path] = None,
) -> Path:
    """Extracts planned highlight clips and concatenates them into a finished MP4 montage.

    Rendering pipeline:
    1. Validates that the edit plan contains at least one clip.
    2. Extracts each planned interval with frame-accurate seeking (-ss and -to).
    3. Normalizes each clip to the target profile canvas (resolution, fps, pixel format).
    4. Handles aspect ratio differences deterministically using padding (letterbox/pillarbox).
    5. Normalizes audio to stereo AAC 44.1kHz (or omits audio if source is video-only).
    6. Concatenates normalized clips using the FFmpeg concat demuxer with stream copy (-c copy).
    7. Cleans up intermediate clip files unless keep_intermediate_clips is True.

    Args:
        source_path: Path to the input gameplay video recording.
        edit_plan: Validated EditPlan containing planned clips.
        output_path: Destination path for rendered MP4 montage.
        config: Assembly configuration defining the output profile and timeouts.
        source_has_audio: Whether the source media includes an audio stream.
        temp_dir: Working directory for intermediate clip segments.

    Returns:
        Path to the verified, rendered output video.

    Raises:
        AssemblyRenderError: If extraction, normalization, or concatenation fails.
    """
    if not edit_plan.clips:
        raise AssemblyRenderError("Cannot render montage: EditPlan contains zero clips.")

    if not source_path.is_file():
        raise AssemblyRenderError(f"Source media file not found: '{source_path}'")

    ffmpeg_exe = _find_ffmpeg_executable()
    ensure_safe_directory(output_path.parent)

    working_dir = temp_dir or (output_path.parent / f"_tmp_{output_path.stem}")
    ensure_safe_directory(working_dir)

    profile = config.get_profile_config()
    extracted_clip_paths: list[Path] = []

    # Aspect ratio and canvas filter: scale to fit within target canvas, pad with black
    vf_filter = (
        f"scale={profile.width}:{profile.height}:force_original_aspect_ratio=decrease,"
        f"pad={profile.width}:{profile.height}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"setsar=1,fps={profile.fps}"
    )

    try:
        # Phase 1: Extract and normalize individual clips
        for clip in edit_plan.clips:
            clip_path = working_dir / f"clip_{clip.clip_index:03d}_{clip.clip_id[:8]}.mp4"
            extracted_clip_paths.append(clip_path)

            # Build clip extraction command
            cmd = [
                ffmpeg_exe,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                str(clip.source_interval.start),
                "-to",
                str(clip.source_interval.end),
                "-i",
                str(source_path),
                "-vf",
                vf_filter,
                "-c:v",
                profile.video_codec,
                "-preset",
                "fast",
                "-crf",
                str(profile.crf),
                "-pix_fmt",
                profile.pixel_format,
            ]

            if source_has_audio:
                cmd.extend(
                    [
                        "-c:a",
                        profile.audio_codec,
                        "-ar",
                        str(profile.audio_sample_rate),
                        "-ac",
                        str(profile.audio_channels),
                    ]
                )
            else:
                cmd.append("-an")

            cmd.append(str(clip_path))

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=config.timeout_seconds,
                check=False,
            )

            if proc.returncode != 0:
                raise AssemblyRenderError(
                    f"FFmpeg failed extracting clip {clip.clip_index} "
                    f"[{clip.source_interval.start}s - {clip.source_interval.end}s]: {proc.stderr}"
                )

            if not clip_path.is_file() or clip_path.stat().st_size == 0:
                raise AssemblyRenderError(
                    f"FFmpeg produced empty output for clip {clip.clip_index} at '{clip_path}'"
                )

        # Phase 2: Concatenate clips via concat demuxer
        concat_list_path = working_dir / "concat_list.txt"
        with concat_list_path.open("w", encoding="utf-8") as f:
            for p in extracted_clip_paths:
                # Escape single quotes in filenames for concat format
                safe_path = str(p.resolve()).replace("'", "'\\''")
                f.write(f"file '{safe_path}'\n")

        concat_cmd = [
            ffmpeg_exe,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list_path),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(output_path),
        ]

        concat_proc = subprocess.run(
            concat_cmd,
            capture_output=True,
            text=True,
            timeout=config.timeout_seconds,
            check=False,
        )

        if concat_proc.returncode != 0:
            raise AssemblyRenderError(f"FFmpeg concatenation failed: {concat_proc.stderr}")

        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise AssemblyRenderError(
                f"Rendered output montage is missing or empty at '{output_path}'"
            )

        return output_path

    except subprocess.TimeoutExpired as exc:
        if output_path.exists():
            output_path.unlink(missing_ok=True)
        raise AssemblyRenderError(
            f"FFmpeg montage rendering timed out after {config.timeout_seconds}s"
        ) from exc
    except Exception:
        if output_path.exists():
            output_path.unlink(missing_ok=True)
        raise
    finally:
        # Cleanup temporary clips if not configured to keep them
        if not config.keep_intermediate_clips and working_dir.exists():
            for p in extracted_clip_paths:
                if p.exists():
                    p.unlink(missing_ok=True)
            concat_file = working_dir / "concat_list.txt"
            if concat_file.exists():
                concat_file.unlink(missing_ok=True)
            # Remove working dir if empty
            try:
                if not os.listdir(working_dir):
                    working_dir.rmdir()
            except OSError:
                pass
