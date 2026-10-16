# BLAZZID AI Studio — AI & Media Processing Pipeline

## 1. Modular Media Architecture Overview

The BLAZZID AI Studio media pipeline transforms raw, unindexed gaming recordings into structured, ranked highlight candidates. The pipeline adheres to three core design rules:

1. **Two-Tier Adaptive Sampling:** Inexpensive, high-throughput macro-analysis scans the entire video at sparse temporal resolution (1 frame per second). Heavy visual, OCR, and AI inference models are restricted strictly to promising candidate windows at dense resolution (15–30 fps).
2. **Deterministic Fallbacks:** The pipeline never depends on a single brittle neural network. If an AI inference step fails or times out, the system automatically falls back to heuristic visual detectors (color histogram shift, template matching) and audio energy metrics.
3. **Hardware Portability:** Code runs natively on **Apple Silicon (macOS Metal/MPS)**, standard **x86_64 CPU**, **NVIDIA CUDA GPUs**, and ephemeral **Google Colab** runtimes without code branching.

---

## 2. Pipeline Stage Breakdown

```
Raw Media (MP4/MKV)
       │
       ▼
[ Stage 1: Container Probing & Header Validation (ffprobe) ]
       │
       ▼
[ Stage 2: Dual-Stream Proxy & Audio Extraction (FFmpeg) ]
       ├──► 720p30 H.264 Proxy Video (.mp4)
       └──► 16kHz Mono PCM Audio (.wav)
       │
       ├─────────────────────────────────┐
       ▼                                 ▼
[ Stage 3A: Audio Feature Extraction ]   [ Stage 3B: Macro Visual Scan (1 fps) ]
 • RMS Energy & Spectral Centroid         • Scene boundary detection
 • Game sound effect stinger matching     • HUD elimination banner detector
       │                                 │
       └────────────────┬────────────────┘
                        ▼
       [ Stage 4: Window Proposal & Dense Sampling ]
        • Intersect audio spikes + visual cues
        • Extract 15–30 fps frames on candidate windows [t_start - 3s, t_end + 3s]
                        │
                        ▼
       [ Stage 5: Micro OCR & Semantic Verification ]
        • PaddleOCR / Tesseract on Kill Feed & Score HUD
        • Optional Vision-Language Model (VLM) validation
                        │
                        ▼
       [ Stage 6: Multimodal Evidence Fusion & Calibration ]
        • Bayesian probability update
        • Temporal boundary refinement (Setup -> Climax -> Payoff)
                        │
                        ▼
       [ Stage 7: Deterministic EDL Compilation & Rendering ]
        • FFmpeg filter_complex multi-clip assembly
        • EBU R128 audio normalization
```

---

## 3. Technology Stack & Library Evaluation

| Pipeline Function | Primary Library | Secondary / Fallback | Hardware Target | License |
| :--- | :--- | :--- | :--- | :--- |
| **Media Probing** | `ffprobe` (via Python subprocess) | `pymediainfo` | CPU (All) | LGPL / GPL |
| **Video Decoding & Proxy** | `FFmpeg` CLI (version 8.x) | Hardware accels (`h264_videotoolbox`, `h264_nvenc`) | Apple Silicon, CUDA, CPU | LGPL / GPL |
| **Frame Manipulation** | `OpenCV` (`cv2` 4.9+) | `Pillow-SIMD` | CPU / Metal / CUDA | Apache 2.0 |
| **Audio Processing** | `NumPy`, `SciPy`, `SoundFile` | `Librosa` (feature extraction) | CPU (Vectorized) | BSD-3-Clause |
| **Text Recognition (OCR)** | `PaddleOCR` (PP-OCRv4) | `Tesseract` (via `pytesseract`) | CPU / MPS / CUDA | Apache 2.0 |
| **VLM / Semantic Embedding** | `CLIP` (ViT-B/32) / `SigLIP` | `Moondream2` / `SmolVLM` | MPS / CUDA / CPU | MIT / Apache 2.0 |
| **Audio Normalization** | `FFmpeg` (`loudnorm` filter) | `pydub` | CPU | LGPL |

---

## 4. Adaptive Sampling Strategy

### 4.1 Tier 1: Macro-Analysis (1 FPS)
Scanning a 2-hour 60fps video at full frame rate requires decoding and inspecting **432,000 frames**.
- Macro-analysis samples exactly **1 frame per second** (7,200 frames total).
- For each sampled frame:
  1. Compute grayscale average luminance and color histogram difference against previous frame (scene cut / death screen detection).
  2. Crop static HUD regions (Brawl Stars Top Center: Gem/Star count; Top Right: Elimination Kill Feed).
  3. Compute template matching cross-correlation with known UI icons (Showdown Skull, Overtime text stinger).
- Macro-analysis processes at **$\ge 200\text{ fps}$**, completing a 2-hour recording in under **40 seconds** on a standard modern CPU.

### 4.2 Tier 2: Candidate Window Expansion & Dense Sampling (15 FPS)
- When Tier 1 macro-analysis or audio energy spikes exceed baseline threshold ($z \ge 2.5$), a candidate window $[t_{\text{trigger}} - 6.0\text{s}, t_{\text{trigger}} + 6.0\text{s}]$ is marked.
- The video decoder seeks to the candidate keyframe and densely samples frames at **15 fps**.
- OCR and fine-grained visual tracking are executed exclusively within these dense windows.
- Over a 2-hour video with 20 candidate events, dense sampling processes only $20 \times 12\text{s} \times 15\text{ fps} = 3,600\text{ frames}$, achieving a **99.2% reduction in compute load** compared to brute-force dense scanning.

---

## 5. Game-Specific Heuristics: Brawl Stars Profile

The pipeline encapsulates game-specific knowledge into a modular `GameProfile` interface:

```python
class BrawlStarsProfile(GameProfile):
    GAME_TITLE = "Brawl Stars"
    
    # Normalized bounding box coordinates (x, y, width, height) relative to 16:9 canvas
    HUD_REGIONS = {
        "KILL_FEED": (0.72, 0.05, 0.26, 0.25),
        "GEM_SCORE_TOP": (0.35, 0.02, 0.30, 0.10),
        "SHOWDOWN_COUNT": (0.40, 0.12, 0.20, 0.08),
        "SUPER_JOYSTICK": (0.75, 0.65, 0.20, 0.30),
    }

    # Audio acoustic signature frequencies
    AUDIO_SIGNATURES = {
        "OVERTIME_ALARM_HZ": [880, 1760],
        "GEM_SPAWN_CHIME_HZ": [2400, 3200],
    }

    # Key text patterns for regex matching
    OCR_PATTERNS = [
        r"(?i)defeated",
        r"(?i)eliminated",
        r"(?i)double kill",
        r"(?i)triple kill",
        r"(?i)match over",
        r"(?i)showdown",
    ]
```

Adding support for another game (e.g., *Valorant* or *League of Legends*) simply requires registering a new `GameProfile` subclass without altering the core pipeline.

---

## 6. Multimodal Evidence Fusion & Calibration

A raw gameplay event is never asserted from a single detector. Instead, evidence from multiple modalities is fused using a **Calibrated Bayesian Evidence Model**:

$$P(\text{Highlight} \mid E) = \frac{P(\text{Highlight}) \prod_{m} P(E_m \mid \text{Highlight})}{P(E)}$$

In log-odds space, this translates to an additive weighted scoring formula:

$$\text{Score}_{\text{composite}} = \sigma \left( \beta_0 + \sum_{m \in M} w_m \cdot f_m(E_m) \right)$$

Where:
- $w_{\text{visual}}$: Weight assigned to visual HUD triggers ($w \approx 0.35$).
- $w_{\text{ocr}}$: Weight assigned to verified text (e.g., player elimination name) ($w \approx 0.40$).
- $w_{\text{audio}}$: Weight assigned to acoustic energy/stinger spikes ($w \approx 0.25$).
- $\sigma(z) = \frac{1}{1 + e^{-z}}$: Logistic sigmoid mapping the score into a calibrated probability $[0.0, 1.0]$.

### Provenance Tracking
Every fused event retains an immutable `evidence_payload`:
```json
{
  "event_id": "ev_8829",
  "event_type": "TRIPLE_KILL",
  "calibrated_confidence": 0.942,
  "sources": [
    {
      "modality": "OCR",
      "detector": "KillFeedParser",
      "timestamp": 421.200,
      "raw_text": "Triple Elimination",
      "confidence": 0.95
    },
    {
      "modality": "AUDIO",
      "detector": "RMSZScore",
      "timestamp": 421.800,
      "z_score": 3.42,
      "confidence": 0.88
    },
    {
      "modality": "VISUAL",
      "detector": "TemplateMatcher",
      "timestamp": 420.900,
      "template": "skull_icon.png",
      "correlation": 0.91
    }
  ]
}
```

---

## 7. Context-Aware Boundary Expansion

Raw triggers indicate the exact moment an event registers (e.g., elimination message at $t = 124.5\text{s}$). If a clip is cut directly at this timestamp, the viewer misses the anticipation and the aftermath.

The pipeline expands each raw trigger into a narrative three-act structure:
1. **Setup (Anticipation):** $t_{\text{trigger}} - \Delta t_{\text{lead-in}}$ (typically $4.0\text{s}$ to $6.0\text{s}$ prior). Captures the positioning, aiming, and initiation of the play.
2. **Climax (Action):** The event moment itself.
3. **Payoff (Aftermath):** $t_{\text{trigger}} + \Delta t_{\text{lead-out}}$ (typically $2.0\text{s}$ to $4.0\text{s}$ post). Captures reaction, gem pickup, or emote reaction.

### Dynamic Boundary Adjustment
- If an audio cheering spike persists after the elimination, $\Delta t_{\text{lead-out}}$ is extended dynamically until the audio energy returns to the baseline rolling mean.
- If a scene cut (black frame or match victory screen) occurs within the lead-out window, the boundary is snapped to the scene cut to avoid showing jarring partial transitions.

---

## 8. Hardware Target Matrix & Performance Profile

| Target Environment | Acceleration Backend | Model Selection | Expected Ingestion Ratio ($T_{\text{proc}} / T_{\text{video}}$) | Peak Memory |
| :--- | :--- | :--- | :--- | :--- |
| **Apple Silicon (M1/M2/M3/M4)** | Metal Performance Shaders (`mps`) + `VideoToolbox` | PaddleOCR (ONNX) + SigLIP (CoreML/MPS) | $\approx 0.12\times$ (1hr video in 7.2 min) | $\approx 2.2\text{ GB}$ |
| **Linux / x86_64 CPU** | AVX2 / OpenBLAS | PaddleOCR (CPU) + MobileNetV4 | $\approx 0.25\times$ (1hr video in 15 min) | $\approx 1.8\text{ GB}$ |
| **NVIDIA GPU (CUDA)** | TensorRT / PyTorch CUDA | PaddleOCR (CUDA) + SmolVLM | $\approx 0.05\times$ (1hr video in 3 min) | $\approx 4.5\text{ GB}$ |
| **Google Colab (T4 GPU)** | CUDA 12.x | PaddleOCR + CLIP ViT-B/32 | $\approx 0.08\times$ (1hr video in 4.8 min) | $\approx 3.8\text{ GB}$ |

### Zero Mandatory Fine-Tuning Policy
In Stage 0 through Stage 4, **no custom neural network fine-tuning is required**. The pipeline relies on:
1. Classical computer vision (OpenCV template matching, color histograms).
2. Off-the-shelf, open-weight OCR engines (PaddleOCR Apache 2.0).
3. Digital signal processing for audio (FFT, RMS energy, spectral centroid).
4. Pretrained zero-shot vision-language embeddings (SigLIP / CLIP).

Fine-tuning will only be evaluated in Stage 9 if an empirical benchmark on labeled test datasets demonstrates an irrecoverable precision deficit in zero-shot models.
