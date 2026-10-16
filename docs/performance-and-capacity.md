# BLAZZID AI Studio — Performance Engineering & Capacity Planning

## 1. Capacity Planning Model & Workload Variables

System capacity and hardware requirements are functions of continuous media characteristics and concurrent job loads. Rather than committing to arbitrary scale targets, we define a parameterized mathematical model.

### 1.1 Independent Workload Variables

| Variable | Description | Typical Baseline Value | High-Load Peak Value |
| :--- | :--- | :--- | :--- |
| $T_{\text{rec}}$ | Duration of single input recording | $3,600\text{ s}$ (1 hour) | $10,800\text{ s}$ (3 hours) |
| $(W, H)$ | Resolution of input recording | $1920 \times 1080$ (1080p) | $3840 \times 2160$ (4K UHD) |
| $FPS_{\text{in}}$ | Native frame rate of recording | $60\text{ fps}$ | $60\text{ fps}$ |
| $BR_{\text{in}}$ | Video bit rate | $15\text{ Mbps}$ | $45\text{ Mbps}$ |
| $\lambda$ | Job arrival rate (new uploads per hour) | $10\text{ jobs/hour}$ ($\approx 0.0028\text{ s}^{-1}$) | $60\text{ jobs/hour}$ ($\approx 0.0167\text{ s}^{-1}$) |
| $K$ | Target highlight clips selected | $10\text{ clips}$ | $25\text{ clips}$ |
| $D_{\text{reel}}$ | Final exported highlight reel duration | $180\text{ s}$ (3 minutes) | $360\text{ s}$ (6 minutes) |

---

## 2. Processing Stage Latency & Resource Model

Let $T_{\text{stage}}$ represent the wall-clock execution time for a given stage on a single asset.

### 2.1 Stage 1: Ingestion Probing & Container Validation
- **Computation:** Header parsing via `ffprobe`, reading moov atom and stream metadata.
- **Formula:** $T_{\text{probe}} = c_{\text{probe}} \approx 2.0\text{ seconds}$ (constant, I/O bound to header read).
- **RAM Footprint:** $\approx 50\text{ MB}$.

### 2.2 Stage 2: Dual-Stream Proxy & Audio Extraction
- **Computation:** Decoding H.264/HEVC, downscaling to $1280 \times 720$, encoding 30fps H.264 proxy, extracting 16kHz mono WAV.
- **Formula:** 
  $$T_{\text{proxy}} = \frac{T_{\text{rec}}}{\text{SpeedFactor}_{\text{proxy}}}$$
  Where $\text{SpeedFactor}_{\text{proxy}} \approx 10.0\times$ on modern multi-core CPU with SIMD / hardware acceleration.
  For $T_{\text{rec}} = 3600\text{s}$, $T_{\text{proxy}} \approx 360\text{s}$ (6.0 minutes).
- **CPU Demand:** 2 cores at $100\%$ utilization.
- **Disk Scratch:** 
  $$\text{Disk}_{\text{proxy}} \approx T_{\text{rec}} \times \left( \frac{2.5\text{ Mbps (proxy)}}{8} + \frac{0.256\text{ Mbps (wav)}}{8} \right) \approx 1.24\text{ GB}$$

### 2.3 Stage 3: Audio Analysis & Stinger Matching
- **Computation:** STFT, RMS energy, spectral centroid, cross-correlation on 16kHz mono WAV ($5.76 \times 10^7$ samples for 1 hour).
- **Formula:** $T_{\text{audio}} \approx 15.0\text{ seconds}$ (vectorized NumPy/SciPy operates at $> 200\times$ real-time).
- **RAM Footprint:** $57.6\times 10^6 \times 4\text{ bytes} \approx 230\text{ MB}$.

### 2.4 Stage 4: Visual Macro-Scan & Dense OCR Inference
- **Macro-Scan:** 1 frame per second $\to 3,600\text{ frames}$.
  $T_{\text{macro}} = \frac{3,600\text{ frames}}{150\text{ fps}} \approx 24.0\text{ seconds}$.
- **Candidate Proposals:** Identifies $M \approx 30$ candidate windows of length $12\text{s}$ each ($360\text{s}$ total dense footage).
- **Dense Frame Extraction:** $360\text{s} \times 15\text{ fps} = 5,400\text{ frames}$.
- **OCR Processing:** Lightweight PaddleOCR on cropped HUD regions:
  $$T_{\text{ocr}} = 5,400\text{ crops} \times L_{\text{ocr}}$$
  On Apple Silicon MPS or CUDA GPU: $L_{\text{ocr}} \approx 8\text{ms per crop} \implies T_{\text{ocr}} \approx 43.2\text{ seconds}$.
  On x86_64 CPU (4 cores): $L_{\text{ocr}} \approx 25\text{ms per crop} \implies T_{\text{ocr}} \approx 135.0\text{ seconds}$.

### 2.5 Stage 5: Evidence Fusion & DP Ranking
- **Computation:** Sweep-line aggregation + Weighted Interval Scheduling DP.
- **Formula:** $T_{\text{alg}} \le 0.5\text{ seconds}$ (pure in-memory algorithm).
- **RAM Footprint:** $< 10\text{ MB}$.

### 2.6 Stage 6: Final Export Render (FFmpeg)
- **Computation:** Trimming source chunks, scaling to $1080 \times 1920$, blending crossfades, applying `loudnorm`.
- **Formula:** 
  $$T_{\text{render}} = \frac{D_{\text{reel}}}{\text{SpeedFactor}_{\text{render}}}$$
  Where $\text{SpeedFactor}_{\text{render}} \approx 2.5\times$ for 1080p H.264 encode.
  For $D_{\text{reel}} = 180\text{s}$ (3-min highlight reel), $T_{\text{render}} \approx 72.0\text{ seconds}$.

---

## 3. Total End-to-End Service Time & Sizing

For a 1-hour recording ($T_{\text{rec}} = 3,600\text{s}$), total analysis service time $T_{\text{service}}$ is:

$$T_{\text{service}} = T_{\text{probe}} + T_{\text{proxy}} + \max(T_{\text{audio}}, T_{\text{visual}}) + T_{\text{alg}}$$

$$\text{GPU Accelerated:} \quad T_{\text{service}} \approx 2 + 180 + \max(15, 68) + 0.5 \approx 250\text{ seconds} \approx \mathbf{4.2\text{ minutes}} \quad (0.07\times \text{ real-time})$$

$$\text{Standard CPU:} \quad T_{\text{service}} \approx 2 + 360 + \max(15, 160) + 0.5 \approx 522\text{ seconds} \approx \mathbf{8.7\text{ minutes}} \quad (0.145\times \text{ real-time})$$

---

## 4. Queuing Model & Worker Cluster Sizing (M/M/c Approximation)

To evaluate cluster worker sizing under concurrent load, we model the worker pool as an $M/M/c$ queuing system:
- **Arrival Rate ($\lambda$):** 20 recordings per hour ($0.0055\text{ jobs/second}$).
- **Service Rate ($\mu$):** 1 job per 522 seconds ($\mu = 0.00191\text{ jobs/second per worker}$).
- **Traffic Intensity ($\rho$):** 
  $$\rho = \frac{\lambda}{c \cdot \mu}$$
  For system stability, we require $\rho < 1$, which implies:
  $$c > \frac{\lambda}{\mu} = \frac{0.0055}{0.00191} = 2.88 \implies \mathbf{c \ge 3\text{ workers minimum}}.$$

### Sizing Recommendations:
- **Baseline Worker Pool:** 4 Workers ($c=4 \implies \rho \approx 0.72$).
  - Average queue waiting time $W_q \approx 45\text{ seconds}$.
- **Peak Load (60 jobs/hour):** KEDA scales worker pool dynamically up to $c=12$ pods ($\rho \approx 0.73$).

---

## 5. Storage Capacity Planning & Bandwidth

### Storage Requirements per 1-Hour Recording:

| Artifact | Size Calculation | Storage Required |
| :--- | :--- | :--- |
| **Raw Recording (1080p60)** | $3600\text{s} \times 15\text{Mbps} / 8$ | $6.75\text{ GB}$ |
| **Proxy Video (720p30)** | $3600\text{s} \times 2.5\text{Mbps} / 8$ | $1.12\text{ GB}$ |
| **Extracted Audio (16kHz mono)**| $3600\text{s} \times 16,000 \times 2\text{ bytes}$ | $0.11\text{ GB}$ |
| **Waveform Peaks JSON** | 36,000 bins $\times 8\text{ bytes}$ | $0.28\text{ MB}$ |
| **Candidate Thumbnails** | 30 events $\times 5\text{ frames} \times 40\text{KB}$ | $6.00\text{ MB}$ |
| **Rendered Export (3 min)** | $180\text{s} \times 12\text{Mbps} / 8$ | $0.27\text{ GB}$ |
| **Total Storage per Video** | | **$8.25\text{ GB}$** |

### 1,000 Recordings Storage Footprint:
- **Active Hot Storage (30 days):** $1,000 \times 8.25\text{ GB} = \mathbf{8.25\text{ TB}}$.
- **With 30-day raw video expiration policy (retaining only proxy + metadata + export):**
  $$1,000 \times (1.12 + 0.11 + 0.27)\text{ GB} = \mathbf{1.50\text{ TB}} \implies \mathbf{81.8\%\text{ storage cost reduction}}.$$

---

## 6. Empirical Benchmarking Protocol

The capacity model above represents engineering approximations. In Stage 1 through Stage 5, the following automated benchmarks will replace estimates with measured production coefficients:

1. **`bench_proxy_transcode`:** Measures CPU cores vs. transcode speed factor across H.264, HEVC, and VP9 inputs.
2. **`bench_audio_rms`:** Measures vectorized FFT and rolling z-score throughput across 1,000,000 sample windows.
3. **`bench_ocr_latency`:** Measures batch inference latency ($ms/frame$) on target deployment architectures (Apple Silicon MPS vs x86_64 CPU vs NVIDIA T4/A10G).
4. **`bench_render_filtergraph`:** Profiles multi-input FFmpeg concat and loudnorm rendering speed across complex 10-clip EDLs.
