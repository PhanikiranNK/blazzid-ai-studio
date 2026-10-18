/**
 * Strict TypeScript types for BLAZZID AI Studio FastAPI REST backend.
 */

export type JobState =
  | "QUEUED"
  | "PROCESSING"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCEL_REQUESTED"
  | "CANCELLED";

export type JobStage =
  | "VALIDATING_INPUT"
  | "PROBING_MEDIA"
  | "PREPROCESSING"
  | "DETECTING_EVENTS"
  | "RANKING_HIGHLIGHTS"
  | "PLANNING_EDIT"
  | "RENDERING"
  | "VALIDATING_OUTPUT"
  | "FINALIZING";

export type AssemblyProfile = "youtube_shorts" | "landscape_16_9" | "dynamic";
export type AspectRatio = "9:16" | "16:9";

export interface JobResponse {
  job_id: string;
  owner_id: string;
  state: JobState;
  stage: JobStage;
  progress_percent: number;
  source_filename: string;
  target_duration_sec: number;
  assembly_profile: AssemblyProfile | string;
  aspect_ratio: AspectRatio | string;
  error_code: string | null;
  error_message: string | null;
  retry_count: number;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  status_url: string;
  result_url: string | null;
}

export interface JobListResponse {
  items: JobResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface JobCancelResponse {
  job_id: string;
  state: JobState;
  message: string;
  cancelled_at: string | null;
}

export interface ArtifactMeta {
  artifact_type: string;
  filename: string;
  size_bytes: number;
  content_type: string;
  download_url: string;
}

export interface HighlightClipItem {
  clip_id: string;
  source_start_sec: number;
  source_end_sec: number;
  duration_sec: number;
  score: number;
  label?: string;
  reason?: string;
}

export interface EditManifest {
  job_id?: string;
  schema_version?: string;
  created_at?: string;
  source_media?: {
    duration_sec?: number;
    width?: number;
    height?: number;
    fps?: number;
  };
  output_profile?: {
    name?: string;
    aspect_ratio?: string;
    target_duration_sec?: number;
  };
  clips?: HighlightClipItem[];
  timeline_duration_sec?: number;
  selected_candidates_count?: number;
}

export interface JobResultResponse {
  job_id: string;
  state: JobState;
  completed_at: string | null;
  manifest: EditManifest | null;
  artifacts: ArtifactMeta[];
}

export interface HealthResponse {
  status: string;
  database_ready: boolean;
  redis_ready: boolean;
  timestamp: string;
}

export interface SubmitJobParams {
  file: File;
  target_duration_sec: number;
  assembly_profile: AssemblyProfile;
  aspect_ratio: AspectRatio;
  max_clips?: number;
}
