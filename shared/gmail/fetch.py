"""
Fetches recent inbox messages via the Gmail API.

Kept deliberately simple: pulls subject, sender, snippet, and plain-text
body for messages from the last N days. No pagination beyond max_results —
fine for a personal inbox check; revisit if you need deep history.
"""
import base64
from datetime import datetime, timezone

from googleapiclient.discovery import build

from shared.gmail.auth import get_credentials


def _extract_plain_text(payload: dict) -> str:
    """Gmail messages can be multipart; walk parts looking for text/plain."""
    if payload.get("mimeType") == "text/plain" and "data" in payload.get("body", {}):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        text = _extract_plain_text(part)
        if text:
            return text

    return ""


def _header(headers: list[dict], name: str) -> str | None:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return None


def fetch_recent_messages(days: int = 3, max_results: int = 25) -> list[dict]:
    """Returns a list of {gmail_message_id, subject, sender, body, received_at}."""
    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds)

    query = f"newer_than:{days}d in:inbox"
    list_response = (
        service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    )
    message_refs = list_response.get("messages", [])

    results = []
    for ref in message_refs:
        msg = service.users().messages().get(userId="me", id=ref["id"], format="full").execute()
        headers = msg["payload"].get("headers", [])
        body = _extract_plain_text(msg["payload"])
        received_at = datetime.fromtimestamp(int(msg["internalDate"]) / 1000, tz=timezone.utc)

        results.append(
            {
                "gmail_message_id": msg["id"],
                "subject": _header(headers, "Subject"),
                "sender": _header(headers, "From"),
                "body": body or msg.get("snippet", ""),
                "received_at": received_at,
            }
        )

    return results