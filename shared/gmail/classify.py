"""
Orchestrates: fetch recent Gmail messages -> classify importance via LLM
-> save to inbox_flags -> print important ones to console.

Idempotent: skips messages already in inbox_flags (unique on
gmail_message_id), so re-running only processes genuinely new mail.
"""
import json

from shared.gmail.fetch import fetch_recent_messages
from shared.db.models import InboxFlag
from shared.db.session import get_session
from shared.llm.client import call_llm

SYSTEM_PROMPT = """You are helping a computer science student monitor their inbox for \
important messages related to job/internship applications, campus placements, or \
recruiting. Classify the email as "important" if it relates to: an application status \
update, an interview invitation or scheduling, an offer, a placement cell / college \
placement announcement, an assessment/test invitation, or direct recruiter outreach. \
Classify as "not_important" for newsletters, promotional content, unrelated personal/\
spam mail, or generic marketing from job platforms (e.g. "50 new jobs for you").

Respond ONLY with a JSON object, no other text, no markdown fences:
{"importance": "important" or "not_important", "reasoning": "<one sentence why>"}
"""


def classify_email(subject: str, sender: str, body: str) -> tuple[str, str]:
    user_message = f"From: {sender}\nSubject: {subject}\n\nBody:\n{body[:3000]}"
    raw = call_llm(SYSTEM_PROMPT, user_message, max_tokens=200)
    parsed = json.loads(raw)
    return parsed["importance"], parsed["reasoning"]


def run_inbox_check(days: int = 3, max_results: int = 25) -> None:
    messages = fetch_recent_messages(days=days, max_results=max_results)
    print(f"[gmail] fetched {len(messages)} messages from the last {days} day(s)")

    with get_session() as session:
        already_seen_ids = {
            row[0]
            for row in session.query(InboxFlag.gmail_message_id)
            .filter(InboxFlag.gmail_message_id.in_([m["gmail_message_id"] for m in messages]))
            .all()
        }

    new_messages = [m for m in messages if m["gmail_message_id"] not in already_seen_ids]
    print(f"[gmail] {len(new_messages)} are new (not yet classified)")

    important_found = []
    for msg in new_messages:
        try:
            importance, reasoning = classify_email(
                msg["subject"] or "", msg["sender"] or "", msg["body"] or ""
            )
        except Exception as exc:  # noqa: BLE001 — one bad message shouldn't kill the run
            print(f"[gmail] failed to classify message {msg['gmail_message_id']}: {exc}")
            continue

        with get_session() as session:
            flag = InboxFlag(
                gmail_message_id=msg["gmail_message_id"],
                subject=msg["subject"],
                sender=msg["sender"],
                importance=importance,
                reasoning=reasoning,
                received_at=msg["received_at"],
                reviewed=False,
            )
            session.add(flag)

        if importance == "important":
            important_found.append(msg)

    print(f"[gmail] classified {len(new_messages)} messages; {len(important_found)} important")

    if important_found:
        print("\n=== IMPORTANT EMAILS ===")
        for msg in important_found:
            print(f"\nFrom: {msg['sender']}")
            print(f"Subject: {msg['subject']}")
            print(f"Received: {msg['received_at']}")