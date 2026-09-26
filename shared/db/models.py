"""
HireMind shared SQLAlchemy models.

This module is the single source of truth for the schema. It's imported
by any service that needs DB access (ingestion-service, intelligence-service,
gateway-service) rather than each service defining its own copy.

Single-user project: no User/Auth tables. `credentials` stores tokens for
external platforms (Gmail, LinkedIn, etc.), not app users.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Credential(Base):
    """One row per external platform (gmail, linkedin, naukri, ...)."""

    __tablename__ = "credentials"

    id: Mapped[uuid.UUID] = _uuid_pk()
    platform: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    auth_type: Mapped[str] = mapped_column(String, nullable=False)  # 'oauth2' | 'session_cookie'
    credential_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RawJob(Base):
    """Unprocessed payload straight from an ingestion module."""

    __tablename__ = "raw_jobs"
    __table_args__ = (UniqueConstraint("source", "source_job_id", name="uq_raw_jobs_source_id"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    source: Mapped[str] = mapped_column(String, nullable=False)
    source_job_id: Mapped[str | None] = mapped_column(String)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    normalized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    job: Mapped["Job | None"] = relationship(back_populates="raw_job", uselist=False)


class Job(Base):
    """Normalized job posting, deduped across sources."""

    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    raw_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("raw_jobs.id", ondelete="SET NULL")
    )
    source: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    apply_url: Mapped[str] = mapped_column(Text, nullable=False)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recruiter_email: Mapped[str | None] = mapped_column(
        String, comment="Contact email explicitly listed on the posting itself, if any"
    )
    dedup_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    raw_job: Mapped["RawJob | None"] = relationship(back_populates="job")
    match: Mapped["Match | None"] = relationship(back_populates="job", uselist=False)


class Match(Base):
    """A job scored against your profile by intelligence-service."""

    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("job_id", name="uq_matches_job_id"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"))
    score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")  # pending|applied|dismissed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    job: Mapped["Job"] = relationship(back_populates="match")
    drafts: Mapped[list["Draft"]] = relationship(back_populates="match", cascade="all, delete-orphan")


class Draft(Base):
    """Generated artifact tied to a match: resume, cover letter, or recruiter email."""

    __tablename__ = "drafts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    match_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("matches.id", ondelete="CASCADE"))
    draft_type: Mapped[str] = mapped_column(String, nullable=False)  # resume|cover_letter|recruiter_email
    content: Mapped[str] = mapped_column(Text, nullable=False)
    gmail_draft_id: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="pending_review"
    )  # pending_review|approved|sent|discarded
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    match: Mapped["Match"] = relationship(back_populates="drafts")


class InboxFlag(Base):
    """Claude's classification of an incoming Gmail message."""

    __tablename__ = "inbox_flags"

    id: Mapped[uuid.UUID] = _uuid_pk()
    gmail_message_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    subject: Mapped[str | None] = mapped_column(String)
    sender: Mapped[str | None] = mapped_column(String)
    importance: Mapped[str] = mapped_column(String, nullable=False)  # important|not_important
    reasoning: Mapped[str | None] = mapped_column(Text)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())