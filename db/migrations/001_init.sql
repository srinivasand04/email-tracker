-- Phase 1 schema: accounts, emails, sync state.
-- Applied by `python -m ingest.migrate` (tracked in schema_migrations).

CREATE TABLE accounts (
    id          SERIAL PRIMARY KEY,
    email       TEXT NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE emails (
    id                BIGSERIAL PRIMARY KEY,
    account_id        INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    gmail_message_id  TEXT NOT NULL,
    gmail_thread_id   TEXT NOT NULL,

    -- Written by the ingest job (Phase 1)
    sender_name       TEXT NOT NULL DEFAULT '',
    sender_email      TEXT NOT NULL DEFAULT '',
    subject           TEXT NOT NULL DEFAULT '',
    received_at       TIMESTAMPTZ NOT NULL,
    snippet           TEXT NOT NULL DEFAULT '',
    -- First part of the body, kept only until the email is classified.
    -- The classifier (Phase 2) sets this to NULL once it has written `summary`.
    body_excerpt      TEXT,
    gmail_labels      TEXT[] NOT NULL DEFAULT '{}',
    is_list_mail      BOOLEAN NOT NULL DEFAULT FALSE,  -- has List-Unsubscribe / List-Id
    has_attachments   BOOLEAN NOT NULL DEFAULT FALSE,
    gmail_link        TEXT NOT NULL,

    -- Written by the classifier (Phase 2) or corrected by the user (Phase 3)
    category          TEXT CHECK (category IN (
                          'direct_opportunity',   -- 1 recruiter / hiring manager writing personally
                          'application_update',   -- 2 application / interview update
                          'company_postings',     -- 3 openings sent by companies / career sites
                          'job_alerts',           -- 4 LinkedIn / Naukri / Indeed digests
                          'visa_government',      -- 5
                          'finance_bills',        -- 6
                          'security_account',     -- 7
                          'personal',             -- 8 personal / needs reply
                          'other'                 -- 9 everything else, hidden by default
                      )),
    priority          TEXT CHECK (priority IN ('high', 'medium', 'low')),
    summary           TEXT,
    reason            TEXT,
    classified_by     TEXT CHECK (classified_by IN ('rules', 'llm', 'user')),
    classified_at     TIMESTAMPTZ,

    -- Written by the web app (Phase 3)
    reviewed          BOOLEAN NOT NULL DEFAULT FALSE,
    reviewed_at       TIMESTAMPTZ,

    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (account_id, gmail_message_id)
);

CREATE INDEX emails_received_at_idx ON emails (received_at DESC);
CREATE INDEX emails_category_idx ON emails (category, received_at DESC);
CREATE INDEX emails_unclassified_idx ON emails (id) WHERE category IS NULL;
CREATE INDEX emails_unreviewed_idx ON emails (received_at DESC) WHERE NOT reviewed;

CREATE TABLE sync_state (
    account_id             INTEGER PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
    -- Gmail internalDate (ms since epoch) of the newest message stored so far.
    -- The next sync asks Gmail for mail after this point, minus a safety overlap.
    last_internal_date_ms  BIGINT,
    last_synced_at         TIMESTAMPTZ,
    last_status            TEXT CHECK (last_status IN ('ok', 'error')),
    last_error             TEXT,
    last_run_new_messages  INTEGER NOT NULL DEFAULT 0
);

-- Roadmap (not built yet): a `jobs` table holding structured job records
-- extracted from job emails, e.g.
--   jobs(id, email_id REFERENCES emails(id), company, role, location,
--        apply_link, status, ...)
-- One email can yield many jobs (digests), so jobs hang off emails.id.
-- Later tables for resumes and applications will reference jobs.id.
