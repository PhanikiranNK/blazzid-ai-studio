"""Deterministic clip extraction and montage assembly using FFmpeg."""

from __future__ import annotations

import contextlib
import os
import shutil
import signal
import subprocess
import time
from collections.abc import Callable
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


def _run_cancellable_subprocess(
    cmd: list[str],
    timeout_seconds: float,
    is_cancelled_fn: Optional[Callable[[], bool]] = None,
) -> tuple[int, str, str]:
    """Run subprocess in isolated process group with clean cancellation support."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    t0 = time.time()
    try:
        while True:
            ret = proc.poll()
            if ret is not None:
                stdout, stderr = proc.communicate()
                return ret, stdout, stderr

            if is_cancelled_fn and is_cancelled_fn():
                with contextlib.suppress(OSError):
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                try:
                    proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    with contextlib.suppress(OSError):
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                raise AssemblyRenderError("FFmpeg execution cancelled by user request")

            if time.time() - t0 > timeout_seconds:
                with contextlib.suppress(OSError):
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                raise subprocess.TimeoutExpired(cmd, timeout_seconds)

            time.sleep(0.05)
    finally:
        if proc.poll() is None:
            with contextlib.suppress(OSError):
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)


def render_montage(
    source_path: Path,
    edit_plan: EditPlan,
    output_path: Path,
    config: AssemblyConfig,
    *,
    source_has_audio: bool = True,
    temp_dir: Optional[Path] = None,
    is_cancelled_fn: Optional[Callable[[], bool]] = None,
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
    assets_dir = Path(__file__).parent / "assets"
    memes_dir = assets_dir / "memes"
    music_dir = assets_dir / "music"

    try:
        # Phase 1: Extract and normalize individual clips
        for clip in edit_plan.clips:
            clip_path = working_dir / f"clip_{clip.clip_index:03d}_{clip.clip_id[:8]}.mp4"
            extracted_clip_paths.append(clip_path)

            clip_dur = max(0.5, clip.source_interval.end - clip.source_interval.start)
            if (
                clip.climax_timestamp is not None
                and clip.source_interval.start <= clip.climax_timestamp <= clip.source_interval.end
            ):
                rel_c = clip.climax_timestamp - clip.source_interval.start
            else:
                rel_c = clip_dur / 2.0
            z_start = max(0.0, rel_c - 0.75)
            z_end = min(clip_dur, rel_c + 1.25)
            z_len = max(0.4, z_end - z_start)

            vf_steps: list[str] = []

            # 1. Aspect Ratio & Canvas Normalization
            vf_steps.append(
                f"scale={profile.width}:{profile.height}:force_original_aspect_ratio=decrease,"
                f"pad={profile.width}:{profile.height}:(ow-iw)/2:(oh-ih)/2:color=black,"
                f"setsar=1,fps={profile.fps}"
            )

            # 2. Action Cam Punch-In Zoom at Climax
            if config.auto_zoom:
                vf_steps.append(
                    f"scale=w='{profile.width}*(1+0.22*between(t,{z_start:.3f},{z_end:.3f}))':"
                    f"h='{profile.height}*(1+0.22*between(t,{z_start:.3f},{z_end:.3f}))':eval=frame,"
                    f"crop={profile.width}:{profile.height}:(iw-{profile.width})/2:(ih-{profile.height})/2"
                )

            # 3. Meme Badge Overlay at Climax
            badge_path: Optional[Path] = None
            if config.meme_overlays and memes_dir.exists():
                badges = ["ko_badge.png", "iq_badge.png", "victory_badge.png"]
                cand_badge = memes_dir / badges[clip.clip_index % len(badges)]
                if cand_badge.is_file():
                    badge_path = cand_badge

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
            ]

            if badge_path is not None:
                cmd.extend(["-loop", "1", "-i", str(badge_path)])
                filter_chain = ",".join(vf_steps)
                filter_complex = (
                    f"[0:v]{filter_chain}[base];"
                    f"[base][1:v]overlay=x=(W-w)/2:y=H*0.18:enable='between(t,{z_start:.3f},{z_end:.3f})':shortest=1[vout]"
                )
                cmd.extend(["-filter_complex", filter_complex, "-map", "[vout]"])
                if source_has_audio:
                    cmd.extend(["-map", "0:a"])
            else:
                cmd.extend(["-vf", ",".join(vf_steps)])

            cmd.extend(
                [
                    "-c:v",
                    profile.video_codec,
                    "-preset",
                    "fast",
                    "-crf",
                    str(profile.crf),
                    "-pix_fmt",
                    profile.pixel_format,
                ]
            )

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

            retcode, _stdout, stderr = _run_cancellable_subprocess(
                cmd,
                timeout_seconds=config.timeout_seconds,
                is_cancelled_fn=is_cancelled_fn,
            )

            if retcode != 0:
                raise AssemblyRenderError(
                    f"FFmpeg failed extracting clip {clip.clip_index} "
                    f"[{clip.source_interval.start}s - {clip.source_interval.end}s]: {stderr}"
                )

            if not clip_path.is_file() or clip_path.stat().st_size == 0:
                raise AssemblyRenderError(
                    f"FFmpeg produced empty output for clip {clip.clip_index} at '{clip_path}'"
                )

        # Phase 2: Concatenate clips via concat demuxer
        concat_list_path = working_dir / "concat_list.txt"
        with concat_list_path.open("w", encoding="utf-8") as f:
            for p in extracted_clip_paths:
                safe_path = str(p.resolve()).replace("'", "'\\''")
                f.write(f"file '{safe_path}'\n")

        # Check if soundtrack mixing is requested
        music_path: Optional[Path] = None
        if config.soundtrack and music_dir.exists():
            music_map = {
                "phonk": "phonk_drift.wav",
                "cyber": "cyber_arcade.wav",
                "trap": "trap_montage.wav",
            }
            cand_music = music_dir / music_map.get(config.soundtrack.lower(), "phonk_drift.wav")
            if cand_music.is_file():
                music_path = cand_music

        intermediate_out = (
            working_dir / "intermediate_concat.mp4" if music_path else output_path
        )

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
            str(intermediate_out),
        ]

        concat_retcode, _concat_stdout, concat_stderr = _run_cancellable_subprocess(
            concat_cmd,
            timeout_seconds=config.timeout_seconds,
            is_cancelled_fn=is_cancelled_fn,
        )

        if concat_retcode != 0:
            raise AssemblyRenderError(f"FFmpeg concatenation failed: {concat_stderr}")

        if not intermediate_out.is_file() or intermediate_out.stat().st_size == 0:
            raise AssemblyRenderError(
                f"Rendered intermediate montage is missing or empty at '{intermediate_out}'"
            )

        # Phase 3: Mix trending soundtrack if configured
        if music_path is not None:
            if source_has_audio:
                amix_filter = (
                    "[0:a]volume=0.82[game];"
                    "[1:a]volume=0.38[music];"
                    "[game][music]amix=inputs=2:duration=first:dropout_transition=2[aout]"
                )
                map_audio = "[aout]"
            else:
                amix_filter = "[1:a]volume=0.45[music]"
                map_audio = "[music]"

            mix_cmd = [
                ffmpeg_exe,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(intermediate_out),
                "-stream_loop",
                "-1",
                "-i",
                str(music_path),
                "-filter_complex",
                amix_filter,
                "-map",
                "0:v",
                "-map",
                map_audio,
                "-c:v",
                "copy",
                "-c:a",
                profile.audio_codec,
                "-ar",
                str(profile.audio_sample_rate),
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(output_path),
            ]

            mix_retcode, _mix_stdout, mix_stderr = _run_cancellable_subprocess(
                mix_cmd,
                timeout_seconds=config.timeout_seconds,
                is_cancelled_fn=is_cancelled_fn,
            )

            if mix_retcode != 0:
                raise AssemblyRenderError(f"FFmpeg soundtrack mixing failed: {mix_stderr}")

            if not output_path.is_file() or output_path.stat().st_size == 0:
                raise AssemblyRenderError(
                    f"Rendered montage with soundtrack is missing or empty at '{output_path}'"
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
