# Dashboard

Triage and history for velocity-bd-team, read straight from the ledger with the same
DATABASE_URL the pipeline uses. There is no API layer. Pages are server-rendered; the only
client-side code is the error page's "Try again" button. What each page shows and how the
write actions work is in [docs/DASHBOARD.md](../docs/DASHBOARD.md).

## Run locally

Needs Node 20.9 or newer (built on Node 24). From the repo root, in PowerShell:

```powershell
cd dashboard
npm install
Copy-Item .env.example .env.local    # then set DATABASE_URL and DASHBOARD_USERS
npm run dev                          # http://localhost:3000
```

| Command | What it does |
|---|---|
| `npm run dev` | Development server with live reload. |
| `npm run build` | Production build, including the TypeScript check. |
| `npm start` | Serves the production build. |
| `npm test` | Unit tests for the helpers in `lib/`, on Node's built-in test runner. |

Next.js sends anonymous usage telemetry by default. `npx next telemetry disable` turns it off
for this machine.

## Settings

All read from `dashboard/.env.local` locally, or from the host's environment variables when
deployed. `.env.local` is git-ignored; never commit it or print its values.

| Variable | Required | Meaning |
|---|---|---|
| DATABASE_URL | yes | The ledger. Locally, the Supabase session pooler URL from the repo's `.env`. |
| DASHBOARD_USERS | to record decisions | Comma-separated names allowed to decide. `Name=U0123ABCD` also shows that person's Slack decisions under the name. With one name, that person is the default. |
| DASHBOARD_USER_HEADER | no | Take the viewer from this request header (set by an access proxy) instead of the "Deciding as" picker. |
| DASHBOARD_TIMEZONE | no | Zone for displayed times. Default `America/Denver`. The ledger stores UTC. |
| LEDGER_LOG_DIR | no | Where the pipeline writes run logs, for the log links on /runs. Default `../data/logs`. |

## Deploy from this subdirectory

The app is self-contained in `dashboard/`, with its own `package.json` and lockfile.

- **Vercel**: import the repository, set **Root Directory** to `dashboard`, keep the Next.js
  framework preset, and add the variables above under Settings, Environment Variables.
- **Other hosts**: with `dashboard/` as the working directory, run `npm ci`, `npm run build`,
  then `npm start` (port 3000, or set `PORT`).

Three things differ from running it on the pipeline machine:

1. On a serverless host, use Supabase's **transaction pooler** URL (port 6543). The client
   already turns prepared statements off, which that pooler requires.
2. Run logs stay on the machine that runs the pipeline, so log links answer "not on this host".
3. There is no login. Put the deployment behind an access proxy (Vercel deployment
   protection, Cloudflare Access or similar) and set DASHBOARD_USER_HEADER to the header it
   adds, so decisions are attributed to a verified person.

## Layout

| Path | Contents |
|---|---|
| `app/` | The four pages, `actions.ts` (the one write), `runs/[id]/log/route.ts` (log files), `error.tsx`. |
| `components/` | `Shell.tsx` (navigation and the "Deciding as" control), `bits.tsx` (badges, notices, links). |
| `lib/db.ts` | The Postgres client, created on first use. |
| `lib/queries.ts` | Every SQL statement the dashboard runs. |
| `lib/viewer.ts`, `lib/settings.ts` | Who is deciding; time zone and log directory. |
| `lib/format.ts`, `people.ts`, `text.ts`, `values.ts` | Pure helpers, each with a `.test.ts` beside it. |

## Note for agents working here

This is Next.js 16.4 (App Router, Turbopack). Several APIs differ from older releases:
`searchParams` and route `params` are Promises, `cookies()` and `headers()` are async, and
error boundaries receive `retry()`. The documentation for the installed version is in
`node_modules/next/dist/docs/`; read the relevant page before changing framework code. Next's
own generated AGENTS.md is switched off (`agentRules: false` in `next.config.ts`) because the
repository's AGENTS.md governs agents here.
