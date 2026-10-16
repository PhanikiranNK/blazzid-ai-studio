# BLAZZID AI Studio — Stage 2: Media Ingestion, Preprocessing & Fast Video Analysis

## 1. Overview & Module Responsibilities

Stage 2 delivers a robust, local-first media processing engine that inspects raw mobile gaming screen recordings and produces standardized analysis artifacts for downstream computer vision and audio analysis.

The implementation resides in `packages/media/` (`blazzid-media`) and is partitioned into dedicated single-responsibility modules:

| Module | Responsibility | Key Public Entry Points |
| :--- | :--- | :--- |
| `blazzid_media.validation` | Safe path resolution, size boundary verification, symlink policy, directory traversal mitigation. | `validate_input_media_file`, `ensure_safe_directory` |
| `blazzid_media.probe` | Subprocess-based `ffprobe` stream metadata inspection and empirical presentation timestamp pacing analysis. | `probe_media`, `inspect_media` |
| `blazzid_media.preprocessing` | Deterministic FFmpeg transcoding for 720p 30fps analysis proxies and 16kHz mono PCM WAV extraction. | `generate_analysis_proxy`, `extract_audio_wav`, `preprocess_media` |
| `blazzid_media.frames` | Timestamp-aware sparse frame extraction using OpenCV (`cv2.VideoCapture`), streaming frames directly to disk. | `extract_sparse_frames` |
| `blazzid_media.waveform` | Bounded chunk-based audio amplitude and RMS energy computation producing normalized timeline visualizers. | `generate_waveform_peaks`, `save_waveform_json` |
| `blazzid_media.pipeline` | Synchronous pipeline orchestrator providing stage-by-stage diagnostics, timing audits, and artifact aggregation. | `MediaPipeline.process` |
| `blazzid_media.models` | Immutable Pydantic v2 data contracts for media metadata, inspection results, frame descriptors, and pipeline outcomes. | `PipelineResult`, `MediaInspectionResult`, etc. |
| `blazzid_media.errors` | Structured domain exceptions inheriting from `blazzid_core.errors.BlazzidError`. | `MediaInputError`, `ProbeError`, `AudioExtractionError`, etc. |

---

## 2. Supported Input Assumptions & Dependencies

### External Executable Dependencies
- **FFmpeg 7.x / 8.x** (`ffmpeg` on system `PATH`): Required for video transcoding and audio extraction.
- **ffprobe 7.x / 8.x** (`ffprobe` on system `PATH`): Required for container and stream inspection.
- **OpenCV 4.8+** (`opencv-python-headless`): Used for frame-accurate timestamp seeking (`CAP_PROP_POS_MSEC`) and JPEG encoding.

### Supported Input Containers & Codecs
- **Containers**: MP4 (`.mp4`, `.m4v`), QuickTime (`.mov`), Matroska/WebM (`.mkv`, `.webm`).
- **Video Codecs**: H.264 / AVC, H.265 / HEVC, VP9, AV1.
- **Audio Codecs**: AAC, Opus, MP3, Vorbis, PCM WAV.
- **Video without audio**: Fully supported as a first-class input condition. The pipeline produces video proxies and keyframes while gracefully marking the audio waveform stage as `SKIPPED`.

---

## 3. Input Validation & Security Boundary

Processing untrusted user-uploaded media files is intrinsically exposed to container parser vulnerabilities in native demuxers. The security boundary enforces the following controls:

1. **Existence and Type Verification**: Validates that the input path exists, resolves to a regular file, and has active read permissions. Rejects sockets, directories, and character devices.
2. **Size Bounds**: Rejects empty (0-byte) files and files outside configurable bounds (default: 1 KB minimum, 25 GB maximum).
3. **Symlink Policy**: Resolves real target paths and rejects symbolic links when `allow_symlinks=False`.
4. **Subprocess Isolation**:
   - `subprocess.run` is always invoked with argument lists (`List[str]`) and `shell=False`. User strings are never interpolated into shell command strings.
   - Child processes have explicit deadlines (`timeout=180s` for proxy, `30s` for probe).
   - On timeout or subprocess failure, child process resources are reclaimed and partial/corrupted output files are unlinked immediately.
5. **Path Traversal Protection**: Output directories are verified via `ensure_safe_directory` to prevent directory traversal outside designated job sandboxes.
6. **Container Sandboxing Recommendation**: In distributed production deployments (Stage 5+), FFmpeg processing must execute inside an unprivileged, non-root, read-only rootfs container with CPU/memory cgroups and network namespace isolation (`--net=none`).

---

## 4. Metadata Inspection & Frame-Rate Classification

Naive inspection often misclassifies mobile gameplay recordings as Constant Frame Rate (CFR) because MP4 container headers frequently report nominal 30.0 or 60.0 fps in `avg_frame_rate` and `r_frame_rate`, while the underlying stream experiences dropped frames due to thermal throttling or screen recorder contention.

`blazzid_media.probe` executes a two-phase inspection:

1. **Header Inspection**: Executes `ffprobe -show_format -show_streams -print_format json` to extract container duration, bitrates, video dimensions, codec profile, pixel format, time base, aspect ratios, and rotation tags.
2. **Empirical Packet Delta Inspection**:
   - Reads presentation timestamps from a bounded initial window (up to 3 seconds) using `ffprobe -read_intervals %+3 -select_streams v:0 -show_entries packet=pts_time`.
   - Sorts timestamps into presentation order (accounting for B-frame decode-order permutations).
   - Computes consecutive presentation deltas: $\Delta t_i = t_{i+1} - t_i$.
   - **Classification Rules**:
     - $\max(\Delta t) - \min(\Delta t) \le 0.0025\text{s}$ ($\le 2.5\text{ms}$ variance): Confirmed **CFR**.
     - $\max(\Delta t) - \min(\Delta t) > 0.0080\text{s}$ ($> 8.0\text{ms}$ variance): Suspected **VFR**.
     - Insufficient sample count: Falls back to header ratio comparison or **UNKNOWN**.

---

## 5. Preprocessing & Scaling Policy

### Analysis Proxy Video (`proxy.mp4`)
- **Target Resolution**: 1280x720 at 30 fps (CRF 23, preset `fast`).
- **Scaling Filter**:
  ```text
  scale='min(1280,iw)':'min(720,ih)':force_original_aspect_ratio=decrease,scale='trunc(iw/2)*2':'trunc(ih/2)*2'
  ```
- **Policy Rules**:
  - **Aspect Ratio Preservation**: Gameplay frames are never stretched or cropped. UI elements (super button, health bars, gem counts) retain spatial coordinates.
  - **No Upscaling**: Videos smaller than target dimensions (e.g., 480x270 or 360x640 portrait) remain at native scale.
  - **Portrait Video**: A 1080x1920 portrait recording scales down to 404x720 (even dimensions, 9:16 aspect ratio), fitting comfortably inside the 1280x720 bounding box.
  - **Verification**: The generated proxy is verified via `probe_media` before reporting success.

### Audio Extraction (`audio.wav`)
- **Target Format**: 16,000 Hz, 1-channel (mono), 16-bit signed PCM (`pcm_s16le`).
- **Temporal Alignment**: Preserves original container presentation timestamp offsets.

---

## 6. Sparse Frame Extraction

Implemented in `blazzid_media.frames`:
- **Default Sampling Frequency**: Approximately 1 frame per second (`target_interval_seconds=1.0`).
- **Seeking Mechanism**: Uses OpenCV `CAP_PROP_POS_MSEC` to jump directly to interval milestones, then queries actual presentation timestamp to eliminate timestamp drift.
- **Memory Safety**: Frames are encoded and written directly to disk (`frame_{index:06d}_{timestamp_ms:08d}.jpg`). Frames are never buffered in a Python list.
- **Filename Convention**: `frame_000000_00000000.jpg`, `frame_000001_00001000.jpg`, etc.

---

## 7. Waveform Peak Generation

Implemented in `blazzid_media.waveform`:
- **Streaming Chunks**: Reads audio in bounded 1-second buffers (`16,000 samples`), guaranteeing $O(1)$ memory consumption regardless of recording length.
- **Peak Bucket Calculation**: Configurable bucket duration (default 100ms = 0.1s).
- **Normalized Values**: Computes maximum absolute sample $\frac{\max |x_i|}{32768.0}$ and RMS energy $\frac{\sqrt{\frac{1}{N}\sum x_i^2}}{32768.0}$, clamped to $[0.0, 1.0]$.
- **JSON Schema**:
  ```json
  {
    "sample_rate": 16000,
    "channels": 1,
    "bucket_duration_seconds": 0.1,
    "audio_start_seconds": 0.0,
    "total_buckets": 30,
    "peaks": [0.7071, 0.7071, ...],
    "rms": [0.5000, 0.5000, ...]
  }
  ```

---

## 8. Pipeline Output Layout & Artifact Directory

For a given run `MediaPipeline().process(source_path, work_dir)`:

```text
<work_dir>/
├── proxy.mp4              # 720p 30fps H.264 video analysis proxy
├── audio.wav              # 16kHz mono 16-bit PCM WAV (if audio exists)
├── waveform.json          # 100ms bucketed peak & RMS energy data (if audio exists)
└── frames/                # Sparse extracted JPEG keyframes
    ├── frame_000000_00000000.jpg
    ├── frame_000001_00001000.jpg
    └── frame_000002_00002000.jpg
```

---

## 9. Performance & Capacity Benchmarks

Empirical performance measured on host hardware (Apple Silicon M-series, macOS, Python 3.9.13, FFmpeg 8.1.2):

| Operation | Input Target | Mean Latency | Throughput | Peak Memory |
| :--- | :--- | :--- | :--- | :--- |
| **Waveform Peak Generation** | 10s 16kHz WAV (100 buckets) | **1.28 ms** | ~776 ops/sec | $O(1)$ (~2 MB buffer) |
| **Audio Extraction** | 3s 720p MP4 $\to$ 16kHz WAV | **32.11 ms** | ~31 ops/sec | Subprocess streaming |
| **Sparse Frame Extraction** | 3s 720p MP4 (3 frames extracted) | **52.70 ms** | ~19 ops/sec | $O(1)$ (1 frame in memory) |
| **ffprobe Metadata & VFR Pacing** | 720p 30fps MP4 | **62.00 ms** | ~16 ops/sec | Subprocess |
| **Proxy Transcode** | 3s 720p MP4 $\to$ H.264 CRF 26 | **352.68 ms** | ~2.8 ops/sec | Subprocess streaming |
| **End-to-End MediaPipeline** | Full 5-stage pipeline | **515.94 ms** | ~1.9 ops/sec | Subprocess streaming |

*Key finding: Complete 5-stage end-to-end preprocessing processes media at approximately 6x faster than real-time playback speed.*

---

## 10. Execution & Verification Commands

### Run Unit & Integration Tests
```bash
.venv/bin/pytest -v tests/unit/test_media_validation.py \
                    tests/unit/test_probe.py \
                    tests/unit/test_preprocessing.py \
                    tests/unit/test_frames.py \
                    tests/unit/test_waveform.py \
                    tests/integration/test_media_pipeline.py
```

### Run Benchmarks
```bash
.venv/bin/pytest -v benchmarks/test_media_benchmarks.py
```

### Run Strict Type Checking & Linting
```bash
.venv/bin/mypy --strict packages/core/src packages/algorithms/src packages/media/src tests benchmarks
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```
