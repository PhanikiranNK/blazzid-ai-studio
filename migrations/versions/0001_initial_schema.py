"""0001 initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-18 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

json_type = sa.JSON().with_variant(JSONB, "postgresql")


def upgrade() -> None:
    # jobs table
    op.create_table(
        "jobs",
        sa.Column("job_id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("owner_id", sa.String(length=128), nullable=False, default="anonymous"),
        sa.Column("idempotency_key", sa.String(length=256), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False, default="QUEUED"),
        sa.Column("stage", sa.String(length=32), nullable=False, default="VALIDATING_INPUT"),
        sa.Column("progress_percent", sa.Float(), nullable=False, default=0.0),
        sa.Column("source_filename", sa.String(length=256), nullable=False),
        sa.Column("source_storage_path", sa.String(length=512), nullable=False),
        sa.Column("target_duration_sec", sa.Float(), nullable=False),
        sa.Column(
            "assembly_profile", sa.String(length=64), nullable=False, default="youtube_shorts"
        ),
        sa.Column("max_clips", sa.Integer(), nullable=True),
        sa.Column("aspect_ratio", sa.String(length=16), nullable=False, default="9:16"),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=1024), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, default=0),
        sa.Column("max_retries", sa.Integer(), nullable=False, default=3),
        sa.Column("worker_id", sa.String(length=128), nullable=True),
        sa.Column("worker_lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_manifest", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, default=1),
    )
    op.create_index("ix_jobs_owner_id", "jobs", ["owner_id"])
    op.create_index("ix_jobs_state", "jobs", ["state"])
    op.create_index(
        "ix_jobs_owner_idempotency_key", "jobs", ["owner_id", "idempotency_key"], unique=True
    )
    op.create_index("ix_jobs_worker_lease_until", "jobs", ["worker_lease_until"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])
    op.create_index("ix_jobs_owner_state", "jobs", ["owner_id", "state"])
    op.create_index("ix_jobs_created_state", "jobs", ["created_at", "state"])

    # job_attempts table
    op.create_table(
        "job_attempts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column(
            "job_id",
            sa.String(length=64),
            sa.ForeignKey("jobs.job_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.String(length=1024), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_job_attempts_job_id", "job_attempts", ["job_id"])

    # outbox table
    op.create_table(
        "outbox",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", json_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_outbox_event_id", "outbox", ["event_id"], unique=True)
    op.create_index("ix_outbox_job_id", "outbox", ["job_id"])
    op.create_index("ix_outbox_event_type", "outbox", ["event_type"])
    op.create_index("ix_outbox_created_at", "outbox", ["created_at"])
    op.create_index("ix_outbox_published_at", "outbox", ["published_at"])
    op.create_index("ix_outbox_pending", "outbox", ["published_at", "created_at"])


def downgrade() -> None:
    op.drop_table("outbox")
    op.drop_table("job_attempts")
    op.drop_table("jobs")
