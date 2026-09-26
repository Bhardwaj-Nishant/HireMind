"""
LinkedIn ingestion via the unofficial `linkedin-api` package (Voyager
API wrapper), NOT Firecrawl — session-cookie authenticated, matching the
earlier decision to avoid both official API restrictions and browser-
automation scraping.

HONEST CAVEATS, please read before relying on this:
  - `linkedin-api` (PyPI) is effectively unmaintained: no release since
    November 2024, and its published GitHub source/docs URLs currently
    return 404. LinkedIn's internal Voyager API can change without
    notice, and this library has had no chance to adapt if it has. It
    may simply stop working at any time — that's a real risk, not a
    hypothetical one.
  - This uses YOUR personal LinkedIn account's session cookies. Session
    cookies expire (days to weeks) and need re-extracting from a browser
    when they do. Automated use of a personal account for this purpose
    also violates LinkedIn's Terms of Service — the risk of account
    restriction is real, which is exactly why requests are capped at
    roughly once per hour (see min_interval_hours below).
  - Field availability (posted date, location format, etc.) from
    search_jobs()/get_job() is whatever this specific library version
    happens to expose — expect to see debug output on first real use and
    adjust extraction the same way we did for Internshala/Unstop.

Setup (one-time):
  1. Log into linkedin.com in your browser.
  2. Open DevTools -> Application (Chrome) or Storage (Firefox) -> Cookies
     -> https://www.linkedin.com
  3. Copy the values of the `li_at` and `JSESSIONID` cookies.
  4. Set env vars LINKEDIN_LI_AT and LINKEDIN_JSESSIONID for the first
     run — they're then stored in the `credentials` table (platform=
     'linkedin') and reused automatically after that, same pattern as
     Gmail OAuth tokens.

Rate limiting: a `last_fetch_at` timestamp is persisted in the same
credentials row. Every fetch_all() call checks it first and refuses to
run again before min_interval_hours has passed (default 1.0), unless
force=True. This is enforced per ENTIRE cycle (search + detail calls),
not per individual request, which is the practical way to keep to "about
once an hour" for the whole account.
"""
import os
import time
from datetime import datetime, timezone

from linkedin_api import Linkedin
from requests.cookies import RequestsCookieJar

from shared.db.models import Credential
from shared.db.session import get_session
from shared.ingestion.common import derive_search_keywords, matches_location_mode

DEFAULT_KEYWORD = "Software Development"
PHRASE_EXAMPLES = '"Backend Developer", "Full Stack Developer", "Python Developer", "Software Engineer Intern"'

MIN_INTERVAL_HOURS = float(os.environ.get("LINKEDIN_MIN_INTERVAL_HOURS", "1"))
REQUEST_DELAY_SECONDS = float(os.environ.get("LINKEDIN_REQUEST_DELAY", "2"))

_client_cache: Linkedin | None = None


class RateLimitedError(RuntimeError):
    """Raised when fetch_all() is called before min_interval_hours has
    elapsed since the last successful run, and force=False."""


def _load_credential() -> dict | None:
    """Returns the credential_data dict (not the ORM object — the session
    closes before this returns, so returning the object itself would raise
    DetachedInstanceError on any later attribute access)."""
    with get_session() as session:
        row = session.query(Credential).filter_by(platform="linkedin").one_or_none()
        return dict(row.credential_data) if row else None


def _store_credential(li_at: str, jsessionid: str, last_fetch_at: str | None = None) -> None:
    with get_session() as session:
        row = session.query(Credential).filter_by(platform="linkedin").one_or_none()
        data = {"li_at": li_at, "jsessionid": jsessionid}
        if last_fetch_at is not None:
            data["last_fetch_at"] = last_fetch_at
        elif row and row.credential_data.get("last_fetch_at"):
            data["last_fetch_at"] = row.credential_data["last_fetch_at"]

        if row:
            row.credential_data = data
        else:
            row = Credential(platform="linkedin", auth_type="session_cookie", credential_data=data)
            session.add(row)


def _update_last_fetch_at() -> None:
    with get_session() as session:
        row = session.query(Credential).filter_by(platform="linkedin").one_or_none()
        if row:
            data = dict(row.credential_data)
            data["last_fetch_at"] = datetime.now(timezone.utc).isoformat()
            row.credential_data = data


def _check_rate_limit(min_interval_hours: float, force: bool) -> None:
    if force:
        return
    credential_data = _load_credential()
    last_fetch_at = credential_data.get("last_fetch_at") if credential_data else None
    if not last_fetch_at:
        return

    elapsed_hours = (datetime.now(timezone.utc) - datetime.fromisoformat(last_fetch_at)).total_seconds() / 3600
    if elapsed_hours < min_interval_hours:
        wait_minutes = round((min_interval_hours - elapsed_hours) * 60)
        raise RateLimitedError(
            f"LinkedIn was fetched {elapsed_hours:.1f}h ago; waiting for min_interval_hours="
            f"{min_interval_hours}. Try again in about {wait_minutes} min, or pass force=True."
        )


def get_client() -> Linkedin:
    """Builds (and caches) a Linkedin API client from session cookies.
    Env vars take priority when set (so you can refresh expired/invalid
    cookies just by re-setting LINKEDIN_LI_AT / LINKEDIN_JSESSIONID and
    re-running — otherwise, once cookies were stored once, new env vars
    would be silently ignored). Falls back to whatever's already stored
    in the credentials table when the env vars aren't set."""
    global _client_cache
    if _client_cache is not None:
        return _client_cache

    env_li_at = os.environ.get("LINKEDIN_LI_AT")
    env_jsessionid = os.environ.get("LINKEDIN_JSESSIONID")

    if env_li_at and env_jsessionid:
        li_at, jsessionid = env_li_at, env_jsessionid
        _store_credential(li_at, jsessionid)
    else:
        credential_data = _load_credential()
        if not credential_data:
            raise FileNotFoundError(
                "No LinkedIn session cookies found. Set LINKEDIN_LI_AT and LINKEDIN_JSESSIONID "
                "(extracted from your browser's DevTools -> Application -> Cookies -> "
                "linkedin.com) for the first run — see module docstring for exact steps."
            )
        li_at = credential_data.get("li_at")
        jsessionid = credential_data.get("jsessionid")

    jar = RequestsCookieJar()
    jar.set("li_at", li_at, domain=".linkedin.com", path="/")
    jsessionid_value = jsessionid if jsessionid.startswith('"') else f'"{jsessionid}"'
    jar.set("JSESSIONID", jsessionid_value, domain=".linkedin.com", path="/")

    try:
        _client_cache = Linkedin("", "", cookies=jar, authenticate=False)
    except TypeError:
        # Some fork/versions of this library don't accept authenticate= —
        # fall back to the constructor without it.
        _client_cache = Linkedin("", "", cookies=jar)

    return _client_cache


def _job_id_from_result(result: dict) -> str | None:
    """search_jobs() results identify the job via a URN like
    'urn:li:jobPosting:1234567890' under varying key names depending on
    library version — check the common ones."""
    urn = result.get("trackingUrn") or result.get("entityUrn") or result.get("dashEntityUrn")
    if not urn:
        return None
    return str(urn).split(":")[-1]


def _epoch_ms_is_recent(epoch_ms: int | None, max_days: int) -> bool:
    if not epoch_ms:
        return False
    posted = datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
    age_days = (datetime.now(timezone.utc) - posted).total_seconds() / 86400
    return 0 <= age_days <= max_days


def fetch_all(
    max_jobs: int = 10,
    work_type: str = "internship",
    location_mode: str = "any",
    keywords: list[str] | None = None,
    max_age_days: int = 1,
    ignore_recency: bool = False,
    force: bool = False,
    max_detail_fetches: int = 2,
) -> list[dict]:
    """Full fetch cycle. Same parameter meanings as internshala.fetch_all,
    plus:

    force: bypass the min-interval-hours rate gate (debugging only —
        avoid using this routinely, it exists specifically to protect
        the LinkedIn account this session belongs to).
    max_detail_fetches: how many search results to fetch full details
        (description) for via an extra get_job() call each. Kept small
        by default to minimize request count per hourly cycle — the
        rest are included with whatever summary fields search_jobs()
        already returned, no extra request per posting.
    """
    if work_type not in ("internship", "job"):
        raise ValueError("work_type must be 'internship' or 'job'")
    if location_mode not in ("remote", "onsite", "any"):
        raise ValueError("location_mode must be 'remote', 'onsite', or 'any'")

    _check_rate_limit(MIN_INTERVAL_HOURS, force)

    client = get_client()
    search_keywords = keywords or derive_search_keywords(
        "LinkedIn", PHRASE_EXAMPLES, DEFAULT_KEYWORD, keyword_style="phrase"
    )

    experience = ["1"] if work_type == "internship" else None  # '1' = Internship, per library's known codes
    remote_filter = None
    if location_mode == "remote":
        remote_filter = ["2"]  # '2' = Remote
    elif location_mode == "onsite":
        remote_filter = ["1"]  # '1' = On-site

    raw_results = []
    for kw in search_keywords:
        if len(raw_results) >= max_jobs:
            break
        try:
            search_kwargs = {"keywords": kw, "limit": max_jobs}
            if experience:
                search_kwargs["experience"] = experience
            if remote_filter:
                search_kwargs["remote"] = remote_filter
            results = client.search_jobs(**search_kwargs)
        except Exception as exc:  # noqa: BLE001 — one bad keyword shouldn't kill the whole run
            hint = ""
            if "Expecting value" in str(exc) or "JSONDecodeError" in type(exc).__name__:
                hint = (
                    " — this usually means LinkedIn returned something that isn't JSON (an "
                    "expired/invalid session cookie, a login redirect, or a verification "
                    "challenge page) rather than real search results. Try logging into "
                    "linkedin.com fresh in your browser, re-extracting li_at and JSESSIONID, "
                    "and re-running with LINKEDIN_LI_AT / LINKEDIN_JSESSIONID set again — that "
                    "overwrites the stored cookies."
                )
            print(f"[linkedin] search failed for keyword '{kw}': {exc}{hint}")
            continue

        print(f"[linkedin] search '{kw}' returned {len(results)} results")
        raw_results.extend(results)
        time.sleep(REQUEST_DELAY_SECONDS)

    payloads = []
    skipped_stale = 0
    skipped_location = 0
    detail_fetches_used = 0

    for result in raw_results[:max_jobs]:
        job_id = _job_id_from_result(result)
        if not job_id:
            print(f"[linkedin] couldn't extract a job id from search result, skipping: {list(result.keys())}")
            continue

        title = (result.get("title") or {}).get("text") if isinstance(result.get("title"), dict) else result.get("title")
        company = None
        location = result.get("formattedLocation") or result.get("location")
        listed_at = result.get("listedAt")
        description = None

        if detail_fetches_used < max_detail_fetches:
            try:
                detail = client.get_job(job_id)
                detail_fetches_used += 1
                description = detail.get("description", {}).get("text") if isinstance(detail.get("description"), dict) else detail.get("description")
                company = (
                    detail.get("companyDetails", {})
                    .get("com.linkedin.voyager.deco.jobs.web.shared.WebCompactJobPostingCompany", {})
                    .get("companyResolutionResult", {})
                    .get("name")
                )
                listed_at = listed_at or detail.get("listedAt")
                time.sleep(REQUEST_DELAY_SECONDS)
            except Exception as exc:  # noqa: BLE001 — fall back to search-result summary fields
                print(f"[linkedin] failed to fetch details for job {job_id}: {exc}")

        if not title:
            print(f"[linkedin] skipping job {job_id} — no title in result")
            continue

        recent_enough = ignore_recency or (
            _epoch_ms_is_recent(listed_at, max_age_days) if listed_at else True  # unknown -> can't verify, include
        )
        if not recent_enough:
            skipped_stale += 1
            continue
        if not matches_location_mode(location, location_mode):
            skipped_location += 1
            continue

        payloads.append(
            {
                "url": f"https://www.linkedin.com/jobs/view/{job_id}/",
                "markdown": None,
                "extracted": {
                    "title": title,
                    "company": company or "Unknown (LinkedIn didn't expose company name for this result)",
                    "location": location,
                    "description": description,
                    "stipend_or_salary": None,
                    "posted_date": None,  # already filtered via listed_at above; not re-parsed from text
                    "recruiter_email": None,  # LinkedIn postings don't expose this
                },
            }
        )

    _update_last_fetch_at()

    print(
        f"[linkedin] kept {len(payloads)}, skipped {skipped_stale} stale "
        f"(older than {max_age_days}d) and {skipped_location} location-mismatched "
        f"({detail_fetches_used} detail fetches used)"
    )
    return payloads