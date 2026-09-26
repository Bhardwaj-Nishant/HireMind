"""
gateway-service — the single API entry point for the (future) dashboard.

No auth: this is a single-user personal project running on your own
machine/server, per your earlier decision. If this is ever exposed
beyond localhost, add auth before doing so.
"""
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import (
    DraftOut,
    DraftWithJobOut,
    GeneratePayload,
    InboxFlagOut,
    InboxFlagUpdate,
    MatchOut,
    MatchUpdate,
)
from shared.db.models import Draft, InboxFlag, Job, Match
from shared.db.session import get_session

app = FastAPI(title="HireMind Gateway", version="0.1.0")

# Dev-friendly CORS — tighten this once the dashboard has a fixed origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/matches", response_model=list[MatchOut])
def list_matches(
    status: str | None = Query(default=None, description="Filter by match status"),
    min_score: float | None = Query(default=None),
    limit: int = Query(default=50, le=200),
):
    with get_session() as session:
        query = session.query(Match).join(Job, Match.job_id == Job.id)
        if status:
            query = query.filter(Match.status == status)
        if min_score is not None:
            query = query.filter(Match.score >= min_score)
        matches = query.order_by(Match.score.desc()).limit(limit).all()

        # Force-load job relationship + build response before session closes
        return [MatchOut.model_validate(m) for m in matches]


@app.patch("/matches/{match_id}", response_model=MatchOut)
def update_match(match_id: UUID, update: MatchUpdate):
    if update.status not in ("pending", "applied", "dismissed"):
        raise HTTPException(400, "status must be one of: pending, applied, dismissed")

    with get_session() as session:
        match = session.get(Match, match_id)
        if not match:
            raise HTTPException(404, "Match not found")
        match.status = update.status
        session.flush()
        return MatchOut.model_validate(match)


@app.post("/matches/refresh")
def refresh_matches(
    source: str = Query(default="internshala", pattern="^(internshala|unstop|linkedin)$"),
    max_jobs: int = Query(default=10, le=50),
    match_limit: int = Query(default=20, le=100),
    work_type: str = Query(default="internship", pattern="^(internship|job)$"),
    location: str = Query(default="any", pattern="^(remote|onsite|any)$"),
    keywords: str | None = Query(default=None, description="Comma-separated category slugs, overrides resume-derived search"),
    max_age_days: int = Query(default=1, le=30, description="Only fetch postings at most this many days old"),
    force: bool = Query(default=False, description="LinkedIn only: bypass the hourly rate gate"),
):
    """Scrapes new listings from the given source (category derived from
    the resume unless `keywords` is given) and scores any newly-unmatched
    jobs against the resume, synchronously. Called by the dashboard's
    'Fetch more matches' button. Can take a while (scraping + several LLM
    calls) — the dashboard shows a loading state while this runs."""
    from shared.ingestion.normalize import normalize_and_save, save_raw
    from shared.ingestion.registry import get_source
    from shared.matching.matcher import run_matching_cycle

    source_module = get_source(source)
    keyword_list = [k.strip() for k in keywords.split(",")] if keywords else None
    extra_kwargs = {"force": force} if source == "linkedin" else {}

    try:
        payloads = source_module.fetch_all(
            max_jobs=max_jobs, work_type=work_type, location_mode=location, keywords=keyword_list,
            max_age_days=max_age_days, **extra_kwargs,
        )
    except Exception as exc:  # noqa: BLE001 — surface scraping errors to the caller
        # LinkedIn's rate gate raises a RuntimeError subclass with a clear
        # wait-time message — surface it as 429 rather than a generic 502.
        status = 429 if type(exc).__name__ == "RateLimitedError" else 502
        raise HTTPException(status, f"Scraping failed: {exc}")

    new_jobs = 0
    for payload in payloads:
        raw_job_id = save_raw(source, payload)
        job_id = normalize_and_save(source, raw_job_id, payload)
        if job_id:
            new_jobs += 1

    try:
        run_matching_cycle(limit=match_limit)
    except Exception as exc:  # noqa: BLE001 — surface matching errors to the caller
        raise HTTPException(502, f"Matching failed: {exc}")

    return {"source": source, "scraped": len(payloads), "new_jobs": new_jobs}


@app.get("/matches/{match_id}/drafts", response_model=list[DraftOut])
def get_match_drafts(match_id: UUID):
    with get_session() as session:
        match = session.get(Match, match_id)
        if not match:
            raise HTTPException(404, "Match not found")
        drafts = session.query(Draft).filter_by(match_id=match_id).all()
        return [DraftOut.model_validate(d) for d in drafts]


@app.post("/matches/{match_id}/generate", response_model=list[DraftOut])
def generate_match_drafts(match_id: UUID, payload: GeneratePayload = GeneratePayload()):
    """Generates resume/cover letter/recruiter email drafts for this match
    on demand (whichever types don't exist yet, or all of them if
    force=True). Calls the LLM synchronously — the request can take a few
    seconds while all three drafts are generated."""
    from shared.generation.generator import generate_for_match

    with get_session() as session:
        if not session.get(Match, match_id):
            raise HTTPException(404, "Match not found")

    try:
        generate_for_match(match_id, force=payload.force)
    except FileNotFoundError as exc:
        raise HTTPException(500, f"Resume not configured: {exc}")
    except Exception as exc:  # noqa: BLE001 — surface LLM/provider errors to the caller
        raise HTTPException(502, f"Generation failed: {exc}")

    with get_session() as session:
        drafts = session.query(Draft).filter_by(match_id=match_id).all()
        return [DraftOut.model_validate(d) for d in drafts]


@app.get("/drafts", response_model=list[DraftWithJobOut])
def list_all_drafts(
    draft_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, le=300),
):
    with get_session() as session:
        query = (
            session.query(Draft, Job)
            .join(Match, Draft.match_id == Match.id)
            .join(Job, Match.job_id == Job.id)
        )
        if draft_type:
            query = query.filter(Draft.draft_type == draft_type)
        if status:
            query = query.filter(Draft.status == status)
        rows = query.order_by(Draft.created_at.desc()).limit(limit).all()

        return [
            DraftWithJobOut(
                id=d.id,
                match_id=d.match_id,
                draft_type=d.draft_type,
                content=d.content,
                gmail_draft_id=d.gmail_draft_id,
                status=d.status,
                created_at=d.created_at,
                job_title=j.title,
                job_company=j.company,
                recruiter_email=j.recruiter_email,
            )
            for d, j in rows
        ]


@app.post("/drafts/{draft_id}/push-to-gmail")
def push_draft_to_gmail(draft_id: UUID):
    """Pushes one recruiter_email draft into a real Gmail draft (never
    sends). Requires Gmail OAuth to already be set up (same credentials
    used by ingestion-service's check-gmail/push-email-drafts commands)."""
    from shared.gmail.push import push_single_draft

    with get_session() as session:
        draft = session.get(Draft, draft_id)
        if not draft:
            raise HTTPException(404, "Draft not found")
        if draft.draft_type != "recruiter_email":
            raise HTTPException(400, "Only recruiter_email drafts can be pushed to Gmail")

    try:
        result = push_single_draft(draft_id)
    except FileNotFoundError as exc:
        raise HTTPException(500, f"Gmail OAuth not configured: {exc}")
    except Exception as exc:  # noqa: BLE001 — surface Gmail API errors to the caller
        raise HTTPException(502, f"Push to Gmail failed: {exc}")

    return result


@app.post("/inbox/refresh")
def refresh_inbox(days: int = Query(default=3, le=30), max_results: int = Query(default=25, le=100)):
    """Fetches recent Gmail messages and classifies any new ones,
    synchronously. Called by the dashboard's Inbox refresh button."""
    from shared.gmail.classify import run_inbox_check

    try:
        run_inbox_check(days=days, max_results=max_results)
    except FileNotFoundError as exc:
        raise HTTPException(500, f"Gmail OAuth not configured: {exc}")
    except Exception as exc:  # noqa: BLE001 — surface Gmail/classification errors to the caller
        raise HTTPException(502, f"Inbox refresh failed: {exc}")

    return {"status": "ok"}


@app.get("/inbox", response_model=list[InboxFlagOut])
def list_inbox(
    importance: str | None = Query(default=None, description="'important' or 'not_important'"),
    reviewed: bool | None = Query(default=None),
    limit: int = Query(default=50, le=200),
):
    with get_session() as session:
        query = session.query(InboxFlag)
        if importance:
            query = query.filter(InboxFlag.importance == importance)
        if reviewed is not None:
            query = query.filter(InboxFlag.reviewed == reviewed)
        flags = query.order_by(InboxFlag.received_at.desc()).limit(limit).all()
        return [InboxFlagOut.model_validate(f) for f in flags]


@app.patch("/inbox/{flag_id}", response_model=InboxFlagOut)
def update_inbox_flag(flag_id: UUID, update: InboxFlagUpdate):
    with get_session() as session:
        flag = session.get(InboxFlag, flag_id)
        if not flag:
            raise HTTPException(404, "Inbox flag not found")
        flag.reviewed = update.reviewed
        session.flush()
        return InboxFlagOut.model_validate(flag)