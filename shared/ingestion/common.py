"""
Shared helpers used by every scraping source module (internshala.py,
unstop.py, ...), so each source only needs to own what's actually
platform-specific: the listing URL shape and the extraction schema.
"""
import json
import re
from datetime import datetime

from shared.generation.resume_store import get_resume_text
from shared.llm.client import call_llm


def derive_search_keywords(
    platform_name: str, examples: str, default_keyword: str, keyword_style: str = "slug"
) -> list[str]:
    """Asks the LLM for search terms matching the resume, for a given
    platform's convention. keyword_style="slug" asks for hyphenated URL
    slugs (Internshala, Unstop); keyword_style="phrase" asks for natural
    search phrases instead (LinkedIn, which takes free-text queries, not
    slugs). Falls back to default_keyword on any failure (missing resume,
    malformed LLM output, provider error) so scraping never hard-fails
    over this step."""
    if keyword_style == "phrase":
        format_instruction = (
            f"{platform_name} search takes natural-language job titles/phrases like {examples}."
        )
    else:
        format_instruction = (
            f"{platform_name} organizes listings under hyphenated, lowercase URL slugs like {examples}."
        )

    system_prompt = f"""You are helping build search queries for an internship/job listing \
site ({platform_name}) based on a candidate's resume. {format_instruction}

Given the resume, respond ONLY with a JSON array of 2-3 search terms that best match the \
candidate's actual skills and experience, most relevant first, no other text:
["term-one", "term-two", "term-three"]
"""
    try:
        resume_text = get_resume_text()
        raw = call_llm(system_prompt, resume_text, max_tokens=100)
        keywords = json.loads(raw)
        if isinstance(keywords, list) and keywords:
            print(f"[{platform_name.lower()}] derived search keywords from resume: {keywords}")
            return [str(k) for k in keywords[:3]]
    except Exception as exc:  # noqa: BLE001 — fall back rather than blocking ingestion
        print(f"[{platform_name.lower()}] couldn't derive keywords from resume ({exc}), using default")

    return [default_keyword]


def matches_location_mode(location: str | None, location_mode: str) -> bool:
    if location_mode == "any":
        return True
    text = (location or "").lower()
    is_remote = "work from home" in text or "remote" in text or "wfh" in text
    return is_remote if location_mode == "remote" else not is_remote


def is_recent(posted_date_text: str | None, max_days: int) -> bool:
    """Parses posted-date text and returns whether it falls within
    max_days. Handles two formats:
      - relative: 'Posted today', '2 days ago', '3 weeks ago'
      - absolute: 'Updated On: 16 Aug 26, 11:02 AM EDT' (seen on Unstop)
    Unparseable/missing text is treated as NOT recent — better to skip a
    posting than to include something whose age we can't confirm."""
    if not posted_date_text:
        return False

    text = posted_date_text.lower()

    if "today" in text or "just now" in text or "few hours" in text or "hour" in text:
        return True
    if "yesterday" in text:
        return max_days >= 1

    relative_match = re.search(r"(\d+)\s*(hour|day|week|month|year)", text)
    if relative_match:
        amount, unit = int(relative_match.group(1)), relative_match.group(2)
        days = {"hour": amount / 24, "day": amount, "week": amount * 7, "month": amount * 30, "year": amount * 365}[unit]
        return days <= max_days

    # Absolute date fallback, e.g. "Updated On: 16 Aug 26, 11:02 AM EDT" or "16 Aug 2026"
    date_match = re.search(r"(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{2,4})", posted_date_text)
    if date_match:
        day, month_str, year = date_match.groups()
        year = ("20" + year) if len(year) == 2 else year
        for fmt in ("%d %b %Y", "%d %B %Y"):
            try:
                parsed = datetime.strptime(f"{day} {month_str} {year}", fmt)
                age_days = (datetime.now() - parsed).days
                return 0 <= age_days <= max_days
            except ValueError:
                continue

    return False