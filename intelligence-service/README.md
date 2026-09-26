# intelligence-service

Claude-powered matching (and later: generation, drafting) logic.

## Structure
- `app/claude_client.py` — thin Anthropic SDK wrapper, shared across matching/generation
- `app/resume_store.py`  — loads resume.txt once, cached
- `app/matcher.py`       — scores unmatched jobs against the resume, writes to `matches`
- `app/main.py`          — CLI entrypoint

## Setup
1. Place your resume as plain text at `intelligence-service/resume.txt`
   (or set RESUME_PATH to point elsewhere).
2. cp .env.example .env, fill in ANTHROPIC_API_KEY.
3. Install deps (run from repo root so `shared` resolves):
       py -m pip install -r intelligence-service/requirements.txt -r shared/db/requirements.txt

## Run
From the repo root (same pattern as ingestion-service):
    $env:ANTHROPIC_API_KEY = "..."
    $env:DATABASE_URL = "postgresql+psycopg2://hiremind:hiremind@localhost:5432/hiremind"
    py run_matching.py match --limit 10

## Notes
- Idempotent: `matches.job_id` is unique, so re-running only scores jobs
  that don't have a match yet — no duplicate Claude calls/cost.
- Score is 0-100 with a short reasoning string, stored per match for
  the dashboard to display later.