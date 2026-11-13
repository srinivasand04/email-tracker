"""Sync logic against a fake Gmail and an in-memory store. No network, no database."""

from __future__ import annotations

import pytest

from ingest.db import SyncState
from ingest.sync import OVERLAP_SECONDS, build_query, sync_account

ACCOUNT = "me@example.com"
NOW = 1794320000.0


class FakeGmail:
    def __init__(self, messages: list[dict], fail_on: str | None = None) -> None:
        # Gmail lists newest first
        self.messages = sorted(messages, key=lambda m: int(m["internalDate"]), reverse=True)
        self.fail_on = fail_on
        self.queries: list[str] = []
        self.fetched: list[str] = []

    def list_message_ids(self, query: str):
        self.queries.append(query)
        after_ms = int(query.removeprefix("after:")) * 1000
        return [m["id"] for m in self.messages if int(m["internalDate"]) > after_ms]

    def get_message(self, message_id: str) -> dict:
        if message_id == self.fail_on:
            raise RuntimeError("Gmail API unavailable")
        self.fetched.append(message_id)
        return next(m for m in self.messages if m["id"] == message_id)


class FakeStore:
    """Mirrors PostgresStore semantics: unique on (account, message id), cursor only moves forward."""

    def __init__(self) -> None:
        self.accounts: dict[str, int] = {}
        self.emails: dict[tuple[int, str], dict] = {}
        self.cursor: dict[int, int | None] = {}
        self.last_run_new: dict[int, int] = {}

    def ensure_account(self, email: str) -> int:
        return self.accounts.setdefault(email, len(self.accounts) + 1)

    def get_sync_state(self, account_id: int) -> SyncState:
        return SyncState(self.cursor.get(account_id))

    def existing_message_ids(self, account_id: int, message_ids: list[str]) -> set[str]:
        return {mid for mid in message_ids if (account_id, mid) in self.emails}

    def upsert_emails(self, account_id: int, emails) -> int:
        inserted = 0
        for email in emails:
            key = (account_id, email.gmail_message_id)
            if key not in self.emails:
                inserted += 1
                self.emails[key] = {"category": None, "reviewed": False}
            self.emails[key]["email"] = email
        return inserted

    def record_sync_success(self, account_id: int, last_internal_date_ms, new_messages: int) -> None:
        self.cursor[account_id] = max(self.cursor.get(account_id) or 0, last_internal_date_ms or 0)
        self.last_run_new[account_id] = new_messages

    def record_sync_error(self, account_id: int, error: str) -> None:
        raise AssertionError("not expected")


@pytest.fixture
def messages(all_messages) -> list[dict]:
    return sorted(all_messages.values(), key=lambda m: int(m["internalDate"]))  # oldest first


def test_build_query_first_run_uses_initial_window():
    assert build_query(None, now_s=1_000_000, initial_days=2) == f"after:{1_000_000 - 2 * 86400}"


def test_build_query_later_runs_use_cursor_minus_overlap():
    assert build_query(5_000_000_000, now_s=5_000_000, initial_days=60) == f"after:{5_000_000 - OVERLAP_SECONDS}"


def test_build_query_never_goes_back_further_than_the_window():
    now = 100 * 86400
    old_cursor_ms = 10 * 86400 * 1000  # last sync 90 days ago (PC was off)
    assert build_query(old_cursor_ms, now_s=now, initial_days=60) == f"after:{now - 60 * 86400}"


def test_build_query_backfill_rereads_the_whole_window():
    now = 100 * 86400
    recent_cursor_ms = (now - 3600) * 1000
    assert build_query(recent_cursor_ms, now_s=now, initial_days=60, backfill=True) == f"after:{now - 60 * 86400}"


def test_backfill_adds_older_mail_without_moving_the_cursor_back(messages):
    newest = max(int(m["internalDate"]) for m in messages)
    now = newest / 1000 + 60
    store = FakeStore()
    # first load with a 0-day window only sees nothing older than now
    sync_account(FakeGmail(messages), store, ACCOUNT, initial_days=0, now_s=now)
    assert len(store.emails) == 0
    store.cursor[1] = newest  # pretend the cursor is already at the newest message

    result = sync_account(FakeGmail(messages), store, ACCOUNT, initial_days=60, now_s=now, backfill=True)

    assert result.inserted == 4
    assert store.cursor[1] == newest


def test_first_sync_stores_inbound_mail_and_skips_sent(messages):
    gmail, store = FakeGmail(messages), FakeStore()

    result = sync_account(gmail, store, ACCOUNT, initial_days=14, now_s=NOW)

    assert result.listed == 5
    assert result.inserted == 4
    assert result.skipped == 1  # sent_by_me
    assert len(store.emails) == 4
    assert (1, "18f0d00000000003") not in store.emails
    # cursor = newest message seen
    assert store.cursor[1] == max(int(m["internalDate"]) for m in messages)
    # stored oldest first, so an interrupted run leaves no gap
    assert gmail.fetched == [m["id"] for m in reversed(gmail.messages)]


def test_rerun_is_idempotent_and_does_not_refetch(messages):
    gmail, store = FakeGmail(messages), FakeStore()
    sync_account(gmail, store, ACCOUNT, initial_days=14, now_s=NOW)
    cursor_before = store.cursor[1]
    gmail.fetched.clear()

    result = sync_account(gmail, store, ACCOUNT, initial_days=14, now_s=NOW)

    assert result.inserted == 0
    assert len(store.emails) == 4
    assert store.cursor[1] == cursor_before
    assert gmail.queries[-1] == f"after:{cursor_before // 1000 - OVERLAP_SECONDS}"
    # everything inside the overlap window is already stored, nothing is downloaded again
    assert all(mid not in gmail.fetched for (_, mid) in store.emails)


def test_only_new_mail_is_added_on_next_sync(messages):
    old, new = messages[:3], messages[3:]
    store = FakeStore()
    sync_account(FakeGmail(old), store, ACCOUNT, initial_days=14, now_s=NOW)
    stored_before = len(store.emails)

    gmail = FakeGmail(messages)
    result = sync_account(gmail, store, ACCOUNT, initial_days=14, now_s=NOW)

    new_inbound = [m for m in new if m["labelIds"] != ["SENT"]]
    assert result.inserted == len(new_inbound)
    assert len(store.emails) == stored_before + len(new_inbound)


def test_failure_midway_keeps_cursor_and_rerun_completes(messages):
    store = FakeStore()
    newest = max(messages, key=lambda m: int(m["internalDate"]))

    with pytest.raises(RuntimeError):
        sync_account(FakeGmail(messages, fail_on=newest["id"]), store, ACCOUNT, initial_days=14, now_s=NOW)
    assert store.cursor.get(1) is None  # cursor not advanced by a failed run

    result = sync_account(FakeGmail(messages), store, ACCOUNT, initial_days=14, now_s=NOW)
    assert len(store.emails) == 4
    assert result.inserted + result.already_stored == 4


def test_accounts_are_kept_separate(messages):
    store = FakeStore()
    sync_account(FakeGmail(messages), store, "a@example.com", initial_days=14, now_s=NOW)
    sync_account(FakeGmail(messages), store, "b@example.com", initial_days=14, now_s=NOW)

    assert len(store.emails) == 8
    assert {account_id for account_id, _ in store.emails} == {1, 2}
