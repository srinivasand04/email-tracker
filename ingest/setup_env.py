"""Fill .env from the clipboard, without ever showing a secret:  python -m ingest.setup_env

Leave this running and click the "copy" button next to each value in the
browser, in any order. Each value is recognised by its shape, written to .env,
and the clipboard is cleared. Only the NAME of each saved setting is printed.

  DATABASE_URL          starts with postgresql:// or postgres://
  GOOGLE_CLIENT_ID      ends with .apps.googleusercontent.com
  GOOGLE_CLIENT_SECRET  starts with GOCSPX-
  ANTHROPIC_API_KEY     starts with sk-ant-api

Windows only (reads the clipboard through PowerShell).
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

from .config import REPO_ROOT

ENV_PATH = REPO_ROOT / ".env"
TIMEOUT_SECONDS = 15 * 60

PATTERNS = {
    "DATABASE_URL": re.compile(r"^postgres(ql)?://\S+$"),
    "GOOGLE_CLIENT_ID": re.compile(r"^[\w-]+\.apps\.googleusercontent\.com$"),
    "GOOGLE_CLIENT_SECRET": re.compile(r"^GOCSPX-[\w-]+$"),
    "ANTHROPIC_API_KEY": re.compile(r"^sk-ant-api[\w-]+$"),
}
PLACEHOLDER_DATABASE_URL = "postgresql://user:password@host/dbname?sslmode=require"


def classify(text: str) -> tuple[str, str] | None:
    """Return (setting name, cleaned value) if the text looks like one of the settings."""
    value = text.strip().strip("'\"")
    # Neon's "copy snippet" may give:  psql 'postgresql://...'
    if value.startswith("psql "):
        value = value[5:].strip().strip("'\"")
    for name, pattern in PATTERNS.items():
        if pattern.match(value):
            return name, value
    return None


def read_env(path: Path) -> dict[str, str]:
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
    return values


def set_env_value(path: Path, name: str, value: str) -> None:
    """Replace the NAME=... line in the .env file, or append it."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    for index, line in enumerate(lines):
        if line.startswith(f"{name}="):
            lines[index] = f"{name}={value}"
            break
    else:
        lines.append(f"{name}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def missing(path: Path) -> list[str]:
    values = read_env(path)
    return [
        name
        for name in PATTERNS
        if not values.get(name) or values[name] == PLACEHOLDER_DATABASE_URL
    ]


def _powershell(command: str) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return result.stdout


# The dashboard's sign-in uses a second Google client (type "Web application").
# With --web, Google client values are saved under these names instead.
WEB_NAMES = {"GOOGLE_CLIENT_ID": "AUTH_GOOGLE_ID", "GOOGLE_CLIENT_SECRET": "AUTH_GOOGLE_SECRET"}


def main(argv: list[str] | None = None) -> int:
    web = "--web" in (sys.argv[1:] if argv is None else argv)
    if web:
        values = read_env(ENV_PATH)
        todo = [name for name in WEB_NAMES.values() if not values.get(name)]
    else:
        todo = missing(ENV_PATH)
    if not todo:
        print("All settings are already in .env.")
        return 0
    print("Waiting for you to copy: " + ", ".join(todo), flush=True)
    deadline = time.time() + TIMEOUT_SECONDS
    while todo and time.time() < deadline:
        found = classify(_powershell("Get-Clipboard -Raw"))
        if found and web:
            found = (WEB_NAMES.get(found[0], ""), found[1])
        if found and found[0] in todo:
            name, value = found
            set_env_value(ENV_PATH, name, value)
            _powershell("Set-Clipboard -Value ' '")  # do not leave the secret on the clipboard
            todo.remove(name)
            print(f"Saved {name}. Still waiting for: {', '.join(todo) or 'nothing'}", flush=True)
        time.sleep(1)
    if todo:
        print("Timed out. Still missing: " + ", ".join(todo), file=sys.stderr)
        return 1
    print("Done. .env is complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
