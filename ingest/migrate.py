"""Apply database migrations:  python -m ingest.migrate"""

from __future__ import annotations

import sys

from . import config, db


def main() -> int:
    config.load_env()
    try:
        database_url = config.require_env("DATABASE_URL")
    except config.ConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    with db.connect(database_url) as conn:
        applied = db.apply_migrations(conn)
    if applied:
        print("Applied migrations: " + ", ".join(applied))
    else:
        print("Database is already up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
