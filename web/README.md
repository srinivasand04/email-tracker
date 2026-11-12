# web/

Phase 3 dashboard: Next.js 15 (App Router), mobile-first, installable (web manifest).
Reads `DATABASE_URL` from the repository's `.env`.

```powershell
npm --prefix web install
npm --prefix web run dev     # http://127.0.0.1:3000
```

No sign-in yet, so it only listens on 127.0.0.1. Google sign-in restricted to the owner's
addresses is added with the Vercel deployment in Phase 4; do not deploy before that.
