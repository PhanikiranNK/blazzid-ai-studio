"""Database engine and session factory configuration."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from blazzid_jobs.models import Base

logger = logging.getLogger("blazzid.jobs.database")


def create_db_engine(database_url: str, echo: bool = False) -> Engine:
    """Create SQLAlchemy engine with appropriate pooling and dialect options."""
    connect_args: dict[str, Any] = {}
    is_sqlite = database_url.startswith("sqlite")

    if is_sqlite:
        connect_args["check_same_thread"] = False
        return create_engine(
            database_url,
            echo=echo,
            connect_args=connect_args,
        )

    # PostgreSQL / other production databases
    return create_engine(
        database_url,
        echo=echo,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a scoped sessionmaker bound to the given engine."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """Ensure all declared tables exist (useful for testing or initial bootstrap)."""
    Base.metadata.create_all(bind=engine)


def check_db_ready(engine: Engine) -> bool:
    """Check whether the database is accessible."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as err:
        logger.warning("Database readiness check failed: %s", err)
        return False
