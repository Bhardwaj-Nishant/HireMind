"""
Matching: for every job that doesn't yet have a Match row, ask Claude to
score it against the resume and store the result.

If a match's job posting has a real recruiter contact email extracted
from it, the recruiter_email draft is auto-generated immediately after
the match is created (see shared.generation.generator.
generate_recruiter_email_if_present) — no score threshold, no manual
"Generate" click needed, since an actual contact email is a strong
enough signal on its own.

Idempotent by design — matches.job_id is unique, so re-running this only
processes jobs that don't have a match yet (no re-scoring, no duplicate
Claude calls/cost on re-runs).
"""
import json
from dataclasses import dataclass

from shared.llm.client import call_llm
from shared.generation.resume_store import get_resume_text
from shared.db.models import Job, Match
from shared.db.session import get_session

SYSTEM_PROMPT = """You are an expert technical recruiter assistant helping a candidate \
evaluate how well a job or internship posting matches their resume.

Score the fit from 0-100, where:
- 90-100: excellent match, directly aligned skills/experience/seniority
- 70-89: strong match, minor gaps
- 40-69: partial match, notable gaps in required skills or seniority level
- 0-39: poor match, wrong domain/seniority/skillset

Respond ONLY with a JSON object, no other text, no markdown fences:
{"score": <int 0-100>, "reasoning": "<2-3 sentence explanation citing specific \
skills/requirements from the job description and how they do or don't match the resume>"}
"""


@dataclass
class JobSummary:
    """Just the fields matching needs — decouples matcher.py from the ORM
    session lifecycle (Job objects go stale once their session closes)."""

    id: object
    title: str
    company: str
    location: str | None
    description: str | None
    recruiter_email: str | None


def _build_user_message(resume_text: str, job: JobSummary) -> str:
    return f"""RESUME:
{resume_text}

---

JOB POSTING:
Title: {job.title}
Company: {job.company}
Location: {job.location or "not specified"}

Description:
{job.description or "not provided"}
"""


def score_job(resume_text: str, job: JobSummary) -> tuple[float, str]:
    """Calls Claude, returns (score, reasoning). Raises on malformed response
    rather than silently defaulting — a bad score is worse than a skipped one."""
    raw = call_llm(SYSTEM_PROMPT, _build_user_message(resume_text, job))
    parsed = json.loads(raw)
    return float(parsed["score"]), parsed["reasoning"]


def run_matching_cycle(limit: int = 50) -> None:
    resume_text = get_resume_text()

    with get_session() as session:
        already_matched_ids = {m.job_id for m in session.query(Match.job_id).all()}
        query = session.query(Job)
        if already_matched_ids:
            query = query.filter(~Job.id.in_(already_matched_ids))
        unmatched_jobs = query.limit(limit).all()

        # Snapshot into plain dataclasses before the session closes
        job_summaries = [
            JobSummary(
                id=j.id, title=j.title, company=j.company, location=j.location,
                description=j.description, recruiter_email=j.recruiter_email,
            )
            for j in unmatched_jobs
        ]

    print(f"[matcher] {len(job_summaries)} unmatched jobs to score")

    scored_count = 0
    for job in job_summaries:
        try:
            score, reasoning = score_job(resume_text, job)
        except Exception as exc:  # noqa: BLE001 — one bad job shouldn't kill the whole cycle
            print(f"[matcher] failed to score job {job.id} ({job.title}): {exc}")
            continue

        with get_session() as session:
            match = Match(job_id=job.id, score=score, reasoning=reasoning, status="pending")
            session.add(match)
            session.flush()
            match_id = match.id

        print(f"[matcher] scored '{job.title}' at {job.company}: {score}")
        scored_count += 1

        if job.recruiter_email:
            from shared.generation.generator import generate_recruiter_email_if_present

            result = generate_recruiter_email_if_present(match_id)
            if result:
                print(f"[matcher] auto-generated recruiter email draft (contact: {result['recruiter_email']})")

    print(f"[matcher] scored {scored_count}/{len(job_summaries)} jobs")