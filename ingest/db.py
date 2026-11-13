"""Postgres access for the ingest job."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import psycopg

from .config import MIGRATIONS_DIR
from .parser import ParsedEmail


@dataclass(frozen=True)
class SyncState:
    last_internal_date_ms: int | None


def connect(database_url: str) -> psycopg.Connection:
    return psycopg.connect(database_url)


def apply_migrations(conn: psycopg.Connection, migrations_dir: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply any db/migrations/*.sql not applied yet, in filename order. Safe to rerun."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
    )
    done = {row[0] for row in conn.execute("SELECT name FROM schema_migrations")}
    applied = []
    for path in sorted(migrations_dir.glob("*.sql")):
        if path.name in done:
            continue
        with conn.transaction():
            conn.execute(path.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (path.name,))
        applied.append(path.name)
    conn.commit()
    return applied


_UPSERT_EMAIL = """
INSERT INTO emails (
    account_id, gmail_message_id, gmail_thread_id, sender_name, sender_email,
    subject, received_at, snippet, body_excerpt, gmail_labels,
    is_list_mail, has_attachments, gmail_link
) VALUES (
    %(account_id)s, %(gmail_message_id)s, %(gmail_thread_id)s, %(sender_name)s, %(sender_email)s,
    %(subject)s, %(received_at)s, %(snippet)s, %(body_excerpt)s, %(gmail_labels)s,
    %(is_list_mail)s, %(has_attachments)s, %(gmail_link)s
)
ON CONFLICT (account_id, gmail_message_id) DO UPDATE SET
    -- Only refresh what Gmail owns. Classification, the reviewed flag and
    -- body_excerpt (cleared after classification) are never overwritten.
    gmail_thread_id = EXCLUDED.gmail_thread_id,
    sender_name     = EXCLUDED.sender_name,
    sender_email    = EXCLUDED.sender_email,
    subject         = EXCLUDED.subject,
    received_at     = EXCLUDED.received_at,
    snippet         = EXCLUDED.snippet,
    gmail_labels    = EXCLUDED.gmail_labels,
    is_list_mail    = EXCLUDED.is_list_mail,
    has_attachments = EXCLUDED.has_attachments,
    gmail_link      = EXCLUDED.gmail_link,
    updated_at      = now()
RETURNING (xmax = 0) AS inserted
"""


class PostgresStore:
    """Everything the sync job needs from the database."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self.conn = conn

    def ensure_account(self, email: str) -> int:
        row = self.conn.execute(
            "INSERT INTO accounts (email) VALUES (%s)"
            " ON CONFLICT (email) DO UPDATE SET email = EXCLUDED.email RETURNING id",
            (email.lower(),),
        ).fetchone()
        self.conn.commit()
        return row[0]

    def get_sync_state(self, account_id: int) -> SyncState:
        row = self.conn.execute(
            "SELECT last_internal_date_ms FROM sync_state WHERE account_id = %s", (account_id,)
        ).fetchone()
        return SyncState(row[0] if row else None)

    def existing_message_ids(self, account_id: int, message_ids: list[str]) -> set[str]:
        if not message_ids:
            return set()
        rows = self.conn.execute(
            "SELECT gmail_message_id FROM emails"
            " WHERE account_id = %s AND gmail_message_id = ANY(%s)",
            (account_id, message_ids),
        )
        return {row[0] for row in rows}

    def upsert_emails(self, account_id: int, emails: list[ParsedEmail]) -> int:
        """Insert or refresh emails in one transaction. Returns how many rows were new."""
        inserted = 0
        with self.conn.transaction():
            for email in emails:
                row = self.conn.execute(
                    _UPSERT_EMAIL,
                    {
                        "account_id": account_id,
                        "gmail_message_id": email.gmail_message_id,
                        "gmail_thread_id": email.gmail_thread_id,
                        "sender_name": email.sender_name,
                        "sender_email": email.sender_email,
                        "subject": email.subject,
                        "received_at": email.received_at,
                        "snippet": email.snippet,
                        "body_excerpt": email.body_excerpt,
                        "gmail_labels": email.gmail_labels,
                        "is_list_mail": email.is_list_mail,
                        "has_attachments": email.has_attachments,
                        "gmail_link": email.gmail_link,
                    },
                ).fetchone()
                inserted += 1 if row[0] else 0
        self.conn.commit()
        return inserted

    def record_sync_success(
        self, account_id: int, last_internal_date_ms: int | None, new_messages: int
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO sync_state (account_id, last_internal_date_ms, last_synced_at,
                                    last_status, last_error, last_run_new_messages)
            VALUES (%s, %s, now(), 'ok', NULL, %s)
            ON CONFLICT (account_id) DO UPDATE SET
                -- the cursor only ever moves forward
                last_internal_date_ms = GREATEST(
                    COALESCE(sync_state.last_internal_date_ms, 0),
                    COALESCE(EXCLUDED.last_internal_date_ms, 0)),
                last_synced_at = now(),
                last_status = 'ok',
                last_error = NULL,
                last_run_new_messages = EXCLUDED.last_run_new_messages
            """,
            (account_id, last_internal_date_ms, new_messages),
        )
        self.conn.commit()

    def unclassified_emails(self, limit: int | None = None):
        from .classify import EmailToClassify

        rows = self.conn.execute(
            """
            SELECT e.id, a.email, e.sender_name, e.sender_email, e.subject, e.snippet,
                   COALESCE(e.body_excerpt, ''), e.is_list_mail, e.gmail_labels
            FROM emails e JOIN accounts a ON a.id = e.account_id
            WHERE e.category IS NULL
            ORDER BY e.received_at DESC
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
        self.conn.commit()
        return [EmailToClassify(*row) for row in rows]

    def still_unclassified(self, email_id: int) -> bool:
        row = self.conn.execute(
            "SELECT category IS NULL FROM emails WHERE id = %s", (email_id,)
        ).fetchone()
        self.conn.commit()
        return bool(row and row[0])

    def save_classification(self, email_id: int, result) -> None:
        """Store a classification and drop the body excerpt. Never overwrites an existing one."""
        self.conn.execute(
            """
            UPDATE emails SET category = %s, priority = %s, summary = %s, reason = %s,
                classified_by = %s, classified_at = now(), body_excerpt = NULL, updated_at = now()
            WHERE id = %s AND category IS NULL
            """,
            (result.category, result.priority, result.summary, result.reason,
             result.classified_by, email_id),
        )
        self.conn.commit()

    def record_sync_error(self, account_id: int, error: str) -> None:
        self.conn.rollback()
        self.conn.execute(
            """
            INSERT INTO sync_state (account_id, last_synced_at, last_status, last_error)
            VALUES (%s, now(), 'error', %s)
            ON CONFLICT (account_id) DO UPDATE SET
                last_synced_at = now(), last_status = 'error', last_error = EXCLUDED.last_error
            """,
            (account_id, error[:2000]),
        )
        self.conn.commit()
