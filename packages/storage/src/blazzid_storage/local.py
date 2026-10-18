"""Local filesystem storage backend implementation."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Optional

from blazzid_storage.interfaces import (
    ArtifactNotFoundError,
    ArtifactType,
    StorageBackend,
    StoragePathTraversalError,
    StorageSizeLimitExceededError,
    StoredArtifact,
)

_JOB_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]+$")
_SAFE_FILENAME_REGEX = re.compile(r"[^a-zA-Z0-9_.\-]")
_CHUNK_SIZE = 64 * 1024  # 64 KB streaming buffer


class LocalStorageBackend(StorageBackend):
    """Stores job sources, temporary files, and output artifacts on the local filesystem."""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir.resolve()
        self.jobs_dir = (self.root_dir / "jobs").resolve()
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

    def _validate_job_id(self, job_id: str) -> str:
        """Ensure job ID conforms to strict alphanumeric/hyphen/underscore syntax."""
        if not job_id or not _JOB_ID_REGEX.match(job_id):
            raise StoragePathTraversalError(f"Invalid or unsafe job identifier: {job_id!r}")
        return job_id

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize client-provided filename to prevent path traversal and unsafe chars."""
        base = os.path.basename(filename)
        cleaned = _SAFE_FILENAME_REGEX.sub("_", base).strip("._")
        if not cleaned:
            return "unnamed_artifact"
        return cleaned

    def _get_job_root(self, job_id: str) -> Path:
        """Resolve and validate the base directory for a specific job."""
        safe_id = self._validate_job_id(job_id)
        job_path = (self.jobs_dir / safe_id).resolve()
        try:
            job_path.relative_to(self.jobs_dir)
        except ValueError as err:
            raise StoragePathTraversalError(f"Job path traversal detected for: {job_id}") from err
        job_path.mkdir(parents=True, exist_ok=True)
        return job_path

    def _get_manifest_path(self, job_id: str) -> Path:
        return self._get_job_root(job_id) / "artifacts_manifest.json"

    def _load_manifest(self, job_id: str) -> list[StoredArtifact]:
        manifest_file = self._get_manifest_path(job_id)
        if not manifest_file.exists():
            return []
        try:
            with open(manifest_file, encoding="utf-8") as f:
                data = json.load(f)
                return [StoredArtifact.model_validate(item) for item in data]
        except Exception:
            return []

    def _save_manifest(self, job_id: str, artifacts: list[StoredArtifact]) -> None:
        manifest_file = self._get_manifest_path(job_id)
        temp_file = manifest_file.with_suffix(".tmp")
        data = [art.model_dump(mode="json") for art in artifacts]
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        temp_file.replace(manifest_file)

    def store_stream(
        self,
        job_id: str,
        filename: str,
        stream: BinaryIO,
        max_bytes: int,
        content_type: Optional[str] = None,
    ) -> StoredArtifact:
        """Stream an input file directly to disk while checking byte limit and computing SHA-256."""
        job_root = self._get_job_root(job_id)
        source_dir = job_root / "source"
        source_dir.mkdir(parents=True, exist_ok=True)

        sanitized = self._sanitize_filename(filename)
        dest_path = source_dir / sanitized
        artifact_id = f"art-{uuid.uuid4().hex[:12]}"

        hasher = hashlib.sha256()
        total_bytes = 0

        # Stream chunk-by-chunk to prevent high RAM consumption
        temp_dest = dest_path.with_suffix(dest_path.suffix + f".tmp-{uuid.uuid4().hex[:8]}")
        try:
            with open(temp_dest, "wb") as f_out:
                while True:
                    chunk = stream.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        raise StorageSizeLimitExceededError(
                            f"File size exceeds maximum permitted limit of {max_bytes} bytes"
                        )
                    hasher.update(chunk)
                    f_out.write(chunk)
            temp_dest.replace(dest_path)
        except Exception:
            if temp_dest.exists():
                temp_dest.unlink(missing_ok=True)
            raise

        rel_path = str(dest_path.relative_to(self.root_dir))
        artifact = StoredArtifact(
            artifact_id=artifact_id,
            job_id=job_id,
            artifact_type=ArtifactType.SOURCE_VIDEO,
            storage_path=rel_path,
            filename=sanitized,
            size_bytes=total_bytes,
            content_type=content_type or "video/mp4",
            created_at=datetime.now(timezone.utc),
            checksum_sha256=hasher.hexdigest(),
        )

        artifacts = self._load_manifest(job_id)
        artifacts.append(artifact)
        self._save_manifest(job_id, artifacts)
        return artifact

    def get_source_path(self, job_id: str, artifact_id: Optional[str] = None) -> Path:
        """Retrieve path to primary source video."""
        job_root = self._get_job_root(job_id)
        source_dir = job_root / "source"
        if not source_dir.exists():
            raise ArtifactNotFoundError(f"No source directory found for job {job_id}")

        artifacts = self._load_manifest(job_id)
        for art in artifacts:
            if art.artifact_type == ArtifactType.SOURCE_VIDEO and (
                artifact_id is None or art.artifact_id == artifact_id
            ):
                path = self.root_dir / art.storage_path
                if path.exists():
                    return path

        # Fallback to inspecting directory
        for p in source_dir.iterdir():
            if p.is_file() and not p.name.startswith("."):
                return p
        raise ArtifactNotFoundError(f"Source media not found for job {job_id}")

    def create_job_working_dir(self, job_id: str) -> Path:
        """Create and return an isolated scratch directory for the job."""
        scratch_dir = self._get_job_root(job_id) / "scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)
        return scratch_dir

    def get_job_scratch_dir(self, job_id: str) -> Path:
        """Return the scratch directory path without creating it if non-existent."""
        return self._get_job_root(job_id) / "scratch"

    def store_artifact_from_path(
        self,
        job_id: str,
        artifact_type: ArtifactType,
        local_file_path: Path,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> StoredArtifact:
        """Copy a generated file into the job's artifacts storage area."""
        if not local_file_path.exists():
            raise ArtifactNotFoundError(f"Source file to store does not exist: {local_file_path}")

        job_root = self._get_job_root(job_id)
        artifacts_dir = job_root / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        chosen_name = self._sanitize_filename(filename or local_file_path.name)
        dest_path = artifacts_dir / chosen_name

        if local_file_path.resolve() != dest_path.resolve():
            shutil.copy2(local_file_path, dest_path)

        size_bytes = dest_path.stat().st_size
        hasher = hashlib.sha256()
        with open(dest_path, "rb") as f:
            while chunk := f.read(_CHUNK_SIZE):
                hasher.update(chunk)

        mime = content_type
        if not mime:
            suffix = dest_path.suffix.lower()
            if suffix == ".mp4":
                mime = "video/mp4"
            elif suffix == ".json":
                mime = "application/json"
            elif suffix in (".wav", ".aac"):
                mime = "audio/wav"
            else:
                mime = "application/octet-stream"

        artifact_id = f"art-{uuid.uuid4().hex[:12]}"
        rel_path = str(dest_path.relative_to(self.root_dir))
        artifact = StoredArtifact(
            artifact_id=artifact_id,
            job_id=job_id,
            artifact_type=artifact_type,
            storage_path=rel_path,
            filename=chosen_name,
            size_bytes=size_bytes,
            content_type=mime,
            created_at=datetime.now(timezone.utc),
            checksum_sha256=hasher.hexdigest(),
        )

        artifacts = self._load_manifest(job_id)
        # Replace if same artifact type and name
        artifacts = [a for a in artifacts if a.storage_path != rel_path]
        artifacts.append(artifact)
        self._save_manifest(job_id, artifacts)
        return artifact

    def get_artifact_path(self, job_id: str, artifact_type: ArtifactType) -> Optional[Path]:
        """Return the absolute path of an artifact if recorded and present."""
        artifacts = self._load_manifest(job_id)
        for art in artifacts:
            if art.artifact_type == artifact_type:
                path = self.root_dir / art.storage_path
                if path.exists():
                    return path
        return None

    def list_job_artifacts(self, job_id: str) -> list[StoredArtifact]:
        """Return all persisted artifacts for a job."""
        return self._load_manifest(job_id)

    def clean_scratch(self, job_id: str) -> None:
        """Safely delete the scratch directory and its contents."""
        scratch_dir = self.get_job_scratch_dir(job_id)
        if scratch_dir.exists():
            shutil.rmtree(scratch_dir, ignore_errors=True)

    def clean_job(self, job_id: str, keep_artifacts: bool = True) -> None:
        """Clean all files for a job, optionally preserving final artifacts."""
        self.clean_scratch(job_id)
        job_root = self._get_job_root(job_id)
        if not keep_artifacts:
            shutil.rmtree(job_root, ignore_errors=True)
        else:
            source_dir = job_root / "source"
            if source_dir.exists():
                shutil.rmtree(source_dir, ignore_errors=True)
