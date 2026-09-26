# gateway-service

Single API entry point for the (future) dashboard. Read-mostly REST API
over `matches`, `drafts`, `inbox_flags` — plus two PATCH endpoints for
the human-in-the-loop actions (mark a match applied/dismissed, mark an
inbox item reviewed).

No auth — single-user project running locally/on your own server.

## Endpoints
- GET  /health
- GET  /matches?status=&min_score=&limit=
- PATCH /matches/{id}          body: {"status": "applied"|"dismissed"|"pending"}
- GET  /matches/{id}/drafts
- GET  /inbox?importance=&reviewed=&limit=
- PATCH /inbox/{id}            body: {"reviewed": true}

## Run
    pip install -r requirements.txt -r ../shared/db/requirements.txt
    # from the hiremind/ repo root:
    $env:DATABASE_URL = "postgresql+psycopg2://hiremind:hiremind@localhost:5432/hiremind"
    py run_gateway.py

Then open http://127.0.0.1:8000/docs for interactive Swagger UI.