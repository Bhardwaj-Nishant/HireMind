"""
Pushes recruiter_email drafts (status='pending_review', not yet pushed)
into real, editable Gmail drafts via the Gmail API. Never sends anything —
this only calls drafts.create, which leaves the message sitting in your
Gmail Drafts folder for you to review and send yourself.

If the job posting had a real recruiter contact email extracted from it
(Job.recruiter_email), that address is filled in as the "To" field
automatically. Otherwise the "To" field is left blank — fill it in once
you've identified/confirmed the right contact.
"""
import base64
from email.mime.text import MIMEText

from googleapiclient.discovery import build

from shared.gmail.auth import get_credentials
from shared.db.models import Draft, Job, Match
from shared.db.session import get_session


def _build_raw_message(subject: str, body: str, to: str | None = None) -> dict:
    message = MIMEText(body)
    message["subject"] = subject
    if to:
        message["to"] = to
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {"raw": raw}


def push_single_draft(draft_id) -> dict:
    """Pushes one recruiter_email draft to Gmail on demand (used by
    gateway-service's POST /drafts/{id}/push-to-gmail). Raises ValueError
    if the draft doesn't exist or isn't a recruiter_email; raises whatever
    the Gmail API raises on failure — the caller (API handler) decides how
    to surface that."""
    with get_session() as session:
        row = (
            session.query(Draft, Job)
            .join(Match, Draft.match_id == Match.id)
            .join(Job, Match.job_id == Job.id)
            .filter(Draft.id == draft_id)
            .one_or_none()
        )
        if not row:
            raise ValueError(f"Draft {draft_id} not found")
        draft, job = row
        if draft.draft_type != "recruiter_email":
            raise ValueError("Only recruiter_email drafts can be pushed to Gmail")
        if draft.gmail_draft_id:
            return {"id": str(draft.id), "gmail_draft_id": draft.gmail_draft_id, "already_pushed": True}

        content, job_title, job_company, recruiter_email = draft.content, job.title, job.company, job.recruiter_email

    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)
    subject = f"Regarding the {job_title} role at {job_company}"
    raw_message = _build_raw_message(subject, content, to=recruiter_email)
    result = service.users().drafts().create(userId="me", body={"message": raw_message}).execute()

    with get_session() as session:
        draft = session.get(Draft, draft_id)
        draft.gmail_draft_id = result["id"]

    return {
        "id": str(draft_id),
        "gmail_draft_id": result["id"],
        "already_pushed": False,
        "to": recruiter_email,
    }


def push_pending_email_drafts(limit: int = 20) -> None:
    with get_session() as session:
        rows = (
            session.query(Draft, Job)
            .join(Match, Draft.match_id == Match.id)
            .join(Job, Match.job_id == Job.id)
            .filter(
                Draft.draft_type == "recruiter_email",
                Draft.status == "pending_review",
                Draft.gmail_draft_id.is_(None),
            )
            .limit(limit)
            .all()
        )
        pending = [
            {
                "draft_id": d.id,
                "content": d.content,
                "job_title": j.title,
                "job_company": j.company,
                "recruiter_email": j.recruiter_email,
            }
            for d, j in rows
        ]

    print(f"[gmail-drafts] {len(pending)} recruiter email drafts to push")

    if not pending:
        return

    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)

    pushed_count = 0
    for item in pending:
        subject = f"Regarding the {item['job_title']} role at {item['job_company']}"
        raw_message = _build_raw_message(subject, item["content"], to=item["recruiter_email"])

        try:
            result = service.users().drafts().create(userId="me", body={"message": raw_message}).execute()
        except Exception as exc:  # noqa: BLE001 — one bad draft shouldn't kill the run
            print(f"[gmail-drafts] failed to push draft {item['draft_id']}: {exc}")
            continue

        with get_session() as session:
            draft = session.get(Draft, item["draft_id"])
            if draft:
                draft.gmail_draft_id = result["id"]

        to_note = f" (to: {item['recruiter_email']})" if item["recruiter_email"] else " (no recipient — add one manually)"
        print(f"[gmail-drafts] pushed draft for '{item['job_title']}' at {item['job_company']}{to_note}")
        pushed_count += 1

    print(f"[gmail-drafts] pushed {pushed_count}/{len(pending)} drafts to Gmail")