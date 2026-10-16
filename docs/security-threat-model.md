# BLAZZID AI Studio — Security Architecture & Threat Model

## 1. Threat Modeling Methodology & Trust Boundaries

BLAZZID AI Studio employs the **STRIDE** methodology (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege) across four distinct **Trust Boundaries**:

```
[ Untrusted Client Web / Mobile ]
               │
               ▼  <--- Trust Boundary 1: Public Internet / Ingress
[ Studio API Gateway & Ingress (Auth, Rate Limiting) ]
               │
               ▼  <--- Trust Boundary 2: Authenticated Service Mesh & Internal Network
[ Processing Workers & Local Scratch Filesystems ]
               │
               ▼  <--- Trust Boundary 3: Data Stores (PostgreSQL, Redis)
[ Managed Persistence Layer ]
               │
               ▼  <--- Trust Boundary 4: External Object Storage (S3 / MinIO)
[ Cloud Storage API ]
```

---

## 2. STRIDE Threat Analysis Matrix

| Threat ID | Threat Category | Threat Scenario | Impact | Severity | Mitigation & Security Control |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TH-01** | Denial of Service / Remote Code Execution | **Malicious Media Parser Exploit:** Attacker uploads crafted MP4/MKV designed to trigger buffer overflow or integer overflow in FFmpeg/libavcodec. | Worker compromise, crash, or RCE. | **Critical** | 1. Sandboxed worker containers with unprivileged user (`uid 10001`).<br>2. FFmpeg executed with disabled network access (`-nostdin -f lavfi` disabled, external protocols blocked via `-protocol_whitelist "file,crypto"`).<br>3. `seccomp` and `AppArmor` profiles blocking dangerous syscalls. |
| **TH-02** | Elevation of Privilege | **Command Injection via Shell Expansion:** Attacker uploads file named `video.mp4; rm -rf /`. | Arbitrary command execution on host. | **Critical** | 1. Zero shell execution: strictly `subprocess.run(args_list, shell=False)`.<br>2. Filenames are discarded upon ingest; files are renamed to UUIDs (`{asset_id}.mp4`). |
| **TH-03** | Denial of Service | **Pixel Bomb / Resource Exhaustion:** Attacker uploads small compressed video that decompresses to massive 8K raw uncompressed RGB frames, causing kernel OOM. | Node crash, starvation of valid jobs. | **High** | 1. Strict `ffprobe` header validation before processing: max duration 3 hours, max resolution 3840x2160, max bitrate 50Mbps.<br>2. Hard cgroup memory limits (`resources.limits.memory`) on all pods.<br>3. Process-level timeouts (SIGKILL after deadline). |
| **TH-04** | Information Disclosure | **SSRF via Media Manifests:** Attacker submits HLS (`.m3u8`) or DASH (`.mpd`) manifest referencing internal cloud metadata endpoint (`http://169.254.169.254/latest/meta-data/`). | Cloud credentials leakage. | **Critical** | 1. Rejection of all playlist/manifest container formats. Only single-file containers (`mp4`, `mkv`, `mov`, `webm`) permitted.<br>2. Kubernetes NetworkPolicy blocks egress to link-local metadata addresses (`169.254.169.254`).<br>3. IMDSv2 enforced with hop count = 1 on AWS. |
| **TH-05** | Information Disclosure | **Broken Object Level Authorization (BOLA):** User A guesses project UUID of User B and fetches video clips or EDL. | Privacy violation, cross-tenant data leak. | **High** | 1. Mandatory authorization middleware validating `workspace_id` and project membership on every request.<br>2. PostgreSQL Row-Level Security (RLS) or repository-level query scoping (`WHERE workspace_id = :current_user_workspace`). |
| **TH-06** | Information Disclosure | **Unrestricted Object Storage Access:** Media bucket configured with public read or persistent presigned URLs. | Unauthorized public exposure of user gaming footage. | **High** | 1. S3 bucket configured with **Block Public Access: Enabled**.<br>2. All access mediated via short-lived (maximum 15 minutes) presigned URLs signed with restricted IAM role.<br>3. Direct S3 access logs enabled and audited. |
| **TH-07** | Tampering / XSS | **Untrusted OCR & Model Output Injection:** OCR engine parses adversarial in-game player name containing `<script>alert(1)</script>` or SQL injection payloads, which are rendered unescaped in Studio UI. | Cross-Site Scripting (XSS) in editor's browser. | **Medium** | 1. All OCR and detector strings treated as untrusted text.<br>2. React auto-escaping on DOM insertion; Content Security Policy (CSP) blocking inline scripts.<br>3. Parametric SQL queries exclusively (no string interpolation). |
| **TH-08** | Information Disclosure | **Scratch Space Leakage:** Residual video chunks and extracted frames remain in `/tmp/scratch` across jobs or container restarts. | Disk space exhaustion, cross-job data residue. | **Medium** | 1. Contextual Python cleanup managers (`with TemporaryDirectory() as tmp_dir:`).<br>2. Local scratch mounted on ephemeral `emptyDir` volumes wiped automatically on pod termination.<br>3. Container entrypoint runs orphan scratch purge. |
| **TH-09** | Information Disclosure | **Secrets in Git / Logs:** Developer commits AWS credentials or API tokens; API logs include JWT tokens or S3 signatures. | Credential compromise. | **High** | 1. Pre-commit hooks (`gitleaks`) scanning for secrets.<br>2. Structured JSON logging with automated redaction filters for `Authorization`, `password`, `secret`, and `token` fields.<br>3. Kubernetes Secrets injected strictly via environment variables or mounted files (never baked into container images). |

---

## 3. Defense-in-Depth Implementation Details

### 3.1 Hardened FFmpeg Execution Pattern
All FFmpeg and ffprobe invocations must pass through an audited utility wrapper:

```python
import subprocess
from typing import List

def run_hardened_ffmpeg(args: List[str], timeout_seconds: int = 300) -> subprocess.CompletedProcess:
    """
    Executes FFmpeg with defensive sandbox arguments:
    - shell=False prevents shell interpolation
    - Disables network protocols to block SSRF
    - Drops interactive input
    """
    sanitized_command = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-nostats",
        "-protocol_whitelist", "file,crypto", # Block http, https, gopher, tcp, etc.
        *args
    ]
    
    return subprocess.run(
        sanitized_command,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=True
    )
```

### 3.2 Media Header Verification Protocol
Before any video is accepted for processing, the `IngestPreprocessWorker` verifies structural invariants:

```python
def validate_media_container(ffprobe_metadata: dict) -> None:
    # 1. Verify container format
    format_name = ffprobe_metadata.get("format", {}).get("format_name", "")
    allowed_formats = {"mov,mp4,m4a,3gp,3g2,mj2", "matroska,webm", "mp4"}
    if not any(f in format_name for f in allowed_formats):
        raise SecurityValidationError(f"Disallowed container format: {format_name}")
        
    # 2. Verify streams
    streams = ffprobe_metadata.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    if len(video_streams) == 0:
        raise SecurityValidationError("No video stream found in uploaded media.")
        
    v = video_streams[0]
    width = int(v.get("width", 0))
    height = int(v.get("height", 0))
    if width > 3840 or height > 2160:
        raise SecurityValidationError(f"Resolution exceeds 4K limit: {width}x{height}")
        
    # 3. Verify duration
    duration = float(ffprobe_metadata.get("format", {}).get("duration", 0))
    if duration > 10800: # 3 hours
        raise SecurityValidationError(f"Duration exceeds 3-hour limit: {duration}s")
```

---

## 4. Least-Privilege IAM & Kubernetes Security Context

### Container Security Context (Pod Spec):
```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  runAsGroup: 10001
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: true
  capabilities:
    drop:
      - ALL
```

### S3 Least-Privilege Bucket Policy (IAM Policy):
Workers receive credentials allowing read and write access strictly to their assigned organization prefix:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:AbortMultipartUpload"
      ],
      "Resource": "arn:aws:s3:::blazzid-media-bucket/org_${aws:PrincipalTag/OrgId}/*"
    }
  ]
}
```
