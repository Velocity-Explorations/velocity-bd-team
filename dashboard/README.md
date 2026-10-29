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
npm run dev                          # http://localhost:8000
```

| Command | What it does |
|---|---|
| `npm run dev` | Development server with live reload, on port 8000 (3000 is taken by another app on this machine). |
| `npm run build` | Production build, including the TypeScript check. |
| `npm start` | Serves the production build, also on port 8000. (Next warns that the build is standalone; the container runs its `server.js` instead.) |
| `npm test` | Unit tests for the helpers in `lib/`, on Node's built-in test runner. |

Next.js sends anonymous usage telemetry by default. `npx next telemetry disable` turns it off
for this machine.

## Settings

All read from `dashboard/.env.local` locally, or from the host's environment variables when
deployed. `.env.local` is git-ignored; never commit it or print its values.

| Variable | Required | Meaning |
|---|---|---|
| DATABASE_URL | yes | The ledger, as in the repo's `.env`. Hosted, Supabase's pooler URL (see Deploy). |
| DASHBOARD_USERS | to record decisions | Comma-separated names allowed to decide. `Name <email>=U0123ABCD`: the email lets a sign-in proxy name the person, and the Slack id shows their Slack decisions under the name. With one name, that person is the default. |
| DASHBOARD_IAP_AUDIENCE | behind Google's IAP | `/projects/<project number>/global/backendServices/<id>`. Every request except `/healthz` must carry IAP's signed header, and the viewer is the email in it. |
| DASHBOARD_USER_HEADER | no | Behind another access proxy: the header it sets with the person's name or email, used instead of the "Deciding as" picker. |
| DASHBOARD_QUEUE | no | `each` (default): everyone decides every call. `shared`: the first decision takes a call off every queue. |
| DASHBOARD_TIMEZONE | no | Zone for displayed times. Default `America/Denver`. The ledger stores UTC. |
| LEDGER_LOG_DIR | no | Where the pipeline writes run logs, for the log links on /runs. Default `../data/logs`. |

## Deploy

The app is self-contained in `dashboard/`, with its own `package.json` and lockfile. Hosted, the
run log links answer "not on this host": the logs stay on the machine that runs the pipeline.

### As a container (GKE, or any container host)

From the repo root:

```powershell
docker build -t velocity-bd-dashboard dashboard
docker run --rm -p 8080:8080 --env-file dashboard/.env.local velocity-bd-dashboard
```

The image holds no settings: `.dockerignore` keeps `.env` files out, and every variable above
comes from the environment when it runs. It listens on port 8080 as an unprivileged user, and
`GET /healthz` answers 200 without the database or the sign-in.

On GKE behind Google's Identity-Aware Proxy (IAP):

1. Point the load balancer's health check at `/healthz`. Health checks do not pass through IAP.
2. Turn IAP on for the dashboard's backend service, and give access to the people who decide.
3. Set DASHBOARD_IAP_AUDIENCE to `/projects/<project number>/global/backendServices/<id>`
   (`gcloud compute backend-services describe <name> --global --format="value(id)"` prints the
   id). Without it the dashboard trusts no sign-in and shows the "Deciding as" picker, where
   anyone can pick any name.
4. Secrets: DATABASE_URL, DASHBOARD_USERS (with each person's email), DASHBOARD_IAP_AUDIENCE,
   DASHBOARD_TIMEZONE and DASHBOARD_QUEUE.
5. DATABASE_URL must be Supabase's **session pooler** URL (Connect, Session pooler, port 5432).
   The direct `db.<ref>.supabase.co` host has only an IPv6 address, which GKE clusters usually
   cannot reach. The client turns prepared statements off, so the transaction pooler (port 6543)
   works too.
6. Once it is live, set DASHBOARD_URL in the scan PC's `.env` to its address, so Slack cards
   and summaries link to it.

### On the scan PC, through a Cloudflare Tunnel (until GKE)

`compose.yml` runs the image above with a Cloudflare Tunnel beside it, so the team reaches the
dashboard at a hostname on Cloudflare while it still runs on the scan PC. The tunnel dials out:
no port opens to the internet, and the dashboard's Google sign-in decides who gets in. The PC must
stay on and awake, as it must for the worker, and Docker Desktop must start when you sign in
(Settings, General).

1. Cloudflare Zero Trust: Networks, Tunnels, Create a tunnel, Cloudflared, named `velocity-bd`.
   Copy the token from its install command into `dashboard/.env.tunnel` as `TUNNEL_TOKEN=<token>`.
   Under Published application routes, add the hostname with service type HTTP and URL
   `dashboard:8080`.
2. `dashboard/.env.hosted`: the settings in `.env.local`, with DATABASE_URL set to Supabase's
   session pooler URL (Docker cannot reach the direct host either; step 5 above) and AUTH_URL set
   to `https://<the hostname>`. Both files are git-ignored and kept out of the image.
3. Google Cloud, the OAuth client: add `https://<the hostname>` to Authorized JavaScript origins
   and `https://<the hostname>/api/auth/callback/google` to Authorized redirect URIs.
4. From the repo root, `docker compose -f dashboard/compose.yml up -d --build`. Run it again
   after each merge that changes the dashboard; `docker compose -f dashboard/compose.yml down`
   stops both.
5. Checks: `http://127.0.0.1:8090/healthz` answers `ok` on the PC and
   `https://<the hostname>/healthz` from anywhere, and
   `docker compose -f dashboard/compose.yml logs tunnel` shows "Registered tunnel connection".

### Vercel

Import the repository, set **Root Directory** to `dashboard`, keep the Next.js framework preset,
and add the variables above under Settings, Environment Variables. Use the transaction pooler
URL. Put it behind an access proxy (Vercel deployment protection, Cloudflare Access or similar)
and set DASHBOARD_USER_HEADER to the header it adds, so decisions are attributed to a verified
person.

## Layout

| Path | Contents |
|---|---|
| `app/` | The pages, `actions.ts` (the writes), `runs/[id]/log/route.ts` (log files), `healthz/route.ts` (the health check), `error.tsx`. |
| `components/` | `Shell.tsx` (navigation and the "Deciding as" control), `bits.tsx` (badges, notices, links). |
| `proxy.ts`, `lib/iap.ts` | Google IAP sign-in: with DASHBOARD_IAP_AUDIENCE set, every request needs IAP's verified signed header. |
| `Dockerfile`, `.dockerignore` | The container image. |
| `compose.yml` | The image and its Cloudflare Tunnel on the scan PC, until GKE. |
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
