"""Configuration loaded from .env / environment variables."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
TOKENS_DIR = REPO_ROOT / "tokens"
MIGRATIONS_DIR = REPO_ROOT / "db" / "migrations"

# The only scope this project ever requests. Read-only: cannot send, delete or modify mail.
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class ConfigError(RuntimeError):
    pass


def load_env() -> None:
    load_dotenv(REPO_ROOT / ".env")


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(f"{name} is not set. Add it to .env (see .env.example).")
    return value


@dataclass(frozen=True)
class OAuthClient:
    client_id: str
    client_secret: str


def oauth_client() -> OAuthClient:
    return OAuthClient(require_env("GOOGLE_CLIENT_ID"), require_env("GOOGLE_CLIENT_SECRET"))


def initial_sync_days() -> int:
    return int(os.environ.get("INITIAL_SYNC_DAYS", "") or "60")


def load_refresh_tokens(tokens_dir: Path = TOKENS_DIR) -> dict[str, str]:
    """Return {gmail address: refresh token} for every configured account.

    Sources, merged (environment wins):
      1. tokens/<address>.json files written by `python -m ingest.authorize`
      2. GMAIL_REFRESH_TOKENS, a JSON object, for GitHub Actions
    """
    tokens: dict[str, str] = {}
    if tokens_dir.is_dir():
        for path in sorted(tokens_dir.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            tokens[data["email"].lower()] = data["refresh_token"]

    raw = os.environ.get("GMAIL_REFRESH_TOKENS", "").strip()
    if raw:
        try:
            from_env = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ConfigError("GMAIL_REFRESH_TOKENS is not valid JSON.") from exc
        if not isinstance(from_env, dict):
            raise ConfigError("GMAIL_REFRESH_TOKENS must be a JSON object of address -> token.")
        tokens.update({email.lower(): token for email, token in from_env.items()})
    return tokens
