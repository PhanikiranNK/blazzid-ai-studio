# BLAZZID AI Studio — API & Event Contracts Specification

## 1. Contract Design Principles

All internal and external communication in BLAZZID AI Studio adheres to strict, versioned contract standards:

1. **Protocol Separation:** 
   - **REST (HTTPS):** Synchronous control plane, project management, timeline queries, and state mutations.
   - **Server-Sent Events (SSE):** Real-time, unidirectional server-to-client job progress and timeline invalidation notifications.
   - **Message Queues (Redis Streams / JSON):** Asynchronous, decoupled inter-service worker task execution.
2. **Timestamp & Interval Semantics:**
   - **Units:** All timestamps are standardized as IEEE 754 64-bit floating point **seconds with millisecond precision** (e.g., `124.532`). Frame numbers are included as optional secondary metadata.
   - **Intervals:** All time intervals are strictly **half-open: $[t_{\text{start}}, t_{\text{end}})$**. This ensures mathematical additivity without frame duplication:
     $$\text{duration} = t_{\text{end}} - t_{\text{start}}$$
3. **Score & Confidence Scales:**
   - **Confidence Scores:** Calibrated probabilities $\in [0.0000, 1.0000]$.
   - **Rank Scores:** Normalized composite utility values $\in [0.0000, 100.0000]$.
4. **Schema Versioning:**
   - All REST APIs are namespaced: `/api/v1/*`.
   - All message payloads include a top-level `"schema_version": "1.0.0"` property following Semantic Versioning.

---

## 2. REST API Specification

### 2.1 Project Creation & Management

#### `POST /api/v1/projects`
Creates a new highlight project.

**Request Payload:**
```json
{
  "title": "Championship Scrims - Day 3",
  "game_title": "Brawl Stars",
  "target_duration_seconds": 180,
  "aspect_ratio": "16:9",
  "metadata": {
    "game_mode": "Gem Grab",
    "brawlers_used": ["Colt", "Mortis", "Spike"]
  }
}
```

**Response (HTTP 201 Created):**
```json
{
  "project_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "title": "Championship Scrims - Day 3",
  "game_title": "Brawl Stars",
  "status": "CREATED",
  "target_duration_seconds": 180,
  "aspect_ratio": "16:9",
  "created_at": "2026-10-16T13:45:00.000Z",
  "updated_at": "2026-10-16T13:45:00.000Z"
}
```

---

### 2.2 Asset Upload & Presigned Multipart URLs

#### `POST /api/v1/projects/{project_id}/assets/initiate-upload`
Initiates a resumable multipart upload directly to object storage.

**Request Payload:**
```json
{
  "filename": "scrim_recording_01.mp4",
  "file_size_bytes": 4294967296,
  "part_count": 5,
  "sha256_checksum": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
}
```

**Response (HTTP 200 OK):**
```json
{
  "asset_id": "c8f5647a-18b3-4f91-88df-6a3f9e2b10a1",
  "upload_id": "s3-multipart-upload-uuid-88234",
  "part_urls": [
    {
      "part_number": 1,
      "url": "https://storage.blazzid.internal/media-raw/upload_1?token=exp_9923"
    },
    {
      "part_number": 2,
      "url": "https://storage.blazzid.internal/media-raw/upload_2?token=exp_9923"
    }
  ],
  "expires_at": "2026-10-16T14:45:00.000Z"
}
```

#### `POST /api/v1/assets/{asset_id}/complete-upload`
Confirms binary upload completion and enqueues inspection.

**Request Payload:**
```json
{
  "upload_id": "s3-multipart-upload-uuid-88234",
  "parts": [
    { "part_number": 1, "etag": "\"d41d8cd98f00b204e9800998ecf8427e\"" },
    { "part_number": 2, "etag": "\"6a821e202c638e9c1c4f513d80d52b12\"" }
  ]
}
```

---

### 2.3 Analysis Trigger & Status Query

#### `POST /api/v1/projects/{project_id}/analyze`
Starts the multi-stage analysis and highlight generation pipeline.

**Request Payload:**
```json
{
  "config": {
    "detection_sensitivity": "HIGH",
    "include_audio_cheers": true,
    "ocr_kill_feed": true,
    "max_reel_duration_seconds": 180,
    "min_clip_duration_seconds": 6.0,
    "max_clip_duration_seconds": 18.0
  }
}
```

**Response (HTTP 202 Accepted):**
```json
{
  "job_id": "f2a1b92c-5678-4321-abcd-9876543210ef",
  "project_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "QUEUED",
  "current_stage": "PREPROCESSING",
  "sse_stream_url": "/api/v1/jobs/f2a1b92c-5678-4321-abcd-9876543210ef/events"
}
```

---

### 2.4 Timeline & Candidates Retrieval

#### `GET /api/v1/projects/{project_id}/timeline`
Returns all detected candidates, audio waveform peaks, and current EDL for interactive editing.

**Response (HTTP 200 OK):**
```json
{
  "schema_version": "1.0.0",
  "project_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "asset": {
    "asset_id": "c8f5647a-18b3-4f91-88df-6a3f9e2b10a1",
    "duration_seconds": 3600.000,
    "fps": 60.0,
    "proxy_stream_url": "https://storage.blazzid.internal/proxies/proxy_720p.mp4",
    "waveform_data_url": "https://storage.blazzid.internal/waveforms/peaks.json"
  },
  "candidates": [
    {
      "candidate_id": "71a2b3c4-d5e6-4f7a-8b9c-0d1e2f3a4b5c",
      "event_type": "TEAM_WIPE",
      "interval": {
        "start_seconds": 412.350,
        "end_seconds": 428.100,
        "climax_seconds": 421.200
      },
      "rank_score": 94.50,
      "confidence": 0.9412,
      "is_selected": true,
      "provenance": {
        "visual_detector": {
          "type": "HUD_KILL_BANNER",
          "timestamp": 421.200,
          "confidence": 0.98
        },
        "ocr": {
          "raw_text": "Triple Elimination! Mortis",
          "confidence": 0.92
        },
        "audio": {
          "rms_spike_db": 14.2,
          "timestamp": 422.000
        }
      }
    }
  ],
  "active_edl": {
    "version": 1,
    "total_duration_seconds": 78.450,
    "clips": [
      {
        "clip_id": "clip_01",
        "candidate_id": "71a2b3c4-d5e6-4f7a-8b9c-0d1e2f3a4b5c",
        "source_asset_id": "c8f5647a-18b3-4f91-88df-6a3f9e2b10a1",
        "timeline_in_seconds": 0.000,
        "timeline_out_seconds": 15.750,
        "source_in_seconds": 412.350,
        "source_out_seconds": 428.100,
        "transition_in": { "type": "DISSOLVE", "duration_seconds": 0.5 },
        "audio_level_db": 0.0
      }
    ]
  }
}
```

---

### 2.5 Creator EDL Modification

#### `PUT /api/v1/projects/{project_id}/edl`
Saves an updated timeline modified by the creator.

**Request Payload:**
```json
{
  "client_version": 1,
  "clips": [
    {
      "clip_id": "clip_01",
      "candidate_id": "71a2b3c4-d5e6-4f7a-8b9c-0d1e2f3a4b5c",
      "source_in_seconds": 414.000,
      "source_out_seconds": 427.500,
      "transition_in": { "type": "CUT" },
      "audio_level_db": +1.5
    }
  ]
}
```

**Response (HTTP 200 OK):**
```json
{
  "project_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "version": 2,
  "total_duration_seconds": 13.500,
  "saved_at": "2026-10-16T13:52:10.000Z"
}
```

---

### 2.6 Render & Export Trigger

#### `POST /api/v1/projects/{project_id}/exports`
Triggers final rendering of the active EDL.

**Request Payload:**
```json
{
  "edl_version": 2,
  "preset": "YOUTUBE_SHORTS_1080P",
  "options": {
    "target_width": 1080,
    "target_height": 1920,
    "burn_captions": false,
    "normalize_loudness_ebu_r128": true
  }
}
```

**Response (HTTP 202 Accepted):**
```json
{
  "export_id": "3c98a12d-7b6e-4e3a-9f12-0a1b2c3d4e5f",
  "status": "QUEUED",
  "estimated_duration_seconds": 45,
  "poll_url": "/api/v1/exports/3c98a12d-7b6e-4e3a-9f12-0a1b2c3d4e5f"
}
```

---

## 3. Server-Sent Events (SSE) Contract

Live progress updates are streamed to the web client via `GET /api/v1/jobs/{job_id}/events`.

### Event Types:

#### `event: job_progress`
```json
{
  "job_id": "f2a1b92c-5678-4321-abcd-9876543210ef",
  "stage": "VISUAL_ANALYSIS",
  "percent_complete": 64.5,
  "processed_duration_seconds": 2322.0,
  "total_duration_seconds": 3600.0,
  "eta_seconds": 35.0
}
```

#### `event: job_completed`
```json
{
  "job_id": "f2a1b92c-5678-4321-abcd-9876543210ef",
  "status": "SUCCESS",
  "candidates_detected": 14,
  "selected_highlights": 6,
  "completed_at": "2026-10-16T13:50:22.000Z"
}
```

#### `event: job_failed`
```json
{
  "job_id": "f2a1b92c-5678-4321-abcd-9876543210ef",
  "status": "FAILED",
  "error_code": "MEDIA_CONTAINER_CORRUPT",
  "error_message": "Missing moov atom at end of MP4 container.",
  "is_retryable": false
}
```

---

## 4. Asynchronous Message Queue Contracts (Redis Streams)

### 4.1 Queue: `queue:preprocess`
Dispatched when raw upload completes.

```json
{
  "schema_version": "1.0.0",
  "job_type": "PREPROCESS_MEDIA",
  "task_id": "tsk_01",
  "asset_id": "c8f5647a-18b3-4f91-88df-6a3f9e2b10a1",
  "raw_s3_key": "raw/org_1/proj_1/asset_1/recording.mp4",
  "idempotency_key": "preprocess:c8f5647a:v1",
  "dispatched_at": "2026-10-16T13:46:00.000Z"
}
```

### 4.2 Queue: `queue:audio_analysis`
Dispatched when audio extraction completes.

```json
{
  "schema_version": "1.0.0",
  "job_type": "ANALYZE_AUDIO",
  "asset_id": "c8f5647a-18b3-4f91-88df-6a3f9e2b10a1",
  "audio_s3_key": "audio/org_1/proj_1/asset_1/audio.wav",
  "parameters": {
    "window_size_ms": 100,
    "hop_length_ms": 50,
    "rms_threshold_std": 2.5
  }
}
```

### 4.3 Queue: `queue:visual_analysis`
Dispatched for parallel frame analysis.

```json
{
  "schema_version": "1.0.0",
  "job_type": "ANALYZE_VISUAL",
  "asset_id": "c8f5647a-18b3-4f91-88df-6a3f9e2b10a1",
  "proxy_s3_key": "proxies/org_1/proj_1/asset_1/proxy_720p.mp4",
  "parameters": {
    "sparse_fps": 1.0,
    "dense_fps": 15.0,
    "game_profile": "BRAWL_STARS"
  }
}
```

### 4.4 Queue: `queue:render`
Dispatched when final render is requested.

```json
{
  "schema_version": "1.0.0",
  "job_type": "RENDER_EXPORT",
  "export_id": "3c98a12d-7b6e-4e3a-9f12-0a1b2c3d4e5f",
  "edl_id": "edl_992",
  "source_assets": [
    {
      "asset_id": "c8f5647a-18b3-4f91-88df-6a3f9e2b10a1",
      "s3_key": "raw/org_1/proj_1/asset_1/recording.mp4"
    }
  ],
  "edl_spec": {
    "clips": [
      {
        "source_asset_id": "c8f5647a-18b3-4f91-88df-6a3f9e2b10a1",
        "in_seconds": 414.0,
        "out_seconds": 427.5
      }
    ],
    "output": {
      "codec": "libx264",
      "width": 1080,
      "height": 1920,
      "crf": 20,
      "audio_codec": "aac",
      "audio_bitrate": "192k"
    }
  },
  "destination_s3_key": "exports/org_1/proj_1/export_3c98/final.mp4"
}
```
