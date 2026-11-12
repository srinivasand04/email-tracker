"""Pull new mail for every configured account into Postgres:  python -m ingest.sync

Idempotent: rerunning never duplicates rows and never overwrites classification
or the reviewed flag. Each account is synced independently; one failing account
does not stop the others, but the process exits non-zero.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from typing import Protocol

from . import config
from .parser import ParsedEmail, parse_message, should_skip

# Re-ask Gmail for the last hour before the cursor on every run. Messages can be
# delivered slightly out of order; the overlap is free because known ids are skipped.
OVERLAP_SECONDS = 3600
BATCH_SIZE = 50


class Gmail(Protocol):
    def list_message_ids(self, query: str): ...
    def get_message(self, message_id: str) -> dict: ...


class Store(Protocol):
    def ensure_account(self, email: str) -> int: ...
    def get_sync_state(self, account_id: int): ...
    def existing_message_ids(self, account_id: int, message_ids: list[str]) -> set[str]: ...
    def upsert_emails(self, account_id: int, emails: list[ParsedEmail]) -> int: ...
    def record_sync_success(self, account_id: int, last_internal_date_ms, new_messages: int) -> None: ...
    def record_sync_error(self, account_id: int, error: str) -> None: ...


@dataclass(frozen=True)
class SyncResult:
    listed: int
    already_stored: int
    skipped: int
    inserted: int


def build_query(last_internal_date_ms: int | None, now_s: float, initial_days: int) -> str:
    """Gmail search query for mail newer than the last sync (or the initial window)."""
    if last_internal_date_ms is None:
        after = int(now_s) - initial_days * 86400
    else:
        after = last_internal_date_ms // 1000 - OVERLAP_SECONDS
    return f"after:{after}"


def sync_account(
    gmail: Gmail,
    store: Store,
    account_email: str,
    *,
    initial_days: int,
    now_s: float | None = None,
) -> SyncResult:
    account_id = store.ensure_account(account_email)
    state = store.get_sync_state(account_id)
    query = build_query(state.last_internal_date_ms, now_s or time.time(), initial_days)

    listed = list(dict.fromkeys(gmail.list_message_ids(query)))
    known = store.existing_message_ids(account_id, listed)
    todo = [message_id for message_id in listed if message_id not in known]

    inserted = skipped = 0
    newest_ms = state.last_internal_date_ms
    batch: list[ParsedEmail] = []

    def flush() -> None:
        nonlocal inserted, newest_ms
        if not batch:
            return
        inserted += store.upsert_emails(account_id, batch)
        newest_ms = max([newest_ms or 0] + [email.internal_date_ms for email in batch])
        batch.clear()

    # Gmail lists newest first; store oldest first so an interrupted run
    # leaves no gap behind the newest stored message.
    for message_id in reversed(todo):
        message = gmail.get_message(message_id)
        if should_skip(message.get("labelIds", [])):
            skipped += 1
            # still move the cursor past it, so it is not fetched again next run
            newest_ms = max(newest_ms or 0, int(message.get("internalDate", 0)))
            continue
        batch.append(parse_message(message, account_email))
        if len(batch) >= BATCH_SIZE:
            flush()
    flush()

    store.record_sync_success(account_id, newest_ms, inserted)
    return SyncResult(listed=len(listed), already_stored=len(known), skipped=skipped, inserted=inserted)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync Gmail accounts into Postgres.")
    parser.add_argument("--account", help="sync only this Gmail address")
    args = parser.parse_args(argv)

    # Imported here so the pure logic above can be tested without these packages configured.
    from . import db
    from .gmail_client import GmailClient, credentials_from_refresh_token

    config.load_env()
    try:
        database_url = config.require_env("DATABASE_URL")
        client = config.oauth_client()
        tokens = config.load_refresh_tokens()
    except config.ConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.account:
        tokens = {email: token for email, token in tokens.items() if email == args.account.lower()}
    if not tokens:
        print("No Gmail accounts configured. Run: python -m ingest.authorize", file=sys.stderr)
        return 2

    failures = 0
    with db.connect(database_url) as conn:
        db.apply_migrations(conn)
        store = db.PostgresStore(conn)
        for email, refresh_token in tokens.items():
            try:
                gmail = GmailClient(credentials_from_refresh_token(refresh_token, client))
                result = sync_account(gmail, store, email, initial_days=config.initial_sync_days())
                print(
                    f"{email}: {result.inserted} new, {result.already_stored} already stored, "
                    f"{result.skipped} skipped (sent/drafts), {result.listed} listed"
                )
            except Exception as exc:  # keep going with the other accounts
                failures += 1
                print(f"{email}: FAILED - {type(exc).__name__}: {exc}", file=sys.stderr)
                try:
                    store.record_sync_error(store.ensure_account(email), f"{type(exc).__name__}: {exc}")
                except Exception:
                    pass
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
