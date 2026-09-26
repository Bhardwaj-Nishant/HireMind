"""Pydantic schemas for API responses/requests — decoupled from the
SQLAlchemy models so the API's shape can evolve independently of the DB."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class JobOut(BaseModel):
    id: UUID
    source: str
    title: str
    company: str
    location: str | None
    apply_url: str
    posted_at: datetime | None
    recruiter_email: str | None = None

    class Config:
        from_attributes = True


class MatchOut(BaseModel):
    id: UUID
    score: float
    reasoning: str | None
    status: str
    created_at: datetime
    job: JobOut

    class Config:
        from_attributes = True


class MatchUpdate(BaseModel):
    status: str  # 'pending' | 'applied' | 'dismissed'


class DraftOut(BaseModel):
    id: UUID
    draft_type: str
    content: str
    gmail_draft_id: str | None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class InboxFlagOut(BaseModel):
    id: UUID
    gmail_message_id: str
    subject: str | None
    sender: str | None
    importance: str
    reasoning: str | None
    reviewed: bool
    received_at: datetime | None

    class Config:
        from_attributes = True


class InboxFlagUpdate(BaseModel):
    reviewed: bool


class DraftWithJobOut(BaseModel):
    """Draft + enough job/match context to render it standalone in a
    cross-match Drafts view (not nested under a specific match)."""

    id: UUID
    match_id: UUID
    draft_type: str
    content: str
    gmail_draft_id: str | None
    status: str
    created_at: datetime
    job_title: str
    job_company: str
    recruiter_email: str | None = None


class GeneratePayload(BaseModel):
    force: bool = False  # regenerate even if drafts already exist for this match