"""Thin wrapper around the Gmail API. Read-only scope only."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import GMAIL_SCOPES, OAuthClient

TOKEN_URI = "https://oauth2.googleapis.com/token"


def credentials_from_refresh_token(refresh_token: str, client: OAuthClient) -> Credentials:
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=client.client_id,
        client_secret=client.client_secret,
        scopes=GMAIL_SCOPES,
    )
    creds.refresh(Request())
    return creds


# Gmail's quota is counted per minute, so a rate-limited call waits this long (seconds)
# before each retry. The library's own retries are too short for a per-minute limit.
RATE_LIMIT_WAITS = (15, 30, 60, 60, 60)


def is_rate_limit(error: Exception) -> bool:
    if not isinstance(error, HttpError):
        return False
    status = int(error.resp.status)
    if status == 429:
        return True
    return status == 403 and "ratelimitexceeded" in str(error).lower()


def execute_with_backoff(request, sleep: Callable[[float], None] = time.sleep):
    """Execute a Gmail API request, waiting and retrying when the quota is exceeded."""
    for wait in RATE_LIMIT_WAITS:
        try:
            return request.execute(num_retries=3)
        except HttpError as error:
            if not is_rate_limit(error):
                raise
            sleep(wait)
    return request.execute(num_retries=3)


class GmailClient:
    def __init__(self, credentials: Credentials) -> None:
        self._service = build("gmail", "v1", credentials=credentials, cache_discovery=False)

    def profile_email(self) -> str:
        profile = execute_with_backoff(self._service.users().getProfile(userId="me"))
        return profile["emailAddress"].lower()

    def list_message_ids(self, query: str) -> Iterator[str]:
        """Ids of all messages matching a Gmail search query (spam and trash excluded)."""
        page_token = None
        while True:
            response = execute_with_backoff(
                self._service.users()
                .messages()
                .list(userId="me", q=query, pageToken=page_token, maxResults=500)
            )
            for item in response.get("messages", []):
                yield item["id"]
            page_token = response.get("nextPageToken")
            if not page_token:
                return

    def get_message(self, message_id: str) -> dict:
        return execute_with_backoff(
            self._service.users().messages().get(userId="me", id=message_id, format="full")
        )
