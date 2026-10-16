# BLAZZID AI Studio — Requirements & Product Specification

## 1. Executive Summary & Vision

**BLAZZID AI Studio** is an AI-powered gaming video intelligence platform that transforms long gaming recordings into high-quality, ranked, context-aware, publish-ready highlights. 

While initially focused on **Brawl Stars** (fast-paced 3v3 and battle royale mobile gameplay with distinct visual kills, kill feeds, gem counts, showdown skulls, and overtime audio stingers), the platform is architected around an extensible, domain-agnostic media intelligence framework. Future support for tactical shooters (Valorant, CS2), MOBAs (Wild Rift, League of Legends), and battle royales (Apex Legends) will plug into the same core ingestion, evidence fusion, candidate ranking, and rendering pipeline without re-architecting the system.

A foundational architectural tenet of BLAZZID AI Studio is:
> **No Magic AI:** The system does not assume an end-to-end black-box model can reliably determine every kill, clutch, comeback, or victory. Instead, the platform is designed around **multimodal evidence, confidence calibration, provenance tracking, uncertainty estimation, and measurable evaluation**.

---

## 2. System Goals & Non-Goals

### 2.1 Functional Goals
1. **Long-Form Ingestion:** Ingest raw gameplay recordings ranging from 5 minutes to 3 hours in common container formats (`MP4`, `MKV`, `MOV`, `WebM`) encoded in `H.264`, `HEVC`, or `VP9` at resolutions up to `4K60`.
2. **Multimodal Analysis:** Extract synchronized visual, audio, OCR, and optional speech features to detect candidate moments (e.g., elimination announcements, multi-kills, match-point countdowns, high-energy commentator/player excitement).
3. **Evidence Fusion & Provenance:** Correlate weak and strong signals into calibrated event observations with traceable provenance (e.g., "Event detected via 0.85 OCR match on elimination banner + 0.72 audio RMS energy spike at offset 124.5s").
4. **Context-Aware Temporal Optimization:** Intelligently expand raw event trigger timestamps into narrative intervals that include setup (anticipation), climax (the action), and payoff (aftermath/reaction), while avoiding disjointed truncations and redundant overlaps.
5. **Deterministic Edit Decision Lists (EDL):** Produce machine-readable, human-inspectable EDL specifications (JSON format) declaring cuts, transitions, volume ducking, and overlays.
6. **Artifact Rendering & Validation:** Render publish-ready MP4 exports using an FFmpeg-based deterministic pipeline, verifying output video duration, audio sync, frame continuity, and bitstream compliance.
7. **Creator Studio UI:** Provide a timeline-based review web application allowing creators to inspect detected highlights, adjust boundaries, reject false positives, reorder clips, preview in real time, and trigger final exports.

### 2.2 Non-Goals for Stage 0 & Initial Production
1. **Real-time Live-Stream Broadcast Ingestion (RTMP/WebRTC):** Initial versions focus on post-session VODs and uploaded files. Live low-latency stream clipping is a planned future capability.
2. **Generative AI Video Hallucination:** The platform edits real gameplay footage; it does not generate synthetic gameplay frames or deepfake video content.
3. **End-to-End Black-Box Video Classification:** We explicitly avoid single-shot black-box "highlight or not" neural networks that lack explainability, confidence intervals, and tunable weights.
4. **Universal Game Automation:** We do not attempt zero-shot gameplay comprehension for arbitrary games without game-specific profile plugins (detectors, OCR bounding boxes, and audio templates).

---

## 3. User Personas & Use Cases

| Persona | Primary Goal | Pain Point Addressed |
| :--- | :--- | :--- |
| **Competitive Brawl Stars Content Creator** | Produce daily YouTube Shorts / TikTok clips from 2-hour scrim recordings. | Spending 3 hours manually scrubbing timelines to find 4 game-winning team wipes. |
| **Tournament Organizer / Caster** | Assemble post-match recap reels within 10 minutes of set completion. | Tight turnaround schedules and human error in missing off-screen clutch plays. |
| **Casual Mobile Gamer** | Archive personal best plays to share with friends and club members. | Lack of video editing expertise or access to desktop NLE software like Premiere/DaVinci. |

---

## 4. Functional Requirements (FR)

### Ingestion & Preprocessing
- **FR-01:** The system shall accept media uploads via direct chunked/resumable upload to S3-compatible object storage via presigned URLs.
- **FR-02:** The system shall inspect uploaded containers using `ffprobe` to extract codec, duration, frame rate, audio channel layout, pixel format, and stream integrity.
- **FR-03:** Media files failing container validation (e.g., truncated files, unsupported codecs, missing moov atom) must be rejected with deterministic error codes.
- **FR-04:** The preprocessor shall extract standardized proxy video streams (e.g., 720p 30fps H.264) and normalized audio waveforms (16kHz mono WAV) for efficient analysis.

### Multimodal Analysis
- **FR-05:** Visual analysis shall perform adaptive frame sampling: sparse temporal sampling (e.g., 1–2 fps) for macro-scene filtering, and dense sampling (e.g., 10–30 fps) around high-interest candidate windows.
- **FR-06:** Visual detectors shall identify HUD state transitions: player count, match clock, showdown/overtime state, and elimination feed alerts.
- **FR-07:** OCR analysis shall extract targeted bounding-box text for kill notices, player tags, and gem/star counts using lightweight inference.
- **FR-08:** Audio analysis shall compute rolling RMS energy, spectral flux, zero-crossing rate, and peak loudness to isolate excitement spikes, game sound effects, and caster commentary.

### Evidence Fusion & Ranking
- **FR-09:** The fusion engine shall aggregate multiple modality observations within a sliding temporal window, computing a composite confidence score $\in [0.0, 1.0]$.
- **FR-10:** Each event must carry an explicit evidence payload listing the contributing detectors, feature values, and timestamp ranges.
- **FR-11:** The ranking engine shall sort candidates using configurable utility functions that prioritize rarity, match significance, and creator preferences.
- **FR-12:** The selection algorithm must enforce global constraints: maximum highlight reel duration, minimum clip duration, maximum overlap threshold, and game mode diversity.

### Review & Rendering
- **FR-13:** The Studio UI shall render an interactive timeline displaying the proxy video, audio waveform, detected candidate markers, confidence scores, and current EDL boundaries.
- **FR-14:** Creators shall be able to drag clip in/out points, add manual clips, adjust playback speed, and reorder highlight sequences.
- **FR-15:** Final rendering requests shall be dispatched to asynchronous worker pools, executing multi-pass or single-pass FFmpeg filter graphs.
- **FR-16:** Rendered outputs shall be validated for audio/video synchronization ($\le 20\text{ms}$ drift), targeted bitrate, and aspect ratio adaptation (16:9 landscape or 9:16 vertical crop).

---

## 5. Non-Functional Requirements (NFR)

### NFR-1: Performance & Latency
- **Ingestion/Analysis Throughput:** A 60-minute 1080p60 recording must complete macro-analysis and generate an initial EDL in $\le 15$ minutes on standard CPU workers (or $\le 5$ minutes with GPU acceleration) — an analysis ratio $\le 0.25\times$ real-time.
- **Render Speed:** Highlight reel generation (typically 3–5 minutes total duration) must render at $\ge 2.0\times$ playback speed on standard hardware.
- **API Latency:** Read queries for projects, job statuses, and candidate lists must return with $P_{95} \le 150\text{ms}$.

### NFR-2: Scalability & Resource Utilization
- **Worker Isolation:** Compute-heavy video decoding and rendering must run in isolated worker processes/pods separate from user-facing web services.
- **Bounded Concurrency:** System must enforce hard limits on concurrent FFmpeg and model inference processes per host to prevent Out-Of-Memory (OOM) kernel panics.
- **Queue-Driven Autoscaling:** Workers must scale based on queue backlog depth and processing time estimates rather than raw CPU utilization.

### NFR-3: Reliability, Durability & Graceful Degradation
- **Idempotency & Resumption:** All worker jobs must be strictly idempotent. A worker crash or node termination must not corrupt project state; uncompleted jobs must be re-queued and safely resumed from known checkpoints.
- **Fallback Modes:** If vision-language models or heavy neural networks are unavailable or time out, the system must gracefully fall back to classical CV (color histogram / template matching) and audio energy spikes.
- **Crash Recovery:** Processing jobs stuck in `RUNNING` state beyond a configurable timeout ($T_{\text{heartbeat}} \times 3$) must be detected by a reconciliation supervisor and recovered.

### NFR-4: Security & Compliance
- **Zero Shell Injection:** All external process invocations (`ffmpeg`, `ffprobe`) must use explicit argument vectors without shell interpretation (`execFile`/`subprocess.run` with `shell=False`).
- **Object Storage Access:** Video binaries must never be directly public. Access must be mediated via short-lived (15–60 min) presigned URLs.
- **Storage Sanitization:** Temporary scratch files must be cleaned up on job completion, failure, or container shutdown via deterministic contextual cleanup handlers.

---

## 6. Knowns, Inferred Context & Technical Assumptions

### 6.1 Known Facts (Observed directly from Environment & Repository)
1. **Repository:** Freshly initialized Git repository on `main` branch with remote pointing to `https://github.com/PhanikiranNK/blazzid-ai-studio.git`.
2. **Local Environment:** Apple Silicon Mac (`Darwin arm64`), macOS 25.6.0 kernel.
3. **Available Tooling:** Python 3.9.13, Node.js v20.20.0, npm, Docker 28.5.1, FFmpeg 8.1.2, ffprobe 8.1.2.
4. **Current Status:** No existing application code or documents; clean slate for Stage 0 architecture.

### 6.2 Inferred Context
1. **Target Developer Experience:** Development will occur locally on macOS Apple Silicon and Linux Docker containers, with target production deployment to Kubernetes.
2. **Compute Profile:** Media processing involves high CPU utilization (FFmpeg decoding/encoding) and bursty GPU/Neural Engine usage (ML inference).

### 6.3 Technical Assumptions & Boundary Conditions
1. **Brawl Stars Gameplay Characteristics:** Standard matches last 2 to 3.5 minutes. Battle Royale (Showdown) matches last 1.5 to 4 minutes. A 1-hour recording typically contains 15–25 individual matches.
2. **Audio Tracks:** Screen recordings may contain game audio only, or game audio mixed with Discord/microphone audio. The audio pipeline must handle mono/stereo and variable sample rates gracefully.
3. **Visual Quality Variations:** Uploaded files may range from clean 1080p 60fps screen captures to compressed 720p 30fps mobile recordings with variable frame rates (VFR). Constant frame rate (CFR) normalization is a necessary preprocessing step.
