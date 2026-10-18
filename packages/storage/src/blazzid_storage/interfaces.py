"""Storage interfaces, data models, and domain errors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import BinaryIO, Optional

from pydantic import BaseModel, ConfigDict, Field

from blazzid_core.errors import BlazzidError


class ArtifactType(str, Enum):
    """Categorization of artifacts produced or consumed by jobs."""

    SOURCE_VIDEO = "source_video"
    SCRATCH_DIR = "scratch_dir"
    EXTRACTED_AUDIO = "extracted_audio"
    SCENE_METRICS = "scene_metrics"
    CANDIDATES_JSON = "candidates_json"
    EDIT_PLAN_JSON = "edit_plan_json"
    RENDERED_MONTAGE = "rendered_montage"
    EDIT_MANIFEST_JSON = "edit_manifest_json"


class StoredArtifact(BaseModel):
    """Metadata record for a stored artifact."""

    model_config = ConfigDict(frozen=True)

    artifact_id: str = Field(description="Unique identifier for the artifact")
    job_id: str = Field(description="ID of the job that owns this artifact")
    artifact_type: ArtifactType = Field(description="Type classification of the artifact")
    storage_path: str = Field(description="Relative or storage-internal URI of the artifact")
    filename: str = Field(description="Sanitized base filename")
    size_bytes: int = Field(ge=0, description="Size of the stored file in bytes")
    content_type: str = Field(default="application/octet-stream", description="MIME type")
    created_at: datetime = Field(description="Timestamp when artifact was persisted")
    checksum_sha256: Optional[str] = Field(
        default=None, description="SHA-256 hex digest if computed"
    )


class StorageError(BlazzidError):
    """Base exception for storage errors."""


class StoragePathTraversalError(StorageError):
    """Raised when an access attempt breaches the configured storage root."""


class StorageSizeLimitExceededError(StorageError):
    """Raised when an upload exceeds the maximum allowed byte threshold."""


class ArtifactNotFoundError(StorageError):
    """Raised when a requested artifact does not exist."""


class StorageBackend(ABC):
    """Abstract storage backend for managing job media and artifacts."""

    @abstractmethod
    def store_stream(
        self,
        job_id: str,
        filename: str,
        stream: BinaryIO,
        max_bytes: int,
        content_type: Optional[str] = None,
    ) -> StoredArtifact:
        """Stream an input file to disk with strict size limits and traversal checks."""

    @abstractmethod
    def get_source_path(self, job_id: str, artifact_id: Optional[str] = None) -> Path:
        """Get the filesystem path to the primary source recording."""

    @abstractmethod
    def create_job_working_dir(self, job_id: str) -> Path:
        """Create and return the isolated scratch directory for the job."""

    @abstractmethod
    def get_job_scratch_dir(self, job_id: str) -> Path:
        """Return the scratch directory path for the job."""

    @abstractmethod
    def store_artifact_from_path(
        self,
        job_id: str,
        artifact_type: ArtifactType,
        local_file_path: Path,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> StoredArtifact:
        """Persist a locally generated file into job artifact storage."""

    @abstractmethod
    def get_artifact_path(self, job_id: str, artifact_type: ArtifactType) -> Optional[Path]:
        """Get the absolute path to a specific artifact if it exists."""

    @abstractmethod
    def list_job_artifacts(self, job_id: str) -> list[StoredArtifact]:
        """List all registered artifacts for a job."""

    @abstractmethod
    def clean_scratch(self, job_id: str) -> None:
        """Remove temporary scratch files for a job while preserving source and artifacts."""

    @abstractmethod
    def clean_job(self, job_id: str, keep_artifacts: bool = True) -> None:
        """Clean all files for a job, optionally keeping rendered artifacts."""
