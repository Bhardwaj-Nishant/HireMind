"""
Normalization: raw Firecrawl payload -> RawJob row -> normalized Job row.

Kept separate from the source module (internshala.py) so re-running
normalization with improved mapping logic doesn't require re-scraping.
"""
import hashlib
from datetime import datetime, timezone

from shared.db.models import Job, RawJob
from shared.db.session import get_session


def _dedup_hash(source: str, title: str, company: str, url: str) -> str:
    """Best-effort dedup key: Internshala job URLs are stable per posting,
    so hash on source + url rather than title+company (which can collide
    across multiple openings at the same company)."""
    raw = f"{source}:{url}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def save_raw(source: str, payload: dict):
    """Persist the raw scrape result, unnormalized. Returns the row's id
    (not the ORM object — the session closes before this returns, so
    returning the object itself would raise DetachedInstanceError on any
    later attribute access).

    Idempotent: if this source+URL was already fetched in an earlier run,
    returns the existing row's id instead of trying to insert a duplicate
    (raw_jobs has a unique constraint on (source, source_job_id))."""
    with get_session() as session:
        existing = (
            session.query(RawJob)
            .filter_by(source=source, source_job_id=payload["url"])
            .one_or_none()
        )
        if existing:
            return existing.id

        raw_job = RawJob(
            source=source,
            source_job_id=payload["url"],  # Internshala URLs are stable per job; use as source_job_id
            raw_payload=payload,
            normalized=False,
        )
        session.add(raw_job)
        session.flush()
        return raw_job.id


def normalize_and_save(source: str, raw_job_id, payload: dict):
    """Map one raw payload into the `jobs` table. Returns the job's id, or
    None if extraction was too incomplete to use (e.g. Firecrawl couldn't
    find a title), or if it was already normalized in an earlier run."""
    extracted = payload.get("extracted") or {}
    title = extracted.get("title")
    company = extracted.get("company")

    if not title or not company:
        print(f"[normalize] skipping {payload['url']} — missing title/company in extraction")
        return None

    dedup_hash = _dedup_hash(source, title, company, payload["url"])

    with get_session() as session:
        existing = session.query(Job).filter_by(dedup_hash=dedup_hash).one_or_none()
        if existing:
            return existing.id  # already normalized, e.g. re-run after a partial failure

        job = Job(
            raw_job_id=raw_job_id,
            source=source,
            title=title,
            company=company,
            location=extracted.get("location"),
            description=extracted.get("description"),
            apply_url=payload["url"],
            posted_at=None,  # posted_date is free text from the page; parse later if needed
            recruiter_email=extracted.get("recruiter_email"),
            dedup_hash=dedup_hash,
            created_at=datetime.now(timezone.utc),
        )
        session.add(job)
        session.flush()
        job_id = job.id

        raw_job = session.get(RawJob, raw_job_id)
        if raw_job:
            raw_job.normalized = True

        return job_id