"""
Unstop ingestion via Firecrawl.

HONEST CAVEAT: unlike Internshala, I couldn't confirm Unstop's exact
search/category listing URL syntax (Unstop's site shows a "cookies
disabled" wall to simple crawlers and appears to render listings via
client-side JS/XHR, which is harder to verify without live access). The
listing URL built below (`unstop.com/{internships|jobs}?searchTerm=...`)
and the /internships/ or /jobs/ + slug detail-page pattern are best-effort
based on public documentation and the confirmed detail-page URL shape
(unstop.com/internships/<slug>-<id>). Expect to see debug output on the
first real run showing what Firecrawl actually got back — the URL
construction and link-matching filter below are the first things to
adjust if it comes back empty, same as we did for Internshala.

Recency note: many Unstop postings don't expose a clear posted/updated
date at all. When posted_date is genuinely missing, the posting is
included anyway (freshness can't be verified either way) rather than
dropped — per an explicit choice, since strict filtering would exclude
most Unstop results. A date that WAS extracted and reads as stale is
still filtered out normally.
"""
import os
import time

from firecrawl import Firecrawl
from pydantic import BaseModel, Field

from shared.ingestion.common import derive_search_keywords, is_recent, matches_location_mode

FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
REQUEST_DELAY_SECONDS = float(os.environ.get("UNSTOP_REQUEST_DELAY", "2"))

DEFAULT_KEYWORD = "software-development"
SLUG_EXAMPLES = (
    '"software-development", "web-development", "backend-development", '
    '"data-science", "app-development", "machine-learning"'
)

client = Firecrawl(api_key=FIRECRAWL_API_KEY)


class UnstopJob(BaseModel):
    """Schema Firecrawl extracts from each opportunity detail page."""

    title: str = Field(description="Job or internship title")
    company: str = Field(description="Hiring company/organizer name")
    location: str | None = Field(default=None, description="Location, e.g. city, 'Work from home', or 'Remote'")
    description: str | None = Field(default=None, description="Full job/internship description text")
    stipend_or_salary: str | None = Field(default=None, description="Stipend or salary as shown on the page")
    posted_date: str | None = Field(
        default=None,
        description="When this was posted, as shown on the page (e.g. 'Posted 2 days ago'). "
        "If the page only shows an application deadline and not a posted date, leave this null.",
    )
    recruiter_email: str | None = Field(
        default=None,
        description="A recruiter or HR contact email address, ONLY if one is explicitly written on the page "
        "(e.g. 'send your resume to hr@company.com'). Do not guess or construct one — leave null if none is shown.",
    )


def _build_listing_url(keyword: str, work_type: str) -> str:
    root = "internships" if work_type == "internship" else "jobs"
    return f"https://unstop.com/{root}?searchTerm={keyword}&oppstatus=open"


def discover_job_urls(listing_url: str, max_urls: int) -> list[str]:
    """Scrape a search/listing page and pull individual detail-page links.
    See module docstring — Unstop's listing page behavior is less verified
    than Internshala's, so this prints generous debug output."""
    result = client.scrape(listing_url, formats=["markdown", "links"])
    links = getattr(result, "links", None) or []

    print(f"[unstop] {listing_url} returned {len(links)} links")

    job_urls = [u for u in links if "/internships/" in u.split("unstop.com")[-1] and u.count("-") > 0]
    # Narrow further to actual detail pages (they have a numeric id suffix),
    # excluding the bare listing/category root itself.
    job_urls = [u for u in job_urls if u.rstrip("/") != listing_url.split("?")[0].rstrip("/") and any(c.isdigit() for c in u)]

    if not job_urls and links:
        print(f"[unstop] no detail-page links found at {listing_url} — "
              f"sample links: {links[:8]} (URL pattern may need adjusting — see module docstring)")

    return job_urls[:max_urls]


def scrape_job(url: str) -> dict:
    """Scrape one opportunity detail page and return raw payload + structured extraction."""
    result = client.scrape(
        url,
        formats=[
            "markdown",
            {"type": "json", "schema": UnstopJob.model_json_schema()},
        ],
    )
    return {
        "url": url,
        "markdown": result.markdown,
        "extracted": result.json,
    }


def fetch_all(
    max_jobs: int = 25,
    work_type: str = "internship",
    location_mode: str = "any",
    keywords: list[str] | None = None,
    max_age_days: int = 1,
    ignore_recency: bool = False,
) -> list[dict]:
    """Full fetch cycle. Same parameter meanings as internshala.fetch_all.

    ignore_recency: when True, skips the max_age_days filter entirely.
    Useful for debugging whether Unstop's posted_date extraction is
    working at all, independent of the recency threshold — see the
    module docstring's caveat about Unstop possibly not exposing a clear
    posted date.
    """
    if work_type not in ("internship", "job"):
        raise ValueError("work_type must be 'internship' or 'job'")
    if location_mode not in ("remote", "onsite", "any"):
        raise ValueError("location_mode must be 'remote', 'onsite', or 'any'")

    search_keywords = keywords or derive_search_keywords("Unstop", SLUG_EXAMPLES, DEFAULT_KEYWORD)

    seen_urls: set[str] = set()
    all_urls: list[str] = []
    for kw in search_keywords:
        if len(all_urls) >= max_jobs:
            break
        listing_url = _build_listing_url(kw, work_type)
        urls = discover_job_urls(listing_url, max_urls=max_jobs)
        for u in urls:
            if u not in seen_urls:
                seen_urls.add(u)
                all_urls.append(u)

    payloads = []
    skipped_stale = 0
    skipped_location = 0
    unverified_included = 0
    for url in all_urls[:max_jobs]:
        try:
            payload = scrape_job(url)
        except Exception as exc:  # noqa: BLE001 — log and continue; one bad page shouldn't kill the run
            print(f"[unstop] failed to scrape {url}: {exc}")
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        extracted = payload.get("extracted") or {}
        location = extracted.get("location")
        posted_date = extracted.get("posted_date")

        # Unstop often doesn't expose a posted/updated date at all (unlike
        # Internshala). Per your choice: when it's genuinely missing, we
        # can't verify freshness either way, so include it rather than
        # silently dropping most Unstop results — but a date that WAS
        # extracted and reads as stale is still filtered out normally.
        if posted_date is None:
            recent_enough = True
            if not ignore_recency:
                unverified_included += 1
        else:
            recent_enough = ignore_recency or is_recent(posted_date, max_age_days)

        if not recent_enough:
            skipped_stale += 1
            print(f"[unstop] skipping (stale) {url} — extracted posted_date={posted_date!r}")
        elif not matches_location_mode(location, location_mode):
            skipped_location += 1
        else:
            payloads.append(payload)

        time.sleep(REQUEST_DELAY_SECONDS)

    print(
        f"[unstop] kept {len(payloads)} ({unverified_included} with unverifiable/missing date), "
        f"skipped {skipped_stale} confirmed-stale (older than {max_age_days}d) and "
        f"{skipped_location} location-mismatched"
    )
    return payloads