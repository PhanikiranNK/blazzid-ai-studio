"""HTTP REST endpoints for video processing job management."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse

from blazzid_api.config import ApiSettings, get_api_settings
from blazzid_api.dependencies import (
    get_current_owner,
    get_job_queue,
    get_job_repository,
    get_storage,
)
from blazzid_api.schemas import (
    JobCancelResponse,
    JobListResponse,
    JobResponse,
    JobResultResponse,
)
from blazzid_jobs.errors import (
    IdempotencyConflictError,
    InvalidStateTransitionError,
)
from blazzid_jobs.models import JobRecord
from blazzid_jobs.queue import JobQueue, OutboxDispatcher
from blazzid_jobs.repository import JobRepository
from blazzid_jobs.states import JobStage, JobState
from blazzid_storage.interfaces import (
    ArtifactType,
    StorageBackend,
    StorageSizeLimitExceededError,
)

router = APIRouter(prefix="/jobs", tags=["Jobs"])

VALID_PROFILES = {"youtube_shorts", "landscape_16_9", "dynamic"}
VALID_ASPECT_RATIOS = {"9:16", "16:9"}


def _get_owned_job(job_id: str, owner_id: str, repository: JobRepository) -> JobRecord:
    """Retrieve job ensuring it belongs to requesting owner; 404s uniformly on mismatch."""
    job = repository.get_by_id(job_id)
    if job is None or job.owner_id != owner_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )
    return job


def _to_job_response(job: JobRecord, request: Request) -> JobResponse:
    base_url = str(request.base_url).rstrip("/")
    status_url = f"{base_url}/api/v1/jobs/{job.job_id}"
    result_url = (
        f"{base_url}/api/v1/jobs/{job.job_id}/result"
        if job.state == JobState.SUCCEEDED.value
        else None
    )

    return JobResponse(
        job_id=job.job_id,
        owner_id=job.owner_id,
        state=JobState(job.state),
        stage=JobStage(job.stage),
        progress_percent=job.progress_percent,
        source_filename=job.source_filename,
        target_duration_sec=job.target_duration_sec,
        assembly_profile=job.assembly_profile,
        aspect_ratio=job.aspect_ratio,
        error_code=job.error_code,
        error_message=job.error_message,
        retry_count=job.retry_count,
        created_at=job.created_at,
        updated_at=job.updated_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        cancelled_at=job.cancelled_at,
        status_url=status_url,
        result_url=result_url,
    )


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobResponse,
    summary="Submit a video processing job",
)
async def submit_job(
    request: Request,
    file: Optional[UploadFile] = File(None),
    target_duration_sec: float = Form(30.0),
    assembly_profile: str = Form("youtube_shorts"),
    max_clips: Optional[int] = Form(None),
    aspect_ratio: str = Form("9:16"),
    storage_ref: Optional[str] = Form(None),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    owner_id: str = Depends(get_current_owner),
    storage: StorageBackend = Depends(get_storage),
    repository: JobRepository = Depends(get_job_repository),
    queue: JobQueue = Depends(get_job_queue),
    settings: ApiSettings = Depends(get_api_settings),
) -> JobResponse:
    """Submit a gameplay recording for asynchronous montage generation."""
    # Validate constraints
    if not (settings.min_job_duration_sec <= target_duration_sec <= settings.max_job_duration_sec):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"target_duration_sec must be between {settings.min_job_duration_sec} and {settings.max_job_duration_sec} seconds",
        )

    if assembly_profile not in VALID_PROFILES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported assembly_profile: {assembly_profile}. Valid options: {sorted(VALID_PROFILES)}",
        )

    if aspect_ratio not in VALID_ASPECT_RATIOS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported aspect_ratio: {aspect_ratio}. Valid options: {sorted(VALID_ASPECT_RATIOS)}",
        )

    if max_clips is not None and (max_clips < 1 or max_clips > 20):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="max_clips must be between 1 and 20",
        )

    # Check idempotency first before streaming file
    if x_idempotency_key:
        existing = repository.get_by_idempotency_key(x_idempotency_key, owner_id=owner_id)
        if existing and existing.owner_id == owner_id:
            return _to_job_response(existing, request)

    job_id = f"job-{uuid.uuid4().hex[:12]}"

    # Handle input media
    if file is not None and file.filename:
        try:
            stored = storage.store_stream(
                job_id=job_id,
                filename=file.filename,
                stream=file.file,
                max_bytes=settings.max_upload_size_bytes,
                content_type=file.content_type,
            )
            source_filename = stored.filename
            source_storage_path = stored.storage_path
        except StorageSizeLimitExceededError as err:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=str(err),
            ) from err
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to ingest uploaded media: {err}",
            ) from err
    elif storage_ref:
        source_filename = storage_ref.split("/")[-1]
        source_storage_path = storage_ref
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either an uploaded video file or a storage_ref must be provided",
        )

    try:
        job = repository.create_job(
            job_id=job_id,
            source_filename=source_filename,
            source_storage_path=source_storage_path,
            target_duration_sec=target_duration_sec,
            assembly_profile=assembly_profile,
            max_clips=max_clips,
            aspect_ratio=aspect_ratio,
            owner_id=owner_id,
            idempotency_key=x_idempotency_key,
        )
    except IdempotencyConflictError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(err),
        ) from err

    # Dispatch outbox record to queue synchronously if available
    try:
        dispatcher = OutboxDispatcher(repository=repository, queue=queue)
        dispatcher.dispatch_pending(batch_size=10)
    except Exception:
        # Non-blocking for client: background outbox dispatcher or worker will pick it up
        pass

    return _to_job_response(job, request)


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get job processing status and progress",
)
def get_job_status(
    job_id: str,
    request: Request,
    owner_id: str = Depends(get_current_owner),
    repository: JobRepository = Depends(get_job_repository),
) -> JobResponse:
    """Retrieve detailed state and monotonic progress of a job."""
    job = _get_owned_job(job_id, owner_id, repository)
    return _to_job_response(job, request)


@router.get(
    "",
    response_model=JobListResponse,
    summary="List submitted jobs with pagination",
)
def list_jobs(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    state: Optional[JobState] = Query(None),
    owner_id: str = Depends(get_current_owner),
    repository: JobRepository = Depends(get_job_repository),
) -> JobListResponse:
    """List jobs filtered by optional state and strictly scoped to authenticated owner."""
    jobs, total = repository.list_jobs(
        owner_id=owner_id,
        state=state,
        limit=limit,
        offset=offset,
    )
    items = [_to_job_response(j, request) for j in jobs]
    return JobListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/{job_id}/cancel",
    response_model=JobCancelResponse,
    summary="Request job cancellation",
)
def cancel_job(
    job_id: str,
    reason: Optional[str] = Form(None),
    owner_id: str = Depends(get_current_owner),
    repository: JobRepository = Depends(get_job_repository),
) -> JobCancelResponse:
    """Cancel an ongoing or queued video processing job."""
    _get_owned_job(job_id, owner_id, repository)

    try:
        updated = repository.request_cancellation(job_id, reason=reason)
        return JobCancelResponse(
            job_id=job_id,
            state=JobState(updated.state),
            message=f"Job cancellation processed (state: {updated.state})",
            cancelled_at=updated.cancelled_at,
        )
    except InvalidStateTransitionError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(err),
        ) from err


@router.get(
    "/{job_id}/result",
    response_model=JobResultResponse,
    summary="Retrieve completed job output manifest and artifact references",
)
def get_job_result(
    job_id: str,
    owner_id: str = Depends(get_current_owner),
    repository: JobRepository = Depends(get_job_repository),
    storage: StorageBackend = Depends(get_storage),
) -> JobResultResponse:
    """Retrieve result manifest and verified artifacts for a succeeded job."""
    job = _get_owned_job(job_id, owner_id, repository)

    if job.state != JobState.SUCCEEDED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job {job_id} is in state {job.state}, not SUCCEEDED",
        )

    artifacts = storage.list_job_artifacts(job_id)
    art_dicts = [art.model_dump(mode="json") for art in artifacts]

    return JobResultResponse(
        job_id=job.job_id,
        state=JobState.SUCCEEDED,
        completed_at=job.completed_at,
        manifest=job.result_manifest,
        artifacts=art_dicts,
    )


@router.get(
    "/{job_id}/artifacts/{artifact_type}",
    summary="Download output artifact file",
)
def download_artifact(
    job_id: str,
    artifact_type: str,
    owner_id: str = Depends(get_current_owner),
    repository: JobRepository = Depends(get_job_repository),
    storage: StorageBackend = Depends(get_storage),
) -> FileResponse:
    """Download a rendered video or manifest file."""
    _get_owned_job(job_id, owner_id, repository)

    try:
        atype = ArtifactType(artifact_type)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid artifact type: {artifact_type}",
        ) from err

    path = storage.get_artifact_path(job_id, atype)
    if path is None or not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact {artifact_type} not found for job {job_id}",
        )

    media_type = "video/mp4" if path.suffix == ".mp4" else "application/json"
    return FileResponse(
        path=path,
        media_type=media_type,
        filename=path.name,
    )
