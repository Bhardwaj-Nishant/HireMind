"""
Entrypoint for ingestion-service. Runs one ingestion cycle (job scraping,
or a Gmail inbox check) and exits — schedule with cron / a container
orchestrator's job runner rather than an internal sleep loop, so restarts
and scheduling stay simple and observable.

The actual scraping/normalization and Gmail logic live in shared/ now
(shared.ingestion, shared.gmail) so gateway-service can trigger the same
cycles on demand from the dashboard. This file is just the CLI wrapper.

Usage:
    python -m app.main scrape --source internshala --max-jobs 10
    python -m app.main scrape --source unstop --work-type job --location remote
    python -m app.main scrape --source linkedin --max-jobs 5
    python -m app.main scrape --source linkedin --force  (bypass the hourly rate gate — use sparingly)
    python -m app.main scrape --source internshala --keywords backend-development,python-development
    python -m app.main check-gmail --days 3 --max-results 25
    python -m app.main push-email-drafts --limit 20
"""
import argparse

from shared.ingestion.registry import SOURCE_NAMES, get_source


def run_scrape_cycle(
    source_name: str, max_jobs: int, work_type: str, location: str, keywords: str | None, max_age_days: int,
    ignore_recency: bool, force: bool,
) -> None:
    from shared.ingestion.normalize import normalize_and_save, save_raw

    source_module = get_source(source_name)
    keyword_list = [k.strip() for k in keywords.split(",")] if keywords else None
    print(
        f"[main] starting ingestion cycle for '{source_name}' "
        f"(max_jobs={max_jobs}, work_type={work_type}, location={location}, "
        f"max_age_days={max_age_days}, ignore_recency={ignore_recency}, keywords={keyword_list or 'from resume'})"
    )

    extra_kwargs = {"force": force} if source_name == "linkedin" else {}

    try:
        payloads = source_module.fetch_all(
            max_jobs=max_jobs, work_type=work_type, location_mode=location, keywords=keyword_list,
            max_age_days=max_age_days, ignore_recency=ignore_recency, **extra_kwargs,
        )
    except Exception as exc:
        # LinkedIn's rate gate (RateLimitedError) surfaces here with a clear
        # wait-time message rather than a raw traceback.
        print(f"[main] scrape failed: {exc}")
        return

    print(f"[main] fetched {len(payloads)} raw pages")

    normalized_count = 0
    for payload in payloads:
        raw_job_id = save_raw(source_name, payload)
        job_id = normalize_and_save(source_name, raw_job_id, payload)
        if job_id:
            normalized_count += 1

    print(f"[main] normalized {normalized_count}/{len(payloads)} into jobs table")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    scrape_parser = subparsers.add_parser("scrape", help="Scrape job/internship listings")
    scrape_parser.add_argument("--source", choices=SOURCE_NAMES, required=True)
    scrape_parser.add_argument("--max-jobs", type=int, default=25)
    scrape_parser.add_argument(
        "--work-type", choices=["internship", "job"], default="internship",
        help="'internship' or 'job' (full-time)"
    )
    scrape_parser.add_argument(
        "--location", choices=["remote", "onsite", "any"], default="any",
        help="Filter by remote/onsite based on each posting's actual location text"
    )
    scrape_parser.add_argument(
        "--max-age-days", type=int, default=1,
        help="Only fetch postings at most this many days old (default: 1)"
    )
    scrape_parser.add_argument(
        "--ignore-recency", action="store_true",
        help="Debug: skip the max-age-days filter entirely, to check raw extraction quality"
    )
    scrape_parser.add_argument(
        "--force", action="store_true",
        help="LinkedIn only: bypass the hourly rate gate. Use sparingly — protects the account."
    )
    scrape_parser.add_argument(
        "--keywords", default=None,
        help="Comma-separated category slugs to override resume-derived search "
             "(e.g. backend-development,python-development). Default: derived from your resume."
    )

    gmail_parser = subparsers.add_parser("check-gmail", help="Check inbox for important new mail")
    gmail_parser.add_argument("--days", type=int, default=3, help="How many days back to check")
    gmail_parser.add_argument("--max-results", type=int, default=25)

    push_parser = subparsers.add_parser(
        "push-email-drafts", help="Push pending recruiter_email drafts into real Gmail drafts"
    )
    push_parser.add_argument("--limit", type=int, default=20)

    args = parser.parse_args()

    if args.command == "scrape":
        run_scrape_cycle(
            args.source, args.max_jobs, args.work_type, args.location, args.keywords, args.max_age_days,
            args.ignore_recency, args.force,
        )
    elif args.command == "check-gmail":
        from shared.gmail.classify import run_inbox_check

        run_inbox_check(days=args.days, max_results=args.max_results)
    elif args.command == "push-email-drafts":
        from shared.gmail.push import push_pending_email_drafts

        push_pending_email_drafts(limit=args.limit)