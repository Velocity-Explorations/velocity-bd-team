# AGENTS.md

Instructions for every agent that builds or maintains this repo. Read this file first, then
docs/STATUS.md, then the phase prompt you were given.

## What this repo is

velocity-bd-team scans government and prime-contractor portals for opportunities that fit
Velocity Explorations, reviews them, keeps a Proposal Library of past submissions, drafts proposal
material, and reports through Slack and a dashboard. Components are independent programs
that share one ledger database: hosted Postgres in production, SQLite in tests.

## Repo layout

| Path | Purpose |
|---|---|
| run.py | Pipeline entry point. Takes a lock file so only one pipeline runs at a time. `run.py --portal <slug> --dry-run` tests one portal. Also runs the portal assistant's jobs (`--remind`, `--post-summary`, `--apply-requests`), because it is the one place that wires components together. |
| config.py | Settings loader. `require("KEY")` raises a ConfigError naming the key; `python -m config` lists which keys are set, never values. |
| ledger/ | The shared database: connection helpers, `migrate.py`, and `migrations/` (numbered `NNN_description.sql`, additive only). |
| portals/<slug>/ | One adapter per portal (first: `portals/vulcan_sof/`). Logs in, lists calls, extracts details, writes `calls` rows. Exposes a `PORTAL` dict that `portals/registry.py` discovers; run.py never names a portal. Keeps only what is specific to that portal, including its `keywords.yaml`. |
| portals/shared/ | Helpers every adapter reuses: `browser` (headless Chromium), `session` (saved cookies in `data/<slug>/cookies.json`), `otp` (emailed sign-in codes, described per portal as an `OtpSource`), `keyword_filter`, `funding_list` (the Get Funded list AFWERX and SpaceWERX share). Not a portal. |
| review/ | Per-call review: regex blocklist, then LLM verdict. Writes verdicts to the ledger. |
| assistant/ | The portal assistant's toolbox: read tools, and propose tools that record change requests for a person to approve. It reads the ledger and the portals' files only. See docs/ASSISTANT.md. |
| library/ | Proposal Library of past submissions: Drive sync, text extraction, chunking, embeddings. |
| drafting/ | Proposal briefs and response drafts built from reviewed calls and the Proposal Library, and the Writer's worker (`python -m drafting.worker`), which runs the proposal workspace's steps (docs/RUNBOOK.md, The worker). |
| dashboard/ | Next.js triage dashboard reading the ledger directly (docs/DASHBOARD.md). Its own package.json; run npm commands inside dashboard/. |
| slack/ | `alerts.py` (failure alerts), `sink.py` (cards, run summary, thread notes, and editing cards to show decisions made on the dashboard), `workspace.py` (the proposal workspace's notices: step ready, behind target, the morning digest; off until WORKSPACE_SLACK=on). |
| scripts/ | PowerShell helpers, including the Task Scheduler registration script. |
| docs/ | OWNERS.md, STATUS.md, LEDGER_SCHEMA.md, RUNBOOK.md, DASHBOARD.md, plans/, design/ (the dashboard redesign: spec, Claude Design's handoff in design/handoff/, and the build plan). |
| tests/ | pytest suite. Every phase adds tests before code. |
| data/ | Runtime files, one subdirectory per component (`data/<component>/`). Never committed. |
| reference/yukon/ | Read-only prior art from the retired Yukon scanner. Never imported. |

The Phase 0 prompt is the authority on layout and schema. Where this table and Phase 0
disagree, Phase 0 wins and this file gets updated in the same PR.

## Hard rules

1. Components communicate only through the ledger database. No HTTP between components,
   no shared files, no imports across component directories. If component B needs
   something component A produced, A writes it to the ledger and B reads it there.
   run.py is the orchestrator, not a component: it is the one file that calls several
   components in turn (portals, review, slack, the assistant's tools).
2. Never use Playwright's `networkidle` on Vulcan SOF. Its Angular app keeps a connection
   open and `networkidle` never fires (see
   reference/yukon/2026-04-18_vulcan-sof-hanging.md). Use `domcontentloaded` plus fixed
   waits, and give every wait, click, and navigation an explicit timeout.
3. `data/` and `.env` are never committed. Both are in .gitignore; do not remove them.
4. Never print, log, echo, or write the value of any environment variable. Log the key
   name only ("BD_SLACK_BOT_TOKEN present: yes"). Never paste a credential into a file,
   commit, issue, PR, log, test fixture, or chat reply, even a partial one.
5. `reference/yukon/` is proven prior art. Read the relevant file (see its INDEX.md)
   before implementing a phase. Copy the ideas that worked; do not import the code.
6. Each phase prompt you receive is self-contained. It carries everything you need for
   that phase. Do not assume context from prompts you were not given, and do not build
   ahead of the phase you are on.
7. Use pathlib for every path. Never hard-code `/` or `\`.
8. Tests first. Write the failing test, then the code.
9. The repo is public (since 2026-10-19). Commits, pull requests and issues, approved fault
   reports included, are world-readable: keep login-gated portal content, CUI and
   export-controlled material out of them, as well as credentials (rule 4).

## Running things

Create the venv once and activate it in every new shell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Apply migrations (idempotent, safe to rerun):

```powershell
python -m ledger.migrate
```

Run the tests:

```powershell
pytest
```

Test one portal without writing to the ledger:

```powershell
python run.py --portal vulcan_sof --dry-run
```

## Working alongside other agents
Several agents work in this repo: a Coordinator, one agent per portal, and specialists
for review, the Proposal Library, drafting, and dashboard. Rules:
1. Ownership. Each top-level directory has one owning agent, listed in docs/OWNERS.md.
   Change a directory you don't own only through a pull request to its owner.
2. Branches. Never commit to main. Work on `<agent>/<short-task>` (e.g. vulcan-sof/fix-deadline-regex),
   open a PR, and the Coordinator merges. Keep PRs to one concern.
   One exception, for approved settings only: when a person approves a `keyword_change`
   request on the dashboard, `run.py --apply-requests` on the scan machine commits that
   portal's keywords.yaml straight to main. One file per commit, subject
   `chore(<slug>): <change> (request #N, approved by <name>)`. It commits only when the
   checkout is on main and the file has no other edits; otherwise the request waits. No
   agent commits to main by hand under this exception.
3. Schema. Only the Coordinator changes the ledger schema, via numbered files in
   ledger/migrations/ (NNN_description.sql), additive only: add tables or columns, never
   rename or drop without a deprecation note and a release gap. Every schema PR updates
   docs/LEDGER_SCHEMA.md in the same commit. If you need a column, open an issue
   describing the query you want to run; don't add it yourself.
4. Shared record shape. Portal agents write `calls` rows using only the shared columns.
   Portal-specific fields go in `calls.extra` (JSON) with a documented key prefix
   (e.g. "vulcan_"), never in new columns.
5. Runs. Every component records what it did in the `runs` table under its own
   `component` value. The Coordinator reads `runs`; nobody else needs to be told.
6. Data. Each component keeps its files under data/<component>/. Don't read or write
   another component's files; if you need its output, it belongs in the ledger.
7. One pipeline at a time. run.py takes a lock file; test a single portal with
   `run.py --portal <slug> --dry-run`, never by running the full pipeline concurrently.
8. Status. The Coordinator keeps docs/STATUS.md (what's live, what's in progress, known
   breakages). Read it before starting work; update it in your PR if your change affects it.
9. Asking. Questions for another agent go in a GitHub issue labeled with that agent's
   name, not in a code comment and not in Slack.

## Environment specifics (David's PC, Windows)
- Shell: PowerShell. Python 3.11+ in a venv at .venv. Use pathlib everywhere; never hard-code / or \.
- Mail and Drive access: the `gog` CLI (install the Windows release, run `gog auth` as david@velocityexplorations.com).
  OTP mailbox: gog gmail search / gog gmail read --account david@velocityexplorations.com
  Drive: gog drive (list / download / export) for the Proposal Library folder
  If gog is unavailable on this machine, implement the same calls with the Gmail and Drive APIs behind the same function signatures.
  Current state (2026-10-16): gog is not installed. OTP mail is read over Gmail IMAP with a Google app password
  (VELOCITY_GMAIL_APP_USERNAME, VELOCITY_GMAIL_APP_PASSWORD in .env); portals/vulcan_sof/otp.py switches to gog automatically once it is on PATH.
- LLM for review and briefs: Anthropic API via ANTHROPIC_API_KEY
  (claude-haiku-5-5 for per-call review, claude-sonnet-5-5 for proposal briefs)
- The Writer (drafting/) drafts with claude-sonnet-5-5 on ANTHROPIC_API_KEY. WRITER_MODEL=grok-4.7 would switch it
  to Grok through xAI's Responses API on BD_XAI_API_KEY; it is unset since David chose Claude on 2026-10-29
- Embeddings: Ollama for Windows, nomic-embed-text at http://localhost:11434 (768 dims)
- Alerts and delivery: Slack: BD_SLACK_BOT_TOKEN + SLACK_CHANNEL_ID in .env
- Scheduler: Windows Task Scheduler, created by a PowerShell script in scripts/ (Register-ScheduledTask); never overlapping runs.
  Each task starts python through `conhost.exe --headless`, so no window opens; Last Run Result always reads 0 (docs/RUNBOOK.md).
- Playwright's Chromium shows up as chrome.exe in Task Manager.
