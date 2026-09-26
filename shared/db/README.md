# shared/db

Single source of truth for HireMind's Postgres schema.

- `models.py` — SQLAlchemy models (Job, Match, Draft, Credential, RawJob, InboxFlag)
- `session.py` — engine/session factory, reads `DATABASE_URL` env var
- `alembic/` — migrations; run from this directory

## Usage

Install deps:
    pip install -r requirements.txt

Set your DB URL (or rely on the default in session.py for local dev):
    export DATABASE_URL=postgresql+psycopg2://hiremind:hiremind@localhost:5432/hiremind

Apply migrations:
    cd shared/db
    alembic upgrade head

Generate a new migration after changing models.py:
    cd shared/db
    alembic revision --autogenerate -m "describe the change"

Other services import models/session like:
    from shared.db.models import Job, Match, Draft
    from shared.db.session import get_session