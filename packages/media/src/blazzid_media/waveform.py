"""Bounded chunk-based audio waveform peak and RMS energy generator."""

from __future__ import annotations

import json
import math
import wave
from pathlib import Path
from typing import Any

import numpy as np

from blazzid_media.errors import WaveformError
from blazzid_media.models import WaveformResult
from blazzid_media.validation import ensure_safe_directory


def generate_waveform_peaks(
    wav_path: Path | str,
    *,
    bucket_duration_seconds: float = 0.1,
    audio_start_seconds: float = 0.0,
    chunk_frames_read: int = 16000,  # 1 second of 16kHz audio per chunk
) -> WaveformResult:
    """Computes compact peak and RMS amplitude summaries from a 16-bit PCM WAV file.

    Reads the audio file in bounded sample chunks, maintaining strictly O(1) memory
    regardless of input audio duration (supporting multi-hour recordings).

    Args:
        wav_path: Path to mono or stereo 16-bit PCM WAV file.
        bucket_duration_seconds: Duration of each peak bucket in seconds (default 0.1s = 100ms).
        audio_start_seconds: Presentation timestamp offset relative to source timeline.
        chunk_frames_read: Number of audio frames to buffer per disk read.

    Returns:
        WaveformResult with normalized peaks and RMS values in [0.0, 1.0].

    Raises:
        WaveformError: If WAV file is invalid, unsupported, or unreadable.
    """
    if (
        bucket_duration_seconds <= 0.0
        or math.isnan(bucket_duration_seconds)
        or math.isinf(bucket_duration_seconds)
    ):
        raise WaveformError(
            f"bucket_duration_seconds must be a positive finite float, got {bucket_duration_seconds}"
        )

    p = Path(wav_path).resolve()
    if not p.is_file():
        raise WaveformError(f"Audio file not found: '{p.name}'")

    try:
        with wave.open(str(p), "rb") as wf:
            sample_width = wf.getsampwidth()
            if sample_width != 2:
                raise WaveformError(
                    f"Only 16-bit PCM WAV (sampwidth=2) is supported, got {sample_width}"
                )

            channels = wf.getnchannels()
            sample_rate = wf.getframerate()

            if sample_rate <= 0:
                raise WaveformError(f"Invalid WAV sample rate: {sample_rate}")

            samples_per_bucket = int(round(sample_rate * bucket_duration_seconds))
            if samples_per_bucket < 1:
                samples_per_bucket = 1

            peaks: list[float] = []
            rms_values: list[float] = []

            current_bucket_samples: list[np.ndarray[Any, Any]] = []
            accumulated_samples_count = 0

            max_int16 = 32768.0

            while True:
                raw_bytes = wf.readframes(chunk_frames_read)
                if not raw_bytes:
                    break

                # Convert 16-bit signed PCM bytes to numpy array
                data = np.frombuffer(raw_bytes, dtype=np.int16)

                # If stereo or multichannel, take the mean across channels or mono slice
                if channels > 1:
                    data = data.reshape(-1, channels)
                    data = data.mean(axis=1).astype(np.int16)

                chunk_len = len(data)
                offset = 0

                while offset < chunk_len:
                    needed = samples_per_bucket - accumulated_samples_count
                    available = chunk_len - offset
                    take_count = min(needed, available)

                    current_bucket_samples.append(data[offset : offset + take_count])
                    accumulated_samples_count += take_count
                    offset += take_count

                    if accumulated_samples_count >= samples_per_bucket:
                        # Finalize current bucket
                        bucket_array = np.concatenate(current_bucket_samples)
                        peak_val = float(np.max(np.abs(bucket_array))) / max_int16
                        rms_val = (
                            float(np.sqrt(np.mean(bucket_array.astype(np.float64) ** 2)))
                            / max_int16
                        )

                        peaks.append(round(min(1.0, max(0.0, peak_val)), 4))
                        rms_values.append(round(min(1.0, max(0.0, rms_val)), 4))

                        current_bucket_samples = []
                        accumulated_samples_count = 0

            # Handle final partial bucket if present
            if current_bucket_samples:
                bucket_array = np.concatenate(current_bucket_samples)
                if len(bucket_array) > 0:
                    peak_val = float(np.max(np.abs(bucket_array))) / max_int16
                    rms_val = (
                        float(np.sqrt(np.mean(bucket_array.astype(np.float64) ** 2))) / max_int16
                    )
                    peaks.append(round(min(1.0, max(0.0, peak_val)), 4))
                    rms_values.append(round(min(1.0, max(0.0, rms_val)), 4))

            return WaveformResult(
                sample_rate=sample_rate,
                channels=channels,
                bucket_duration_seconds=bucket_duration_seconds,
                audio_start_seconds=audio_start_seconds,
                total_buckets=len(peaks),
                peaks=peaks,
                rms=rms_values,
            )
    except WaveformError:
        raise
    except Exception as err:
        raise WaveformError(f"Failed to process WAV file '{p.name}': {err}") from err


def save_waveform_json(result: WaveformResult, destination_path: Path | str) -> Path:
    """Saves a WaveformResult as a formatted JSON artifact."""
    dest = Path(destination_path).resolve()
    ensure_safe_directory(dest.parent)

    data = result.model_dump()
    with dest.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return dest
