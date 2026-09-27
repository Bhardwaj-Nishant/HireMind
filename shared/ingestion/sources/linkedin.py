"""
LinkedIn ingestion via `linkedin_scraper` (joeyism/linkedin_scraper), an
actively maintained (v3.1.2, April 2026) Playwright-based library — NOT
Firecrawl, and NOT the old tomquirk `linkedin-api` wire-API library.

HONEST TRADEOFFS, please read before relying on this:
  - This drives a real (headless) browser via Playwright, not lightweight
    HTTP calls — heavier, slower, and needs the `playwright install
    chromium` browser binary installed on whatever machine runs it
    (including gateway-service's host, if you use the dashboard's
    "Fetch more matches" for LinkedIn).
  - Requires a one-time interactive login: run
    `python scripts/linkedin_setup.py` from ingestion-service/ once, log
    into LinkedIn by hand in the browser window it opens, and it saves a
    reusable session file. This script never sees or stores your
    password.
  - Still your real personal account, still against LinkedIn's Terms of
    Service, still real account-restriction risk — which is why the same
    ~1 request/hour gate from before is kept here (persisted in the
    `credentials` table, checked before every fetch_all() call).
  - The exact fields available on the library's `Job` model aren't fully
    confirmed from where I could verify its docs — the first real run
    logs the raw attributes of one result so field-name mismatches can
    be fixed against real data rather than guessed again.
  - `search()`'s exact keyword-argument surface for filtering (e.g. an
    experience-level or remote-only parameter) isn't confirmed either,
    so work_type is approximated by appending "Intern" to the search
    keywords rather than risking a TypeError from a guessed parameter
    name — cruder, but won't crash if wrong.

Setup:
    pip install linkedin-scraper playwright
    playwright install chromium
    python scripts/linkedin_setup.py   (one-time, from ingestion-service/)
"""

import asyncio
import os
import re
from datetime import datetime, timezone

from shared.db.models import Credential
from shared.db.session import get_session
from shared.ingestion.common import derive_search_keywords, matches_location_mode


DEFAULT_KEYWORD = "Software Development"

PHRASE_EXAMPLES = (
    '"Backend Developer", "Full Stack Developer", '
    '"Python Developer", "Software Engineer"'
)

MIN_INTERVAL_HOURS = float(
    os.environ.get("LINKEDIN_MIN_INTERVAL_HOURS", "1")
)

REQUEST_DELAY_SECONDS = float(
    os.environ.get("LINKEDIN_REQUEST_DELAY", "2")
)

SESSION_PATH = os.environ.get(
    "LINKEDIN_SESSION_PATH",
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "..",
        "ingestion-service",
        "linkedin_session.json",
    ),
)


class RateLimitedError(RuntimeError):
    """Raised when fetch_all() is called before min_interval_hours has
    elapsed since the last successful run, and force=False.
    """


def _load_last_fetch_at() -> str | None:
    with get_session() as session:
        row = (
            session.query(Credential)
            .filter_by(platform="linkedin")
            .one_or_none()
        )

        return row.credential_data.get("last_fetch_at") if row else None


def _update_last_fetch_at() -> None:
    with get_session() as session:
        row = (
            session.query(Credential)
            .filter_by(platform="linkedin")
            .one_or_none()
        )

        now = datetime.now(timezone.utc).isoformat()

        if row:
            data = dict(row.credential_data)
            data["last_fetch_at"] = now
            row.credential_data = data

        else:
            row = Credential(
                platform="linkedin",
                auth_type="session_file",
                credential_data={
                    "last_fetch_at": now
                },
            )

            session.add(row)


def _check_rate_limit(
    min_interval_hours: float,
    force: bool,
) -> None:

    if force:
        return

    last_fetch_at = _load_last_fetch_at()

    if not last_fetch_at:
        return

    elapsed_hours = (
        datetime.now(timezone.utc)
        - datetime.fromisoformat(last_fetch_at)
    ).total_seconds() / 3600

    if elapsed_hours < min_interval_hours:

        wait_minutes = round(
            (min_interval_hours - elapsed_hours) * 60
        )

        raise RateLimitedError(
            f"LinkedIn was fetched {elapsed_hours:.1f}h ago; "
            f"waiting for min_interval_hours={min_interval_hours}. "
            f"Try again in about {wait_minutes} min, "
            f"or pass force=True."
        )


def _describe_job_object(job) -> str:
    """Debug helper: shows what a raw result object actually looks like.

    Handles:
      - plain strings
      - dictionaries
      - Pydantic-model-like objects
    """

    if isinstance(job, str):
        return f"plain string, repr: {job!r}"

    if isinstance(job, dict):
        return (
            f"dict with keys: {list(job.keys())} "
            f"— sample: {job}"
        )

    attrs = [
        a for a in dir(job)
        if not a.startswith("_")
    ]

    sample = {}

    for a in attrs:

        try:
            val = getattr(job, a)

            if not callable(val):
                sample[a] = val

        except Exception:
            continue

    return (
        f"object of type {type(job).__name__} "
        f"with attributes: {list(sample.keys())} "
        f"— sample: {sample}"
    )


def _resolve_url(raw) -> str | None:
    """
    Resolve a LinkedIn URL from a search result.

    Handles:

    1. Normal URL:
       https://www.linkedin.com/jobs/view/123/

    2. Markdown URL:
       [https://www.linkedin.com/jobs/view/123/](https://www.linkedin.com/jobs/view/123/)

    3. Plain job ID:
       123

    4. Object/dict containing linkedin_url or url.
    """

    if isinstance(raw, str):

        # ---------------------------------------------------------
        # Markdown URL
        #
        # Example:
        # [https://www.linkedin.com/jobs/view/123/](https://www.linkedin.com/jobs/view/123/)
        # ---------------------------------------------------------

        markdown_match = re.search(
            r"\]\((https?://www\.linkedin\.com/jobs/view/\d+/?)\)",
            raw,
        )

        if markdown_match:
            return markdown_match.group(1)

        # ---------------------------------------------------------
        # Normal URL
        # ---------------------------------------------------------

        if raw.startswith("http"):
            return raw

        # ---------------------------------------------------------
        # Plain LinkedIn job ID
        # ---------------------------------------------------------

        if raw.isdigit():
            return (
                f"https://www.linkedin.com/jobs/view/"
                f"{raw}/"
            )

    # -------------------------------------------------------------
    # Dictionary result
    # -------------------------------------------------------------

    if isinstance(raw, dict):

        return (
            raw.get("linkedin_url")
            or raw.get("url")
        )

    # -------------------------------------------------------------
    # Object result
    # -------------------------------------------------------------

    return (
        getattr(raw, "linkedin_url", None)
        or getattr(raw, "url", None)
    )


def _get(obj, field_names):
    """
    Safely get the first non-empty field from either a dictionary
    or an object.
    """

    for name in field_names:

        if isinstance(obj, dict):
            val = obj.get(name)

        else:
            val = getattr(obj, name, None)

        if val and not callable(val):
            return val

    return None


async def _search_jobs_async(
    keywords_list: list[str],
    max_jobs: int,
    max_detail_fetches: int,
) -> list[dict]:

    """
    Runs the actual Playwright-driven search + a bounded number
    of detail fetches.

    Returns plain dictionaries instead of the library's Pydantic
    objects.
    """

    from linkedin_scraper import (
        BrowserManager,
        JobScraper,
        JobSearchScraper,
    )

    # -------------------------------------------------------------
    # Verify LinkedIn session
    # -------------------------------------------------------------

    if not os.path.exists(SESSION_PATH):

        raise FileNotFoundError(
            f"No LinkedIn session found at {SESSION_PATH}. "
            f"Run `python scripts/linkedin_setup.py` "
            f"from ingestion-service/ once to log in and create it."
        )

    results = []

    # -------------------------------------------------------------
    # Start browser
    # -------------------------------------------------------------

    async with BrowserManager(headless=True) as browser:

        await browser.load_session(SESSION_PATH)

        search_scraper = JobSearchScraper(browser.page)

        # ---------------------------------------------------------
        # Search jobs
        # ---------------------------------------------------------

        raw_jobs = []

        for kw in keywords_list:

            if len(raw_jobs) >= max_jobs:
                break

            try:

                jobs = await search_scraper.search(
                    keywords=kw,
                    limit=max_jobs,
                )

            except Exception as exc:

                print(
                    f"[linkedin] search failed for keyword "
                    f"'{kw}': {exc}"
                )

                continue

            print(
                f"[linkedin] search '{kw}' "
                f"returned {len(jobs)} results"
            )

            raw_jobs.extend(jobs)

            await asyncio.sleep(
                REQUEST_DELAY_SECONDS
            )

        # ---------------------------------------------------------
        # Debug first search result
        # ---------------------------------------------------------

        if raw_jobs:

            print(
                "[linkedin] DEBUG first search result: "
                f"{_describe_job_object(raw_jobs[0])}"
            )

        # ---------------------------------------------------------
        # Detail scraper
        # ---------------------------------------------------------

        detail_scraper = JobScraper(browser.page)

        detail_debug_printed = False

        # ---------------------------------------------------------
        # Fetch job details
        # ---------------------------------------------------------

        for raw in raw_jobs[:max_detail_fetches]:

            job_url = _resolve_url(raw)

            if not job_url:

                print(
                    "[linkedin] couldn't derive a URL from "
                    f"search result: {raw!r}"
                )

                continue

            try:

                detail = await detail_scraper.scrape(
                    job_url
                )

            except Exception as exc:

                print(
                    f"[linkedin] failed to fetch details "
                    f"for {job_url}: {exc}"
                )

                continue

            # -----------------------------------------------------
            # Debug raw Job object
            # -----------------------------------------------------

            if not detail_debug_printed:

                print(
                    "[linkedin] DEBUG first detail result: "
                    f"{_describe_job_object(detail)}"
                )

                detail_debug_printed = True

            # -----------------------------------------------------
            # Extract normal fields
            # -----------------------------------------------------

            title = _get(
                detail,
                [
                    "title",
                    "job_title",
                    "name",
                ],
            )

            company = _get(
                detail,
                [
                    "company",
                    "company_name",
                    "companyName",
                ],
            )

            location = _get(
                detail,
                [
                    "location",
                    "job_location",
                ],
            )

            description = _get(
                detail,
                [
                    "description",
                    "job_description",
                ],
            )

            # -----------------------------------------------------
            # IMPORTANT:
            #
            # linkedin_scraper currently returns:
            #
            # job_title=None
            #
            # but the browser page title contains:
            #
            # Software Engineering Intern |
            # Abstrabit Technologies | LinkedIn
            #
            # Therefore use page.title() as a fallback.
            # -----------------------------------------------------

            if not title:

                print(
                    "[linkedin] JobScraper did not extract title"
                )

                try:

                    page_title = await browser.page.title()

                    print(
                        f"[linkedin] PAGE TITLE: {page_title}"
                    )

                    if page_title:

                        parts = [
                            part.strip()
                            for part in page_title.split("|")
                        ]

                        if parts:

                            candidate_title = parts[0]

                            if candidate_title:
                                title = candidate_title

                except Exception as exc:

                    print(
                        "[linkedin] failed to extract title "
                        f"from page title: {exc}"
                    )

            # -----------------------------------------------------
            # Optional debug
            # -----------------------------------------------------

            if not title:

                print(
                    "[linkedin] WARNING: title is still missing "
                    f"for {job_url}"
                )

            print(
                "[linkedin] extracted: "
                f"title={title!r}, "
                f"company={company!r}, "
                f"location={location!r}"
            )

            # -----------------------------------------------------
            # Store normalized result
            # -----------------------------------------------------

            results.append(
                {
                    "url": job_url,
                    "title": title,
                    "company": company,
                    "location": location,
                    "description": description,
                }
            )

            await asyncio.sleep(
                REQUEST_DELAY_SECONDS
            )

    return results


def fetch_all(
    max_jobs: int = 10,
    work_type: str = "internship",
    location_mode: str = "any",
    keywords: list[str] | None = None,
    max_age_days: int = 1,
    ignore_recency: bool = False,
    force: bool = False,
    max_detail_fetches: int = 5,
) -> list[dict]:

    """
    Full LinkedIn fetch cycle.

    Parameters:
        max_jobs:
            Maximum number of search results requested.

        work_type:
            Either "internship" or "job".

        location_mode:
            "remote", "onsite", or "any".

        keywords:
            Optional custom LinkedIn search keywords.

        max_age_days:
            Kept for compatibility with other ingestion sources.

        ignore_recency:
            Kept for compatibility with other ingestion sources.

        force:
            Bypass the hourly LinkedIn rate gate.

        max_detail_fetches:
            Maximum number of individual job pages to open.

    Note:
        LinkedIn's search results through this library don't
        reliably expose a posted date, so postings are included
        when recency cannot be verified rather than dropped.
    """

    # -------------------------------------------------------------
    # Validate parameters
    # -------------------------------------------------------------

    if work_type not in (
        "internship",
        "job",
    ):

        raise ValueError(
            "work_type must be 'internship' or 'job'"
        )

    if location_mode not in (
        "remote",
        "onsite",
        "any",
    ):

        raise ValueError(
            "location_mode must be 'remote', 'onsite', or 'any'"
        )

    # -------------------------------------------------------------
    # Rate limit
    # -------------------------------------------------------------

    _check_rate_limit(
        MIN_INTERVAL_HOURS,
        force,
    )

    # -------------------------------------------------------------
    # Derive search keywords
    # -------------------------------------------------------------

    search_keywords = keywords or derive_search_keywords(
        "LinkedIn",
        PHRASE_EXAMPLES,
        DEFAULT_KEYWORD,
        keyword_style="phrase",
    )

    # -------------------------------------------------------------
    # Convert job search into internship search
    # -------------------------------------------------------------

    if work_type == "internship":

        search_keywords = [
            f"{kw} Intern"
            for kw in search_keywords
        ]

    # -------------------------------------------------------------
    # Run async scraper
    # -------------------------------------------------------------

    try:

        raw_results = asyncio.run(
            _search_jobs_async(
                search_keywords,
                max_jobs,
                max_detail_fetches,
            )
        )

    except FileNotFoundError:

        raise

    except Exception as exc:

        raise RuntimeError(
            f"LinkedIn scraping failed: {exc}"
        ) from exc

    # -------------------------------------------------------------
    # Normalize results
    # -------------------------------------------------------------

    payloads = []

    skipped_location = 0
    skipped_missing_fields = 0

    for result in raw_results:

        # ---------------------------------------------------------
        # Require URL and title
        # ---------------------------------------------------------

        if (
            not result.get("url")
            or not result.get("title")
        ):

            skipped_missing_fields += 1

            print(
                "[linkedin] skipping result with "
                f"missing url/title: {result}"
            )

            continue

        # ---------------------------------------------------------
        # Location filtering
        # ---------------------------------------------------------

        if not matches_location_mode(
            result.get("location"),
            location_mode,
        ):

            skipped_location += 1

            continue

        # ---------------------------------------------------------
        # Build ingestion payload
        # ---------------------------------------------------------

        payloads.append(
            {
                "url": result["url"],
                "markdown": None,
                "extracted": {
                    "title": result["title"],
                    "company": (
                        result.get("company")
                        or "Unknown"
                    ),
                    "location": result.get(
                        "location"
                    ),
                    "description": result.get(
                        "description"
                    ),
                    "stipend_or_salary": None,
                    "posted_date": None,
                    "recruiter_email": None,
                },
            }
        )

    # -------------------------------------------------------------
    # Update rate-limit timestamp
    # -------------------------------------------------------------

    _update_last_fetch_at()

    # -------------------------------------------------------------
    # Final stats
    # -------------------------------------------------------------

    print(
        f"[linkedin] kept {len(payloads)}, "
        f"skipped {skipped_location} location-mismatched, "
        f"{skipped_missing_fields} missing url/title"
    )

    return payloads