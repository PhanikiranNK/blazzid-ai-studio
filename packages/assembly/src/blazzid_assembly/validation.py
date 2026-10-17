"""Post-render output integrity and synchronization verification."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from blazzid_assembly.config import AssemblyConfig
from blazzid_assembly.models import EditPlan, ValidationReport
from blazzid_media.probe import probe_media


def validate_rendered_montage(
    output_path: Path,
    edit_plan: EditPlan,
    config: AssemblyConfig,
    *,
    expected_has_audio: bool = True,
    duration_tolerance_seconds: float = 0.75,
) -> ValidationReport:
    """Verifies the structural, temporal, and decode integrity of a rendered montage.

    Verification steps:
    1. Checks that the rendered video file exists and has non-zero size.
    2. Probes container and stream properties using ffprobe.
    3. Confirms video stream presence and verifies canvas dimensions against profile.
    4. Confirms audio stream presence matches source audio policy.
    5. Verifies that actual output duration matches planned duration within tolerance.
    6. Executes a headless decode smoke test (ffmpeg -f null) to verify container and packet integrity.

    Args:
        output_path: Path to rendered MP4 video.
        edit_plan: Edit plan containing planned duration.
        config: Assembly configuration defining expected profile dimensions.
        expected_has_audio: Whether the output is expected to contain an audio stream.
        duration_tolerance_seconds: Maximum permissible deviation between actual and planned duration.

    Returns:
        Structured ValidationReport with pass/fail findings.
    """
    checks_passed: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []

    # Check 1: File existence and non-empty
    if not output_path.is_file():
        errors.append(f"Output file does not exist at '{output_path}'")
        return ValidationReport(
            is_valid=False,
            output_path=output_path,
            container_format="unknown",
            has_video=False,
            has_audio=False,
            width=0,
            height=0,
            actual_duration_seconds=0.0,
            planned_duration_seconds=edit_plan.total_duration_seconds,
            duration_difference_seconds=edit_plan.total_duration_seconds,
            checks_passed=[],
            errors=errors,
            warnings=[],
        )

    file_size = output_path.stat().st_size
    if file_size == 0:
        errors.append("Rendered output file is 0 bytes.")
    else:
        checks_passed.append(f"file_exists_and_non_empty ({file_size} bytes)")

    # Check 2: Probe streams and container
    try:
        inspection = probe_media(output_path)
    except Exception as exc:
        errors.append(f"ffprobe container inspection failed: {exc}")
        return ValidationReport(
            is_valid=False,
            output_path=output_path,
            container_format="corrupt",
            has_video=False,
            has_audio=False,
            width=0,
            height=0,
            actual_duration_seconds=0.0,
            planned_duration_seconds=edit_plan.total_duration_seconds,
            duration_difference_seconds=edit_plan.total_duration_seconds,
            checks_passed=checks_passed,
            errors=errors,
            warnings=[],
        )

    container_format = inspection.container.format_name
    checks_passed.append(f"container_probed ({container_format})")

    # Check 3: Video stream validation
    has_video = inspection.video is not None
    width = 0
    height = 0
    fps = 0.0
    profile = config.get_profile_config()

    if not has_video or inspection.video is None:
        errors.append("Rendered output lacks a valid video stream.")
    else:
        width = inspection.video.width
        height = inspection.video.height
        fps = inspection.video.avg_frame_rate or 0.0
        checks_passed.append("video_stream_present")

        if width != profile.width or height != profile.height:
            errors.append(
                f"Output dimensions ({width}x{height}) do not match target profile ({profile.width}x{profile.height})."
            )
        else:
            checks_passed.append(f"dimensions_match_profile ({width}x{height})")

    # Check 4: Audio stream validation
    has_audio = inspection.audio is not None
    if expected_has_audio and not has_audio:
        errors.append("Audio stream expected but missing in rendered output.")
    elif not expected_has_audio and has_audio:
        warnings.append("Audio stream present in output although source was audio-less.")
    else:
        checks_passed.append(f"audio_policy_satisfied (has_audio={has_audio})")

    # Check 5: Duration tolerance check
    actual_dur = inspection.container.duration_seconds
    planned_dur = edit_plan.total_duration_seconds
    diff = abs(actual_dur - planned_dur)

    if diff > duration_tolerance_seconds:
        errors.append(
            f"Output duration ({actual_dur:.2f}s) deviates from planned duration ({planned_dur:.2f}s) "
            f"by {diff:.2f}s (tolerance: {duration_tolerance_seconds:.2f}s)."
        )
    else:
        checks_passed.append(
            f"duration_within_tolerance (actual={actual_dur:.2f}s, planned={planned_dur:.2f}s, diff={diff:.2f}s)"
        )

    # Check 6: Decode smoke test
    ffmpeg_exe = shutil.which("ffmpeg")
    if ffmpeg_exe is not None:
        smoke_cmd = [
            ffmpeg_exe,
            "-v",
            "error",
            "-i",
            str(output_path),
            "-f",
            "null",
            "-",
        ]
        try:
            smoke_proc = subprocess.run(
                smoke_cmd,
                capture_output=True,
                text=True,
                timeout=config.timeout_seconds,
                check=False,
            )
            if smoke_proc.returncode != 0:
                errors.append(f"Decode smoke test failed: {smoke_proc.stderr}")
            else:
                checks_passed.append("decode_smoke_test_passed")
        except Exception as exc:
            errors.append(f"Exception during decode smoke test: {exc}")

    is_valid = len(errors) == 0

    return ValidationReport(
        is_valid=is_valid,
        output_path=output_path,
        container_format=container_format,
        has_video=has_video,
        has_audio=has_audio,
        width=width,
        height=height,
        fps=fps,
        actual_duration_seconds=round(actual_dur, 3),
        planned_duration_seconds=round(planned_dur, 3),
        duration_difference_seconds=round(diff, 3),
        checks_passed=checks_passed,
        errors=errors,
        warnings=warnings,
    )
