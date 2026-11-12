# Email Tracker

A personal tool that reads three Gmail accounts on a schedule, classifies new mail,
and shows only the important emails in a private web app (phone and laptop).
The main goal is to never miss a job opportunity.

**Status:** Phase 1 (ingest) is built. Phases 2-5 are planned below.

## Architecture

```
GitHub Actions cron (every 3 hours)
        |
        v
  ingest/ (Python) --- Gmail API, read-only scope ---> 3 Gmail accounts
        |
        |  rules first, then Claude Haiku for the rest   (Phase 2)
        v
  Postgres (Neon free tier)  <--- web/ (Next.js on Vercel, PWA, Google sign-in)   (Phase 3)
```

- **Gmail access:** Gmail API with OAuth, scope `gmail.readonly` only. One consent per
  account; refresh tokens are stored as secrets. The Google Cloud OAuth app must be
  "In production", otherwise refresh tokens expire after 7 days.
- **Schedule:** every 3 hours, a Python script run by GitHub Actions cron.
- **Classifier:** cheap rules first (known senders, newsletters), then Claude Haiku
  (`claude-haiku-5-5`) with structured output. Only sender, subject and the first part
  of the body are sent. A one-line summary is stored, not the full body.
- **Database:** hosted Postgres free tier. Per email: account, sender, subject, date,
  category, priority (high/medium/low), one-line summary, reason, Gmail link, reviewed flag.
- **Web app:** Next.js on Vercel, mobile-first and installable (PWA), Google sign-in
  restricted to the owner's own addresses.

## Categories

Job-related categories always rank first.

| # | Category | Slug in the database | Notes |
|---|----------|----------------------|-------|
| 1 | Direct job opportunity | `direct_opportunity` | Recruiter or hiring manager writing personally |
| 2 | Application / interview update | `application_update` | |
| 3 | Company job postings | `company_postings` | Openings sent by companies or their career sites |
| 4 | Job alerts | `job_alerts` | LinkedIn / Naukri / Indeed digests, collapsed |
| 5 | Visa / government | `visa_government` | |
| 6 | Finance and bills | `finance_bills` | |
| 7 | Security and account | `security_account` | |
| 8 | Personal / needs reply | `personal` | |
| 9 | Everything else | `other` | Hidden by default |

## Dashboard (Phase 3)

"New since your last visit", grouped by category. Each card shows the account badge,
sender, subject, summary and an "Open in Gmail" link. You can mark an email reviewed,
correct a wrong category, filter by account, category and date, and search.

## Phases

1. **Ingest** - one account into Postgres. *(built)*
2. **Classify** - rules, then Claude Haiku.
3. **Dashboard** - the Next.js web app.
4. **Deploy** - all 3 accounts, the 3-hour schedule, Vercel.
5. **Alerts** - notify on direct opportunities, weekly summary.

## Later roadmap (not built, but the data model allows for it)

- Upload resumes in the web app and apply to jobs from there.
- After that, automated job applying.
- For both, job emails will be extracted into structured job records
  (company, role, location, apply link) in a `jobs` table that references `emails`.

## Repository layout

```
ingest/          Python ingest job (authorize, sync, migrate, parser, db)
db/migrations/   Postgres schema, applied in filename order
tests/           pytest tests with invented Gmail fixtures
web/             reserved for the Next.js app (Phase 3)
```

## What is stored, and what is not

- Stored: sender, subject, date, Gmail labels, Gmail's short snippet, and the first
  2,000 characters of the body (`body_excerpt`).
- `body_excerpt` exists only so the classifier can read it. Phase 2 deletes it as soon
  as the one-line summary is written.
- Attachments and full bodies are never stored. Spam, trash, drafts, chats and mail you
  sent are not stored.
- The app can only read mail. It cannot send, delete or change anything in Gmail.

---

## Setup guide (Phase 1)

These are the steps only you can do. All commands are for PowerShell, run from the
repository folder. **Secrets go into the `.env` file only - never into chat, never into git.**

### A. Install the Python side

1. Create the virtual environment and install the packages:
   ```powershell
   py -3.12 -m venv .venv
   .venv\Scripts\python -m pip install -r requirements-dev.txt
   ```
2. Create your private settings file:
   ```powershell
   Copy-Item .env.example .env
   ```

### B. Create the Postgres database (Neon)

1. Go to <https://neon.tech> and sign up (free plan).
2. Create a project. Name: `email-tracker`. Region: the one closest to you
   (for India, AWS Singapore). Keep the default database name.
3. On the project dashboard click **Connect**, and copy the connection string
   (it starts with `postgresql://` and ends with `sslmode=require`).
4. Open `.env` in an editor and paste it as the value of `DATABASE_URL`.
5. Create the tables:
   ```powershell
   .venv\Scripts\python -m ingest.migrate
   ```
   Expected output: `Applied migrations: 001_init.sql`

### C. Create the Google Cloud project and OAuth client

1. Go to <https://console.cloud.google.com>, signed in with any one of your Google accounts.
   Open the project picker at the top and choose **New project**. Name: `email-tracker`. Create it
   and make sure it is selected.
2. Enable the Gmail API: open **APIs & Services > Library**, search for **Gmail API**,
   open it and click **Enable**.
3. Configure the consent screen: open **APIs & Services > OAuth consent screen**
   (now called **Google Auth Platform**) and click **Get started**.
   - App name: `Email Tracker`. User support email: your address.
   - Audience: **External**.
   - Contact email: your address. Accept the policy and create.
4. Optional (the script requests the scope itself at sign-in): declare the read-only scope under **Data access**, click **Add or remove scopes**, tick
   `.../auth/gmail.readonly`, then **Update** and **Save**.
5. Add yourself as a test user: under **Audience > Test users**, click **Add users** and
   add every Gmail address you want to connect.

   > **Why not "In production" yet:** Google only enables **Publish app** once the Branding
   > page has a homepage URL and a privacy-policy URL. Those will exist after the web app
   > is deployed (Phase 4). Until then the app stays in **Testing**, which means each
   > account's sign-in expires after 7 days and `ingest.authorize` must be run again.
   > Phase 4 to-do: add the Vercel URL and a `/privacy` page on the Branding page, click
   > **Publish app**, then re-run `ingest.authorize` once per account.
6. Create the OAuth client: under **Clients** (or **APIs & Services > Credentials >
   Create credentials > OAuth client ID**), choose application type **Desktop app**,
   name it `email-tracker-local`, and create it.
7. Copy the **Client ID** and **Client secret** from the dialog into `.env` as
   `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`. You do not need to download the JSON file.

### D. Connect one Gmail account and sync it

1. Run the one-time consent:
   ```powershell
   .venv\Scripts\python -m ingest.authorize
   ```
   A browser opens. Choose the Gmail account to connect.
2. Google shows **"Google hasn't verified this app"**. That is expected for a personal
   app: click **Advanced**, then **Go to Email Tracker (unsafe)**, then **Continue**.
   The only permission requested is "View your email messages and settings".
3. The terminal prints `Connected <your address>`. The token is saved in the `tokens`
   folder, which git ignores.
4. Run the sync:
   ```powershell
   .venv\Scripts\python -m ingest.sync
   ```
   Expected output, for example: `you@gmail.com: 212 new, 0 already stored, 9 skipped (sent/drafts), 221 listed`
   The first run pulls the last 14 days (`INITIAL_SYNC_DAYS` in `.env`) and can take a few minutes.
5. Run the same command again. It should report `0 new` - that proves reruns are safe.
6. Optional check: in Neon, open **Tables > emails** and you should see your recent mail.

To add the other two accounts later, repeat step D1 once per account. `ingest.sync`
picks up every account that has a token.

### Troubleshooting

| Message | Fix |
|---------|-----|
| `DATABASE_URL is not set` | Step B4: the value is missing in `.env`. |
| `Error 403: access_denied` in the browser | That Gmail address is not a test user - do step C5. |
| `invalid_grant` exactly a week after authorizing | The app is still in "Testing" (see the note in step C5) - run `ingest.authorize` again. |
| `invalid_grant` during sync | The token was revoked or expired - run `ingest.authorize` again for that account. |
| `Gmail API has not been used in project ...` | Step C2: enable the Gmail API, wait a minute, retry. |

## Tests

```powershell
.venv\Scripts\python -m pytest
```

The parser and sync tests need no Gmail access and no database. The database tests in
`tests/test_db.py` are skipped unless `TEST_DATABASE_URL` points at a throwaway
Postgres (its tables are dropped); see the top of that file for a Docker one-liner.
