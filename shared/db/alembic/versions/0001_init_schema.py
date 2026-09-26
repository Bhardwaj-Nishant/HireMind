"""init schema

Revision ID: 0001
Revises:
Create Date: 2026-08-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')

    op.create_table(
        "credentials",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("platform", sa.String, nullable=False, unique=True),
        sa.Column("auth_type", sa.String, nullable=False),
        sa.Column("credential_data", JSONB, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "raw_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("source_job_id", sa.String),
        sa.Column("raw_payload", JSONB, nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("normalized", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("source", "source_job_id", name="uq_raw_jobs_source_id"),
    )
    op.create_index(
        "idx_raw_jobs_normalized", "raw_jobs", ["normalized"], postgresql_where=sa.text("normalized = false")
    )

    op.create_table(
        "jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("raw_job_id", UUID(as_uuid=True), sa.ForeignKey("raw_jobs.id", ondelete="SET NULL")),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("company", sa.String, nullable=False),
        sa.Column("location", sa.String),
        sa.Column("description", sa.Text),
        sa.Column("apply_url", sa.Text, nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("dedup_hash", sa.String, nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_jobs_source", "jobs", ["source"])
    op.create_index("idx_jobs_posted_at", "jobs", ["posted_at"])

    op.create_table(
        "matches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Numeric(5, 2), nullable=False),
        sa.Column("reasoning", sa.Text),
        sa.Column("status", sa.String, nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("job_id", name="uq_matches_job_id"),
    )
    op.create_index("idx_matches_status", "matches", ["status"])
    op.create_index("idx_matches_score", "matches", ["score"])

    op.create_table(
        "drafts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("match_id", UUID(as_uuid=True), sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("draft_type", sa.String, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("gmail_draft_id", sa.String),
        sa.Column("status", sa.String, nullable=False, server_default="pending_review"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_drafts_match_id", "drafts", ["match_id"])
    op.create_index("idx_drafts_status", "drafts", ["status"])

    op.create_table(
        "inbox_flags",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("gmail_message_id", sa.String, nullable=False, unique=True),
        sa.Column("subject", sa.String),
        sa.Column("sender", sa.String),
        sa.Column("importance", sa.String, nullable=False),
        sa.Column("reasoning", sa.Text),
        sa.Column("reviewed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("received_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_inbox_flags_reviewed", "inbox_flags", ["reviewed"], postgresql_where=sa.text("reviewed = false"))


def downgrade() -> None:
    op.drop_table("inbox_flags")
    op.drop_table("drafts")
    op.drop_table("matches")
    op.drop_table("jobs")
    op.drop_table("raw_jobs")
    op.drop_table("credentials")