"""Unit tests for FastAPI REST API endpoints."""

from __future__ import annotations

import io
from collections.abc import Generator
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from blazzid_api.dependencies import (
    set_engine_override,
    set_job_queue_override,
    set_storage_override,
)
from blazzid_api.main import create_app
from blazzid_jobs.database import create_db_engine, init_db
from blazzid_jobs.queue import InMemoryJobQueue
from blazzid_storage.local import LocalStorageBackend


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("BLAZZID_ALLOW_ANONYMOUS_DEV", "true")
    import blazzid_api.config

    blazzid_api.config._settings = None

    db_file = tmp_path / "test_api.db"
    engine = create_db_engine(f"sqlite:///{db_file}")
    init_db(engine)

    storage = LocalStorageBackend(root_dir=tmp_path / "storage")
    queue = InMemoryJobQueue()

    set_engine_override(engine)
    set_storage_override(storage)
    set_job_queue_override(queue)

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

    set_engine_override(None)
    set_storage_override(None)
    set_job_queue_override(None)
    blazzid_api.config._settings = None


def test_health_endpoints(client: TestClient) -> None:
    res_live = client.get("/health/live")
    assert res_live.status_code == 200
    assert res_live.json() == {"status": "alive"}

    res_ready = client.get("/health/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == "ready"
    assert res_ready.json()["database_ready"] is True


def test_submit_job_multipart_success(client: TestClient) -> None:
    file_bytes = b"fake video content for testing"
    files = {"file": ("gameplay.mp4", io.BytesIO(file_bytes), "video/mp4")}
    data = {
        "target_duration_sec": "25.0",
        "assembly_profile": "youtube_shorts",
        "aspect_ratio": "9:16",
    }
    headers = {"X-Idempotency-Key": "test-key-001"}

    res = client.post("/api/v1/jobs", files=files, data=data, headers=headers)
    assert res.status_code == 202

    body = res.json()
    assert "job_id" in body
    assert body["state"] == "QUEUED"
    assert body["progress_percent"] == 0.0
    assert body["target_duration_sec"] == 25.0
    assert body["source_filename"] == "gameplay.mp4"
    assert body["status_url"].endswith(f"/api/v1/jobs/{body['job_id']}")

    job_id = body["job_id"]

    # Retrieve status via GET
    status_res = client.get(f"/api/v1/jobs/{job_id}")
    assert status_res.status_code == 200
    assert status_res.json()["job_id"] == job_id


def test_submit_job_idempotency_replay(client: TestClient) -> None:
    file_bytes = b"replay video content"
    files = {"file": ("recording.mp4", io.BytesIO(file_bytes), "video/mp4")}
    data = {"target_duration_sec": "30.0"}
    headers = {"X-Idempotency-Key": "replay-key-002"}

    # First request
    res1 = client.post("/api/v1/jobs", files=files, data=data, headers=headers)
    assert res1.status_code == 202
    job_id1 = res1.json()["job_id"]

    # Replay with same key
    files2 = {"file": ("recording.mp4", io.BytesIO(file_bytes), "video/mp4")}
    res2 = client.post("/api/v1/jobs", files=files2, data=data, headers=headers)
    assert res2.status_code == 202
    assert res2.json()["job_id"] == job_id1


def test_submit_job_validation_errors(client: TestClient) -> None:
    # Target duration out of range
    files = {"file": ("video.mp4", io.BytesIO(b"data"), "video/mp4")}
    res = client.post("/api/v1/jobs", files=files, data={"target_duration_sec": "999.0"})
    assert res.status_code == 422

    # Unsupported assembly profile
    files = {"file": ("video.mp4", io.BytesIO(b"data"), "video/mp4")}
    res = client.post("/api/v1/jobs", files=files, data={"assembly_profile": "unsupported_profile"})
    assert res.status_code == 422


def test_list_and_cancel_jobs(client: TestClient) -> None:
    files = {"file": ("v1.mp4", io.BytesIO(b"data1"), "video/mp4")}
    res_create = client.post("/api/v1/jobs", files=files, data={"target_duration_sec": "20.0"})
    assert res_create.status_code == 202
    job_id = res_create.json()["job_id"]

    # List jobs
    res_list = client.get("/api/v1/jobs")
    assert res_list.status_code == 200
    assert res_list.json()["total"] >= 1
    assert any(j["job_id"] == job_id for j in res_list.json()["items"])

    # Cancel job
    res_cancel = client.post(f"/api/v1/jobs/{job_id}/cancel", data={"reason": "User changed mind"})
    assert res_cancel.status_code == 200
    assert res_cancel.json()["state"] == "CANCELLED"


def test_result_endpoint_not_succeeded(client: TestClient) -> None:
    files = {"file": ("v.mp4", io.BytesIO(b"data"), "video/mp4")}
    res_create = client.post("/api/v1/jobs", files=files, data={"target_duration_sec": "20.0"})
    job_id = res_create.json()["job_id"]

    # Attempt to fetch result while QUEUED -> should be 409 Conflict
    res_result = client.get(f"/api/v1/jobs/{job_id}/result")
    assert res_result.status_code == 409


def test_unauthenticated_access_fails_when_anonymous_dev_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When BLAZZID_ALLOW_ANONYMOUS_DEV is false, unauthenticated requests are rejected with 401."""
    monkeypatch.setenv("BLAZZID_ALLOW_ANONYMOUS_DEV", "false")
    monkeypatch.delenv("BLAZZID_AUTH_SECRET", raising=False)
    import blazzid_api.config

    blazzid_api.config._settings = None

    db_file = tmp_path / "auth_test.db"
    engine = create_db_engine(f"sqlite:///{db_file}")
    init_db(engine)

    set_engine_override(engine)
    set_storage_override(LocalStorageBackend(root_dir=tmp_path / "storage"))
    set_job_queue_override(InMemoryJobQueue())

    app = create_app()
    with TestClient(app) as test_client:
        res = test_client.get("/api/v1/jobs")
        assert res.status_code == 401
        assert "Authentication required" in res.json()["detail"]

    set_engine_override(None)
    set_storage_override(None)
    set_job_queue_override(None)
    blazzid_api.config._settings = None


def test_cross_owner_access_isolation(client: TestClient) -> None:
    """Verify User B cannot access, list, cancel, or download User A's jobs or artifacts."""
    auth_alice = {"Authorization": "Bearer alice_token_123"}
    auth_bob = {"Authorization": "Bearer bob_token_456"}

    # User Alice submits job
    files = {"file": ("alice_video.mp4", io.BytesIO(b"alice content"), "video/mp4")}
    res = client.post(
        "/api/v1/jobs",
        files=files,
        data={"target_duration_sec": "30.0"},
        headers=auth_alice,
    )
    assert res.status_code == 202
    alice_job_id = res.json()["job_id"]
    assert res.json()["owner_id"] == "user:alice_token_123"

    # User Bob tries to GET Alice's job -> 404 (does NOT reveal existence with 403)
    res_get = client.get(f"/api/v1/jobs/{alice_job_id}", headers=auth_bob)
    assert res_get.status_code == 404
    assert res_get.json()["detail"] == f"Job {alice_job_id} not found"

    # User Bob tries to CANCEL Alice's job -> 404
    res_cancel = client.post(f"/api/v1/jobs/{alice_job_id}/cancel", headers=auth_bob)
    assert res_cancel.status_code == 404

    # User Bob tries to GET RESULT of Alice's job -> 404
    res_result = client.get(f"/api/v1/jobs/{alice_job_id}/result", headers=auth_bob)
    assert res_result.status_code == 404

    # User Bob tries to DOWNLOAD ARTIFACT of Alice's job -> 404
    res_download = client.get(
        f"/api/v1/jobs/{alice_job_id}/artifacts/RENDERED_MONTAGE", headers=auth_bob
    )
    assert res_download.status_code == 404

    # User Bob lists jobs -> must NOT include Alice's job
    res_list = client.get("/api/v1/jobs", headers=auth_bob)
    assert res_list.status_code == 200
    assert not any(j["job_id"] == alice_job_id for j in res_list.json()["items"])


def test_cross_owner_idempotency_isolation(client: TestClient) -> None:
    """Verify different owners can use the same idempotency key without collision or leak."""
    auth_alice = {"Authorization": "Bearer user_alice", "X-Idempotency-Key": "shared-key-999"}
    auth_bob = {"Authorization": "Bearer user_bob", "X-Idempotency-Key": "shared-key-999"}

    files_a = {"file": ("a.mp4", io.BytesIO(b"data a"), "video/mp4")}
    res_a = client.post(
        "/api/v1/jobs", files=files_a, data={"target_duration_sec": "20.0"}, headers=auth_alice
    )
    assert res_a.status_code == 202
    job_id_a = res_a.json()["job_id"]

    files_b = {"file": ("b.mp4", io.BytesIO(b"data b"), "video/mp4")}
    res_b = client.post(
        "/api/v1/jobs", files=files_b, data={"target_duration_sec": "20.0"}, headers=auth_bob
    )
    assert res_b.status_code == 202
    job_id_b = res_b.json()["job_id"]

    # Distinct jobs created for each owner despite identical idempotency key string
    assert job_id_a != job_id_b
    assert res_a.json()["owner_id"] == "user:user_alice"
    assert res_b.json()["owner_id"] == "user:user_bob"


def test_production_safe_startup_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify application startup fails safely in production when required auth configuration is missing."""
    monkeypatch.setenv("BLAZZID_ENV", "production")
    monkeypatch.delenv("BLAZZID_AUTH_SECRET", raising=False)
    import blazzid_api.config

    blazzid_api.config._settings = None

    db_file = tmp_path / "prod_test.db"
    engine = create_db_engine(f"sqlite:///{db_file}")

    set_engine_override(engine)
    set_storage_override(LocalStorageBackend(root_dir=tmp_path / "storage"))
    set_job_queue_override(InMemoryJobQueue())

    app = create_app()
    with pytest.raises(RuntimeError, match="Production configuration error"), TestClient(app):
        pass

    set_engine_override(None)
    set_storage_override(None)
    set_job_queue_override(None)
    blazzid_api.config._settings = None
