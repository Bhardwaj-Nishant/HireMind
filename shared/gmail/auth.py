"""
Gmail OAuth handling.

First run: opens a browser for you to sign in and consent, then stores
the resulting token in the `credentials` table (platform='gmail') so
future runs reuse it silently, refreshing automatically when expired.

Setup required before first run (one-time, in Google Cloud Console):
  1. Create a project (or reuse one) at console.cloud.google.com
  2. Enable the "Gmail API" for that project
  3. Create OAuth 2.0 credentials -> Application type: "Desktop app"
  4. Download the JSON and save it as the path pointed to by
     GOOGLE_CLIENT_SECRETS_PATH (see .env.example)
  5. On the OAuth consent screen, add your own Google account as a
     "test user" if the app is in Testing mode (normal for personal use)

Scopes requested:
  - gmail.readonly — to read inbox messages for classification
  - gmail.compose  — to create (never send) drafts later, for the
    recruiter-email-to-Gmail-draft feature
"""
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from shared.db.models import Credential
from shared.db.session import get_session

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]

CLIENT_SECRETS_PATH = os.environ.get(
    "GOOGLE_CLIENT_SECRETS_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "ingestion-service", "client_secrets.json"),
)


def _load_stored_credentials() -> Credentials | None:
    with get_session() as session:
        row = session.query(Credential).filter_by(platform="gmail").one_or_none()
        if not row:
            return None
        return Credentials.from_authorized_user_info(row.credential_data, SCOPES)


def _store_credentials(creds: Credentials) -> None:
    data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }
    with get_session() as session:
        row = session.query(Credential).filter_by(platform="gmail").one_or_none()
        if row:
            row.credential_data = data
        else:
            row = Credential(platform="gmail", auth_type="oauth2", credential_data=data)
            session.add(row)


def get_credentials() -> Credentials:
    """Returns valid Gmail API credentials, running the OAuth consent flow
    only if no usable token is stored yet (or it can't be refreshed)."""
    creds = _load_stored_credentials()

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _store_credentials(creds)
        return creds

    # No usable stored token — run the interactive consent flow (opens browser)
    if not os.path.exists(CLIENT_SECRETS_PATH):
        raise FileNotFoundError(
            f"Gmail OAuth client secrets not found at {CLIENT_SECRETS_PATH}. "
            f"Download it from Google Cloud Console (OAuth client, Desktop app type) "
            f"and set GOOGLE_CLIENT_SECRETS_PATH, or place it at ./client_secrets.json"
        )

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_PATH, SCOPES)
    creds = flow.run_local_server(port=0)
    _store_credentials(creds)
    return creds