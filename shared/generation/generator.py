"""
Generation: for every match above a score threshold that doesn't yet have
drafts, ask the LLM to produce a tailored resume summary, a cover letter,
and a recruiter email — all saved to `drafts` with status='pending_review'.

Additionally, generate_recruiter_email_if_present() auto-generates just
the recruiter_email draft immediately when a match's job posting has a
real recruiter contact email extracted from it — no score threshold, no
manual click. Called from shared/matching/matcher.py right after a match
is created.

Nothing here is ever sent/submitted automatically — this only writes text
for you to review later via the dashboard (or directly in the DB for now).

Idempotent per draft_type: re-running only fills in draft types that are
missing for a given match, so partial failures don't force expensive
re-generation of drafts that already succeeded.
"""
from dataclasses import dataclass

from shared.llm.client import call_llm
from shared.generation.resume_store import get_resume_text
from shared.db.models import Draft, Job, Match
from shared.db.session import get_session

MIN_SCORE_TO_GENERATE = 60.0  # don't spend LLM calls generating drafts for poor matches

RESUME_SYSTEM_PROMPT = """You are an expert resume writer. Given a candidate's base resume \
and a specific job posting, rewrite the resume's summary/objective and reorder or \
rephrase bullet points to emphasize the most relevant experience for this specific job. \
Keep it truthful — never invent experience, skills, or achievements that aren't in the \
original resume. Output the tailored resume as clean plain text, no markdown formatting, \
no commentary before or after."""

COVER_LETTER_SYSTEM_PROMPT = """You are an expert cover letter writer. Given a candidate's \
resume and a job posting, write a concise, specific cover letter (3-4 short paragraphs) \
that connects the candidate's real experience to this role's actual requirements. Avoid \
generic filler phrases. Never invent experience not present in the resume. Output only the \
letter text, no subject line, no commentary."""

EMAIL_SYSTEM_PROMPT = """You are helping a candidate draft a short, professional email to a \
recruiter or hiring contact about a specific job posting. Keep it under 150 words, warm but \
direct, referencing one or two specific and genuine points of fit between the candidate's \
background and the role. Never invent experience not present in the resume. Output ONLY the \
email body text (no subject line, no "Dear ...," salutation placeholder guessing — use \
"Hi," if no contact name is available)."""


@dataclass
class MatchContext:
    match_id: object
    job_title: str
    job_company: str
    job_location: str | None
    job_description: str | None


def _job_block(ctx: MatchContext) -> str:
    return f"""JOB POSTING:
Title: {ctx.job_title}
Company: {ctx.job_company}
Location: {ctx.job_location or "not specified"}

Description:
{ctx.job_description or "not provided"}"""


def generate_resume(resume_text: str, ctx: MatchContext) -> str:
    user_message = f"BASE RESUME:\n{resume_text}\n\n---\n\n{_job_block(ctx)}"
    return call_llm(RESUME_SYSTEM_PROMPT, user_message, max_tokens=1500)


def generate_cover_letter(resume_text: str, ctx: MatchContext) -> str:
    user_message = f"RESUME:\n{resume_text}\n\n---\n\n{_job_block(ctx)}"
    return call_llm(COVER_LETTER_SYSTEM_PROMPT, user_message, max_tokens=800)


def generate_email(resume_text: str, ctx: MatchContext) -> str:
    user_message = f"RESUME:\n{resume_text}\n\n---\n\n{_job_block(ctx)}"
    return call_llm(EMAIL_SYSTEM_PROMPT, user_message, max_tokens=400)


GENERATORS = {
    "resume": generate_resume,
    "cover_letter": generate_cover_letter,
    "recruiter_email": generate_email,
}


def generate_for_match(match_id, force: bool = False) -> list[dict]:
    """On-demand generation for one match (used by gateway-service's
    POST /matches/{id}/generate). Generates whichever draft types are
    missing (or all three if force=True), returns the created draft rows
    as plain dicts (ids as str) — no ORM objects, so this is safe to call
    from a request handler whose session lifecycle differs from the
    bulk cycle's.
    """
    resume_text = get_resume_text()

    with get_session() as session:
        match = session.get(Match, match_id)
        if not match:
            raise ValueError(f"Match {match_id} not found")
        job = session.get(Job, match.job_id)
        ctx = MatchContext(
            match_id=match.id,
            job_title=job.title,
            job_company=job.company,
            job_location=job.location,
            job_description=job.description,
        )
        existing_types = (
            set()
            if force
            else {row[0] for row in session.query(Draft.draft_type).filter_by(match_id=match.id).all()}
        )

    missing_types = [t for t in GENERATORS if t not in existing_types]
    created = []

    for draft_type in missing_types:
        content = GENERATORS[draft_type](resume_text, ctx)  # let errors surface to the API caller

        with get_session() as session:
            draft = Draft(match_id=ctx.match_id, draft_type=draft_type, content=content, status="pending_review")
            session.add(draft)
            session.flush()
            created.append(
                {
                    "id": str(draft.id),
                    "draft_type": draft.draft_type,
                    "content": draft.content,
                    "status": draft.status,
                    "gmail_draft_id": draft.gmail_draft_id,
                }
            )

    return created


def generate_recruiter_email_if_present(match_id) -> dict | None:
    """Auto-generates just the recruiter_email draft for a match, but only
    when the underlying job posting has an actual recruiter contact email
    extracted from it (Job.recruiter_email). Called automatically right
    after a match is created (see shared/matching/matcher.py) — no score
    threshold and no manual click required, since a real contact email is
    a strong enough signal on its own. Returns None if there's no
    recruiter email, or if this draft already exists."""
    with get_session() as session:
        match = session.get(Match, match_id)
        if not match:
            return None
        job = session.get(Job, match.job_id)
        if not job or not job.recruiter_email:
            return None

        existing = (
            session.query(Draft).filter_by(match_id=match_id, draft_type="recruiter_email").one_or_none()
        )
        if existing:
            return None

        ctx = MatchContext(
            match_id=match.id,
            job_title=job.title,
            job_company=job.company,
            job_location=job.location,
            job_description=job.description,
        )
        recruiter_email = job.recruiter_email

    resume_text = get_resume_text()
    try:
        content = generate_email(resume_text, ctx)
    except Exception as exc:  # noqa: BLE001 — don't let a generation failure break matching
        print(f"[generator] failed to auto-generate recruiter email for match {match_id}: {exc}")
        return None

    with get_session() as session:
        draft = Draft(match_id=match_id, draft_type="recruiter_email", content=content, status="pending_review")
        session.add(draft)
        session.flush()
        return {"id": str(draft.id), "recruiter_email": recruiter_email}


def run_generation_cycle(limit: int = 20, min_score: float = MIN_SCORE_TO_GENERATE) -> None:
    resume_text = get_resume_text()

    with get_session() as session:
        good_matches = (
            session.query(Match)
            .join(Job, Match.job_id == Job.id)
            .filter(Match.score >= min_score)
            .limit(limit)
            .all()
        )

        contexts = []
        existing_types_by_match = {}
        for m in good_matches:
            job = session.get(Job, m.job_id)
            contexts.append(
                MatchContext(
                    match_id=m.id,
                    job_title=job.title,
                    job_company=job.company,
                    job_location=job.location,
                    job_description=job.description,
                )
            )
            existing = session.query(Draft.draft_type).filter_by(match_id=m.id).all()
            existing_types_by_match[m.id] = {row[0] for row in existing}

    print(f"[generator] {len(contexts)} matches at/above score {min_score} to process")

    generated_count = 0
    for ctx in contexts:
        already = existing_types_by_match.get(ctx.match_id, set())
        missing_types = [t for t in GENERATORS if t not in already]

        if not missing_types:
            continue  # all draft types already exist for this match

        for draft_type in missing_types:
            try:
                content = GENERATORS[draft_type](resume_text, ctx)
            except Exception as exc:  # noqa: BLE001 — one bad draft shouldn't kill the cycle
                print(f"[generator] failed to generate '{draft_type}' for match {ctx.match_id}: {exc}")
                continue

            with get_session() as session:
                draft = Draft(
                    match_id=ctx.match_id,
                    draft_type=draft_type,
                    content=content,
                    status="pending_review",
                )
                session.add(draft)

            print(f"[generator] generated '{draft_type}' for '{ctx.job_title}' at {ctx.job_company}")
            generated_count += 1

    print(f"[generator] generated {generated_count} drafts across {len(contexts)} matches")