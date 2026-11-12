"""Upsert logic against a real Postgres.

Skipped unless TEST_DATABASE_URL points at a throwaway database
(the tables in it are dropped and recreated). Quick local one with Docker:

    docker run --rm -d --name et-test-pg -e POSTGRES_PASSWORD=test -p 55432:5432 postgres:16
    $env:TEST_DATABASE_URL = "postgresql://postgres:test@localhost:55432/postgres"
"""

from __future__ import annotations

import os
from dataclasses import replace

import pytest

from ingest import db
from ingest.parser import parse_message

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")

ACCOUNT = "me@example.com"


@pytest.fixture
def store():
    with db.connect(TEST_DATABASE_URL) as conn:
        conn.execute(
            "DROP TABLE IF EXISTS sync_state, emails, accounts, schema_migrations CASCADE"
        )
        conn.commit()
        db.apply_migrations(conn)
        yield db.PostgresStore(conn)


@pytest.fixture
def emails(all_messages):
    return [
        parse_message(message, ACCOUNT)
        for name, message in sorted(all_messages.items())
        if name != "sent_by_me"
    ]


def count(store, sql="SELECT count(*) FROM emails"):
    return store.conn.execute(sql).fetchone()[0]


def test_migrations_are_safe_to_rerun(store):
    assert db.apply_migrations(store.conn) == []


def test_ensure_account_returns_same_id(store):
    assert store.ensure_account(ACCOUNT) == store.ensure_account(ACCOUNT.upper())
    assert count(store, "SELECT count(*) FROM accounts") == 1


def test_upsert_inserts_once(store, emails):
    account_id = store.ensure_account(ACCOUNT)

    assert store.upsert_emails(account_id, emails) == len(emails)
    assert store.upsert_emails(account_id, emails) == 0
    assert count(store) == len(emails)
    assert store.existing_message_ids(
        account_id, [emails[0].gmail_message_id, "unknown"]
    ) == {emails[0].gmail_message_id}


def test_same_message_id_in_two_accounts_is_two_rows(store, emails):
    first = store.ensure_account("a@example.com")
    second = store.ensure_account("b@example.com")

    store.upsert_emails(first, emails[:1])
    store.upsert_emails(second, emails[:1])

    assert count(store) == 2


def test_upsert_keeps_classification_review_and_cleared_excerpt(store, emails):
    account_id = store.ensure_account(ACCOUNT)
    email = emails[0]
    store.upsert_emails(account_id, [email])
    # what Phase 2 (classifier) and Phase 3 (web app) will do
    store.conn.execute(
        "UPDATE emails SET category = 'direct_opportunity', priority = 'high',"
        " summary = 'Recruiter intro', body_excerpt = NULL, reviewed = TRUE"
    )
    store.conn.commit()

    changed = replace(email, gmail_labels=["INBOX"], snippet="changed", body_excerpt="again")
    assert store.upsert_emails(account_id, [changed]) == 0

    row = store.conn.execute(
        "SELECT category, priority, summary, body_excerpt, reviewed, gmail_labels, snippet FROM emails"
    ).fetchone()
    assert row == ("direct_opportunity", "high", "Recruiter intro", None, True, ["INBOX"], "changed")


def test_sync_state_cursor_only_moves_forward(store):
    account_id = store.ensure_account(ACCOUNT)
    assert store.get_sync_state(account_id).last_internal_date_ms is None

    store.record_sync_success(account_id, 2000, 5)
    store.record_sync_success(account_id, 1000, 0)
    assert store.get_sync_state(account_id).last_internal_date_ms == 2000

    store.record_sync_error(account_id, "boom")
    row = store.conn.execute("SELECT last_status, last_error, last_internal_date_ms FROM sync_state").fetchone()
    assert row == ("error", "boom", 2000)


def test_invalid_category_is_rejected(store, emails):
    import psycopg

    account_id = store.ensure_account(ACCOUNT)
    store.upsert_emails(account_id, emails[:1])
    with pytest.raises(psycopg.errors.CheckViolation):
        store.conn.execute("UPDATE emails SET category = 'nonsense'")
    store.conn.rollback()
