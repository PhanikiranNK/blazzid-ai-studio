"""FastAPI route dependencies and service wiring."""

from __future__ import annotations

import logging
from typing import Optional

import redis
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from blazzid_api.config import ApiSettings, get_api_settings
from blazzid_jobs.database import create_db_engine, create_session_factory
from blazzid_jobs.queue import InMemoryJobQueue, JobQueue, RedisJobQueue
from blazzid_jobs.repository import JobRepository
from blazzid_storage.interfaces import StorageBackend
from blazzid_storage.local import LocalStorageBackend

logger = logging.getLogger("blazzid.api.dependencies")

_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker[Session]] = None
_storage: Optional[StorageBackend] = None
_queue: Optional[JobQueue] = None


def get_engine(settings: ApiSettings = Depends(get_api_settings)) -> Engine:
    """Provide application database engine."""
    global _engine
    if _engine is None:
        _engine = create_db_engine(settings.database_url)
    return _engine


def get_session_factory(engine: Engine = Depends(get_engine)) -> sessionmaker[Session]:
    """Provide database session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = create_session_factory(engine)
    return _session_factory


def get_storage(settings: ApiSettings = Depends(get_api_settings)) -> StorageBackend:
    """Provide storage backend singleton."""
    global _storage
    if _storage is None:
        _storage = LocalStorageBackend(root_dir=settings.storage_root)
    return _storage


def get_job_repository(
    session_factory: sessionmaker[Session] = Depends(get_session_factory),
) -> JobRepository:
    """Provide repository for job persistence."""
    return JobRepository(session_factory=session_factory)


def get_job_queue(settings: ApiSettings = Depends(get_api_settings)) -> JobQueue:
    """Provide job queue implementation (Redis Streams or InMemory fallback)."""
    global _queue
    if _queue is not None:
        return _queue

    if settings.redis_url.startswith("redis://"):
        try:
            r = redis.Redis.from_url(settings.redis_url, socket_timeout=2.0)
            r.ping()
            _queue = RedisJobQueue(redis_client=r)
            return _queue
        except Exception as err:
            logger.warning("Could not connect to Redis (%s), falling back to in-memory queue", err)

    _queue = InMemoryJobQueue()
    return _queue


def set_job_queue_override(queue: Optional[JobQueue]) -> None:
    """Override queue instance for tests."""
    global _queue
    _queue = queue


def set_storage_override(storage: Optional[StorageBackend]) -> None:
    """Override storage instance for tests."""
    global _storage
    _storage = storage


def set_engine_override(engine: Optional[Engine]) -> None:
    """Override database engine for tests."""
    global _engine, _session_factory
    _engine = engine
    _session_factory = create_session_factory(engine) if engine else None


def get_current_owner(
    authorization: Optional[str] = Header(None),
    settings: ApiSettings = Depends(get_api_settings),
) -> str:
    """Extract authenticated owner identity or anonymous fallback."""
    # Production guard: production must have authentication configured
    if settings.environment == "production" and not settings.auth_secret_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication configuration missing in production",
        )

    if settings.auth_secret_token is not None:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid Bearer authentication header",
            )
        token = authorization[len("Bearer ") :].strip()
        if token == settings.auth_secret_token:
            return "user:default"
        # Support user-scoped tokens: <owner_id>:<secret>
        if ":" in token:
            user_part, secret_part = token.split(":", 1)
            if secret_part == settings.auth_secret_token and user_part.strip():
                return f"user:{user_part.strip()}"
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid credentials",
        )

    # Secret token not set (development mode)
    if authorization and authorization.startswith("Bearer "):
        token = authorization[len("Bearer ") :].strip()
        if token:
            return f"user:{token[:32]}"

    if settings.allow_anonymous_dev:
        return "anonymous"

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required: anonymous development access is disabled",
    )
