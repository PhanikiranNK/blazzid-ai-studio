"""Unit tests for storage backend and artifact management."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from blazzid_storage.interfaces import (
    ArtifactType,
    StoragePathTraversalError,
    StorageSizeLimitExceededError,
)
from blazzid_storage.local import LocalStorageBackend


def test_storage_path_traversal_guards(tmp_path: Path) -> None:
    storage = LocalStorageBackend(root_dir=tmp_path)

    # Job ID directory traversal attempt
    with pytest.raises(StoragePathTraversalError):
        storage._validate_job_id("../../../etc/passwd")

    with pytest.raises(StoragePathTraversalError):
        storage.create_job_working_dir("../suspicious_job")

    with pytest.raises(StoragePathTraversalError):
        storage.get_source_path("../../root_job")


def test_storage_filename_sanitization(tmp_path: Path) -> None:
    storage = LocalStorageBackend(root_dir=tmp_path)

    assert storage._sanitize_filename("valid_name.mp4") == "valid_name.mp4"
    assert storage._sanitize_filename("../../../malicious.mp4") == "malicious.mp4"
    assert storage._sanitize_filename("spaced file (1).mp4") == "spaced_file__1_.mp4"
    assert storage._sanitize_filename("...///...") == "unnamed_artifact"


def test_storage_streaming_and_size_limits(tmp_path: Path) -> None:
    storage = LocalStorageBackend(root_dir=tmp_path)
    job_id = "job-stream-001"

    # Successful stream within limit
    data = b"synthetic video content byte sequence for testing"
    stream = io.BytesIO(data)
    stored = storage.store_stream(
        job_id=job_id,
        filename="test_video.mp4",
        stream=stream,
        max_bytes=1024,
    )

    assert stored.job_id == job_id
    assert stored.filename == "test_video.mp4"
    assert stored.size_bytes == len(data)
    assert stored.artifact_type == ArtifactType.SOURCE_VIDEO
    assert stored.checksum_sha256 is not None
    assert len(stored.checksum_sha256) == 64

    # Verify physical file retrieval
    resolved_path = storage.get_source_path(job_id)
    assert resolved_path.exists()
    assert resolved_path.read_bytes() == data

    # Test size limit exceeded
    oversized = io.BytesIO(b"A" * 500)
    with pytest.raises(StorageSizeLimitExceededError):
        storage.store_stream(
            job_id="job-oversized",
            filename="large.mp4",
            stream=oversized,
            max_bytes=100,
        )


def test_storage_artifacts_and_cleanup(tmp_path: Path) -> None:
    storage = LocalStorageBackend(root_dir=tmp_path)
    job_id = "job-artifacts-002"

    # Create working scratch dir
    scratch_dir = storage.create_job_working_dir(job_id)
    assert scratch_dir.exists()

    temp_montage = scratch_dir / "rendered.mp4"
    temp_montage.write_bytes(b"montage_data")

    # Store artifact from path
    stored_artifact = storage.store_artifact_from_path(
        job_id=job_id,
        artifact_type=ArtifactType.RENDERED_MONTAGE,
        local_file_path=temp_montage,
        filename="final_highlight.mp4",
    )
    assert stored_artifact.artifact_type == ArtifactType.RENDERED_MONTAGE
    assert stored_artifact.size_bytes == len(b"montage_data")

    # Retrieve artifact path
    art_path = storage.get_artifact_path(job_id, ArtifactType.RENDERED_MONTAGE)
    assert art_path is not None
    assert art_path.exists()

    # List artifacts
    all_artifacts = storage.list_job_artifacts(job_id)
    assert len(all_artifacts) == 1
    assert all_artifacts[0].artifact_type == ArtifactType.RENDERED_MONTAGE

    # Clean scratch
    storage.clean_scratch(job_id)
    assert not scratch_dir.exists()
    # Ensure final artifact remains intact
    assert art_path.exists()
