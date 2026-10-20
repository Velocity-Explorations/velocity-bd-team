# Status

Kept by the Coordinator. Read before starting work; update in your PR if your change affects it.

## Live

- Ledger (Phase 0), migration 001_initial applied to the hosted Supabase Postgres on
  2026-10-16, 002_change_requests on 2026-10-17, 003_judgments on 2026-10-20.
  004_decisions (every decision kept per person) is applied with `python -m ledger.migrate`
  after it merges. Tables: calls, change_requests, decisions, judgments, proposals, runs,
  schema_migrations. Connect through the Session pooler URL (the
  direct URL is IPv6-only and unreachable from David's network).

## In progress

- Phase 7 (pipeline): `python run.py` runs every registered portal (fetch under a hard timeout,
  filter, review, digest) and writes data/logs/run_*.log. Scheduled weekly (Sunday 22:00 since 2026-10-20) via
  scripts/install-schedule.ps1 as of 2026-10-16. Failure alerts go to Slack once SLACK_CHANNEL_ID
  is set; until then they are log warnings.
- Phase 8 (Slack delivery and feedback): cards and a summary per run; thread replies polled into
  notes and cards edited to show decisions (`run.py --feedback-only`, daily task). Live on
  2026-10-16. Since 2026-10-17 reactions are not read: decisions are made on the dashboard.
- Phase 9 (dashboard): Next.js 16.4 app in dashboard/, run locally with `npm run dev`. The only
  place decisions are made: review queue buttons, plus a change control on all calls. Several
  people can decide (DASHBOARD_USERS lists David and Shaun since 2026-10-20); each person's
  decisions are kept and a judges page scores Claude and Grok against them. Runs and
  proposals pages too. Not deployed anywhere yet; hosting is undecided, so for now only David
  can decide.

- Phase 2 (Vulcan SOF login): working as of 2026-10-16. Username, password, then the emailed
  code read over Gmail IMAP (VELOCITY_GMAIL_APP_USERNAME + VELOCITY_GMAIL_APP_PASSWORD; gog CLI
  is used instead when installed). Calls listing reachable, 120 call links seen.
- Phase 3 (session persistence): cookies saved to data/vulcan_sof/cookies.json after each successful
  login and restored first on the next run; verified 2026-10-16.
- Portal assistant, step 1 (2026-10-17): read tools in assistant/ (explain, brief, deadlines,
  scraper health, weekly summary, portal profile, settings preview, tuning report), daily
  deadline reminders, the Monday summary and the scraper watch. No model connected yet.
- Portal assistant, step 2 (2026-10-17): approvals. Propose tools (keyword change, re-review,
  scan now, start a draft, fault report) record requests in change_requests (migration 002);
  the dashboard's Requests page approves or rejects them; `run.py --apply-requests` carries
  them out twice a day, at 12:07 and 17:07. Drafts wait for the Writer; fault reports wait for a GitHub
  remote. The reminder and summary jobs moved from `python -m assistant` to run.py.
- GitHub (2026-10-18): the repo is at Velocity-Explorations/velocity-bd-team, public since
  2026-10-19 (a scan of every commit found no credentials first), with main
  pushed. Approved fault reports now file there as issues.
- GitHub token (2026-10-19): fault reports file with the pipeline's own token
  (`BD_GITHUB_TOKEN`), a classic token with the repo scope that expires 2027-01-17, and with
  the gh login when `.env` has none. A token limited to this repo's issues would need
  fine-grained tokens enabled for Velocity-Explorations. Renewal steps are in
  docs/RUNBOOK.md, "GitHub token".
- Plans (2026-10-18): the Writer Plan, the Draft-Ready Upgrade and the Proposal Library plan were revised
  so the dashboard decides. Drafts are requested with the dashboard's Draft button, an approved
  draft request from the assistant, or the CLI. Offline copies are in docs/plans/.
- Shared portal helpers (2026-10-17): browser, saved sessions, emailed sign-in codes and the
  keyword filter live in portals/shared/ for every adapter; Vulcan SOF keeps only its own
  login, scraping and keywords.yaml.
- Phase 4 (Vulcan SOF scrape): `python -m portals.vulcan_sof.run_scrape` writes every listed call
  (60 on 2026-10-16, 18 open and 42 closed; closed flagged in extra.vulcan_closed) in about 170 s
  with 100% field fill. Descriptions are stored at up to 1,500 characters (widened from 400 on 2026-10-16).
- Phase 5 (keyword filter): `python -m portals.vulcan_sof.run_filter` (add `--all` after editing
  portals/vulcan_sof/keywords.yaml). On 2026-10-16: 60 rows, 58 kept (6 tight, 52 broad), 2 rejected.
  The `ai` substring keeps most rows in broad; the LLM review is the real gate.
- Phase 6 (LLM review): `python -m review.run_review` reviews kept, unreviewed rows of the latest run
  with claude-haiku-5-5. On 2026-10-16: 58 rows, yes 17, maybe 33, no 8, 206 s. Model failure yields
  "maybe" with a "Review error" reason, never "no".
- Second judge (2026-10-20): Grok (grok-4.7) judges every call the Claude review rates, with the
  same prompt, when BD_XAI_API_KEY is set. Both verdicts go to the judgments table (migration 003)
  and show on the dashboard with how often they agree; Claude's verdict still decides what is
  posted. `python run.py --backfill-judgments` fills the history once.

## Known breakages
