"""
Internshala ingestion via Firecrawl.

The search category is derived from your resume (via derive_search_keywords
in shared/ingestion/common.py), and you can steer it further with work_type
(internship vs full-time job) and location_mode (remote vs onsite vs any).
Post-extraction, location_mode and recency are applied as filters on the
actual extracted fields, since Internshala's URL query-param syntax for
these isn't reliably documented — filtering on real extracted data is more
robust than guessing a URL param.

Flow:
  1. derive_search_keywords() — asks the LLM for 2-3 Internshala category
     slugs that fit the resume (falls back to a safe default on failure)
  2. discover_job_urls()      — scrapes each category listing page for
     individual detail-page links
  3. scrape_job()             — scrapes + structured-extracts one page
  4. fetch_all()               — orchestrates the above, applies filters,
     and caps at max_jobs
"""
import os
import time

from firecrawl import Firecrawl
from pydantic import BaseModel, Field

from shared.ingestion.common import derive_search_keywords, is_recent, matches_location_mode

FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")

# Conservative pacing — Internshala isn't as ban-happy as LinkedIn, but
# we still don't want to hammer it. Adjust as needed once you see real
# credit usage / response times.
REQUEST_DELAY_SECONDS = float(os.environ.get("INTERNSHALA_REQUEST_DELAY", "2"))

DEFAULT_KEYWORD = "software-development"  # used only if resume-based derivation fails
SLUG_EXAMPLES = (
    '"software-development", "backend-development", "full-stack-development", '
    '"python-development", "web-development", "app-development", "data-science", "machine-learning"'
)

client = Firecrawl(api_key=FIRECRAWL_API_KEY)


class InternshalaJob(BaseModel):
    """Schema Firecrawl extracts from each job detail page."""

    title: str = Field(description="Job title")
    company: str = Field(description="Hiring company name")
    location: str | None = Field(default=None, description="Job location, e.g. city or 'Work from home'")
    description: str | None = Field(default=None, description="Full job description text")
    stipend_or_salary: str | None = Field(default=None, description="Stipend or salary as shown on the page")
    posted_date: str | None = Field(default=None, description="Date the job was posted, as shown on the page")
    recruiter_email: str | None = Field(
        default=None,
        description="A recruiter or HR contact email address, ONLY if one is explicitly written on the page "
        "(e.g. 'send your resume to hr@company.com'). Do not guess or construct one — leave null if none is shown.",
    )


def _build_listing_url(keyword: str, work_type: str) -> str:
    root = "internships" if work_type == "internship" else "jobs"
    suffix = "internship" if work_type == "internship" else "jobs"
    return f"https://internshala.com/{root}/{keyword}-{suffix}/"


def discover_job_urls(listing_url: str, max_urls: int) -> list[str]:
    """Scrape a category listing page and pull individual detail-page links
    rendered on it. Mapping the whole domain (client.map) surfaces category/
    filter pages rather than individual postings, so we scrape the listing
    page directly and inspect its outbound links instead."""
    result = client.scrape(listing_url, formats=["markdown", "links"])
    links = getattr(result, "links", None) or []

    print(f"[internshala] {listing_url} returned {len(links)} links")

    job_urls = [u for u in links if "/internship/detail/" in u or "/job/detail/" in u]

    if not job_urls and links:
        print(f"[internshala] no detail-page links found at {listing_url} — "
              f"sample links: {links[:5]} (category slug may not exist on Internshala)")

    return job_urls[:max_urls]


def scrape_job(url: str) -> dict:
    """Scrape one job detail page and return raw payload + structured extraction."""
    result = client.scrape(
        url,
        formats=[
            "markdown",
            {"type": "json", "schema": InternshalaJob.model_json_schema()},
        ],
    )
    return {
        "url": url,
        "markdown": result.markdown,
        "extracted": result.json,  # dict matching InternshalaJob shape
    }


def fetch_all(
    max_jobs: int = 25,
    work_type: str = "internship",
    location_mode: str = "any",
    keywords: list[str] | None = None,
    max_age_days: int = 1,
    ignore_recency: bool = False,
) -> list[dict]:
    """Full fetch cycle.

    work_type: "internship" or "job" (full-time) — selects Internshala's
        /internships/ vs /jobs/ listing root.
    location_mode: "remote", "onsite", or "any" — applied as a post-filter
        on each posting's actual extracted location text.
    keywords: override the resume-derived search categories, e.g.
        ["backend-development"]. If None, derived from your resume.
    max_age_days: only keep postings whose "Posted ... ago" text indicates
        they're at most this many days old. Defaults to 1.
    ignore_recency: when True, skips the max_age_days filter entirely
        (debugging aid).
    """
    if work_type not in ("internship", "job"):
        raise ValueError("work_type must be 'internship' or 'job'")
    if location_mode not in ("remote", "onsite", "any"):
        raise ValueError("location_mode must be 'remote', 'onsite', or 'any'")

    search_keywords = keywords or derive_search_keywords("Internshala", SLUG_EXAMPLES, DEFAULT_KEYWORD)

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
    for url in all_urls[:max_jobs]:
        try:
            payload = scrape_job(url)
        except Exception as exc:  # noqa: BLE001 — log and continue; one bad page shouldn't kill the run
            print(f"[internshala] failed to scrape {url}: {exc}")
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        extracted = payload.get("extracted") or {}
        location = extracted.get("location")
        posted_date = extracted.get("posted_date")

        if not ignore_recency and not is_recent(posted_date, max_age_days):
            skipped_stale += 1
        elif not matches_location_mode(location, location_mode):
            skipped_location += 1
        else:
            payloads.append(payload)

        time.sleep(REQUEST_DELAY_SECONDS)

    print(
        f"[internshala] kept {len(payloads)}, skipped {skipped_stale} stale "
        f"(older than {max_age_days}d) and {skipped_location} location-mismatched"
    )
    return payloads