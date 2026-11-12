"""Thin wrapper around the Gmail API. Read-only scope only."""

from __future__ import annotations

from collections.abc import Iterator

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

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


class GmailClient:
    def __init__(self, credentials: Credentials) -> None:
        self._service = build("gmail", "v1", credentials=credentials, cache_discovery=False)

    def profile_email(self) -> str:
        profile = self._service.users().getProfile(userId="me").execute(num_retries=3)
        return profile["emailAddress"].lower()

    def list_message_ids(self, query: str) -> Iterator[str]:
        """Ids of all messages matching a Gmail search query (spam and trash excluded)."""
        page_token = None
        while True:
            response = (
                self._service.users()
                .messages()
                .list(userId="me", q=query, pageToken=page_token, maxResults=500)
                .execute(num_retries=3)
            )
            for item in response.get("messages", []):
                yield item["id"]
            page_token = response.get("nextPageToken")
            if not page_token:
                return

    def get_message(self, message_id: str) -> dict:
        return (
            self._service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute(num_retries=3)
        )
