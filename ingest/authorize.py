"""One-time Gmail consent for one account:  python -m ingest.authorize

Opens a browser, asks for READ-ONLY Gmail access, and saves the refresh token
to tokens/<address>.json (git-ignored). Run it once per Gmail account.
The token is never printed.
"""

from __future__ import annotations

import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

from . import config
from .gmail_client import TOKEN_URI, GmailClient


def main() -> int:
    config.load_env()
    try:
        client = config.oauth_client()
    except config.ConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client.client_id,
                "client_secret": client.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": TOKEN_URI,
                "redirect_uris": ["http://localhost"],
            }
        },
        scopes=config.GMAIL_SCOPES,
    )
    print("A browser window will open. Pick the Gmail account to connect and allow read-only access.")
    # access_type=offline + prompt=consent guarantees Google returns a refresh token.
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    if not creds.refresh_token:
        print("Error: Google did not return a refresh token. Run the command again.", file=sys.stderr)
        return 1

    email = GmailClient(creds).profile_email()
    config.TOKENS_DIR.mkdir(exist_ok=True)
    path = config.TOKENS_DIR / f"{email}.json"
    path.write_text(
        json.dumps({"email": email, "refresh_token": creds.refresh_token}, indent=2),
        encoding="utf-8",
    )
    print(f"Connected {email}. Token saved to {path} (git-ignored, keep it private).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
