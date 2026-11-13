# Email Tracker - notes for Claude

Personal app for one user (Python developer, Windows 11, PowerShell). Reads 3 Gmail
accounts, classifies mail, shows the important ones in a private web app. Main goal:
finding job opportunities. Full plan, categories and phases: `README.md`.

## Key decisions (agreed with the user - do not reopen)

- Gmail API with OAuth, scope `gmail.readonly` ONLY. Never add a write scope.
- OAuth client type "Desktop app"; Google Cloud app must be "In production".
  Published to "In production" on 2026-11-13 (project `email-tracker-514521`).
- Dashboard is deployed on Vercel (free Hobby plan) from `web/`: https://email-tracker-zeta-seven.vercel.app
  Every push to `main` redeploys. Sign-in: Auth.js + a second Google client ("Web application",
  `email-tracker-web`), only ALLOWED_EMAILS. Sync and classification stay on the owner's PC
  (Windows task "Email Tracker sync", every 3 hours, local Ollama).
- Ingest runs every 3 hours via a Windows scheduled task on the owner's PC (free; local Ollama).
- Owner wants only free tools. Classifier: rules first, then local Ollama `qwen3:8b`; `claude-haiku-5-5` is optional and unused. Send only
  sender, subject and the first part of the body. Store a one-line summary, not bodies.
- Postgres on a free tier (Neon). Web app: Next.js on Vercel, PWA, Google sign-in
  limited to the user's own addresses.
- Phases: 1 Ingest, 2 Classify, 3 Dashboard, 4 Deploy, 5 Alerts. Do not start a phase
  until the previous one is confirmed working by the user.
- Roadmap: resume upload and applying from the app, then automated applying. Keep job
  emails extractable into a `jobs` table (company, role, location, apply link) that
  references `emails.id`.

## Rules

- Secrets live in `.env` and `tokens/` (both git-ignored). Never ask the user to paste
  a secret into chat, never print tokens, never commit them.
- Test fixtures must be invented mail, never the user's real mail.
- `emails.body_excerpt` is temporary: the classifier must set it to NULL after writing
  `summary`.
- The upsert in `ingest/db.py` must never overwrite `category`, `priority`, `summary`,
  `reason`, `reviewed` or a cleared `body_excerpt`.
- Schema changes: add a new numbered file in `db/migrations/`; never edit an applied one.
- Category slugs are fixed by the CHECK constraint in `db/migrations/001_init.sql`.

## Commands (PowerShell, from the repo root)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m pytest                 # tests (db tests need TEST_DATABASE_URL)
.venv\Scripts\python -m ingest.migrate         # apply db/migrations
.venv\Scripts\python -m ingest.setup_env       # fill .env from the clipboard, secrets never shown
.venv\Scripts\python -m ingest.authorize       # one-time consent per Gmail account
.venv\Scripts\python -m ingest.sync            # sync all accounts; --account <address> for one
.venv\Scripts\python -m ingest.classify       # rules, then local Ollama qwen3:8b (free)
.venv\Scripts\python tests\make_fixtures.py    # regenerate fixtures
npm --prefix web run dev                       # dashboard on http://127.0.0.1:3000 (reads ../.env)
npm --prefix web run build                     # type-check + production build
```

## Layout

- `ingest/parser.py` - pure Gmail message -> `ParsedEmail` (no I/O)
- `ingest/sync.py` - sync loop; cursor = newest `internalDate`, 1 hour overlap, known ids skipped
- `ingest/db.py` - `PostgresStore`, migrations runner
- `ingest/gmail_client.py`, `ingest/authorize.py`, `ingest/config.py`
- `ingest/classify.py` - SENDER_RULES, then local Ollama (or optional Claude) with a JSON-schema output; clears body_excerpt
- `web/` - Next.js 15 App Router; `lib/queries.ts` (SQL), `app/actions.ts` (server actions),
  `lib/categories.ts` (must match the CHECK constraint). Every page and server action requires an ALLOWED_EMAILS Google sign-in.
