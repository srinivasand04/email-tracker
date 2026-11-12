-- Phase 3: small key/value table for the web app (last visit times), and an
-- index for the per-account filter.

CREATE TABLE app_state (
    key    TEXT PRIMARY KEY,
    value  TIMESTAMPTZ
);

CREATE INDEX emails_account_idx ON emails (account_id, received_at DESC);
