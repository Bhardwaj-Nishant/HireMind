# ingestion-service

Fetches job postings from external sources and writes them into Postgres
(`raw_jobs` -> `jobs`, via `shared/db/models.py`).

## Structure
- `app/sources/<name>.py` — one module per source; owns the "how do I
  fetch this site" logic. Currently: `internshala.py` (Firecrawl-based).
- `app/normalize.py` — maps a source's raw payload into the shared `Job`
  model, source-agnostic.
- `app/main.py` — CLI entrypoint, runs one ingestion cycle then exits.

## Common job-posting contract
There's no separate schema file — the contract is: every source's
`fetch_all()` must return a list of dicts shaped like
    {"url": "...", "extracted": {"title": "...", "company": "...",
     "location": "...", "description": "..."}}
`normalize.py` maps this uniformly into the shared `Job` model
(`shared/db/models.py`), regardless of which portal it came from.
`intelligence-service` and `gateway-service` only ever read `jobs` —
they don't know or care which source a posting came from.

## Local run
    cp .env.example .env      # fill in FIRECRAWL_API_KEY
    pip install -r requirements.txt -r ../shared/db/requirements.txt
    # from the hiremind/ repo root:
    python run_ingestion.py scrape --source internshala --max-jobs 10
    python run_ingestion.py check-gmail --days 3
    python run_ingestion.py push-email-drafts --limit 10

## Adding a new source
1. Create `app/sources/<name>.py` with a `fetch_all(max_jobs) -> list[dict]`
   function, matching the contract above.
2. Register it in `_load_source()` and `SOURCE_NAMES` in `app/main.py`.
3. If the extracted field names differ, adjust `normalize_and_save` in
   `normalize.py` (or branch on `source` if mappings diverge a lot).

## Scheduling
No internal loop by design — run this as a scheduled job (cron, or your
container platform's job/cron feature) rather than a long-lived process
with `time.sleep`. Internshala: every 15-30 min is fine. LinkedIn (once
added): cap at ~1 request/hour per your earlier decision.