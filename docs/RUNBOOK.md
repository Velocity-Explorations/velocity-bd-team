# Runbook

How to run the pipeline, what the flags do, and what to look at when something is off.

## Run it by hand

Open PowerShell in the repo root, activate the venv, run:

```powershell
.\.venv\Scripts\Activate.ps1
python run.py
```

A full run of Vulcan SOF takes about three minutes: cookie login, 60 detail pages, filter,
LLM review of any new kept rows, then the digest on stdout.

| Flag | Effect |
|---|---|
| `--portal vulcan_sof` | One portal only. Default: every package under portals/ with a PORTAL dict. |
| `--dry-run` | Everything runs, including the browser and the LLM, but every ledger write goes through one transaction that is rolled back at the end. The digest still prints. Use it to test without touching history. |
| `--skip-fetch` | No browser. Filters rows still `pending` and reviews kept rows without a verdict. Cheap way to re-run the back half. |
| `--no-review` | No LLM. Kept, unreviewed rows get verdict `maybe` with reasoning "LLM review disabled". |
| `--limit N` | Scrape at most N calls and review at most N rows. |
| `--fetch-timeout S` | Override every portal's fetch budget (default 300 s from its PORTAL dict). For testing the timeout path. |
| `--feedback-only` | Only sync Slack: thread replies into notes, decisions onto the cards. This is what the daily task runs. |
| `--debug` | DEBUG logging, which includes the first rendered review prompt. |
| `--deliver-run N` | Re-post run N's new calls that never reached Slack (for example after `not_in_channel`), then exit. |

Exit codes: 0 all portals completed, 1 at least one portal did not complete, 2 unknown
portal slug, 3 another pipeline holds the lock.

Only one pipeline runs at a time. `data/pipeline.lock` holds the owning pid; a lock whose
pid is dead or that is older than two hours is treated as stale and replaced.

## Slack delivery and feedback

Every full run posts one card per new call (verdict yes or maybe) to SLACK_CHANNEL_ID, then a
one-line summary. Decisions are made on the dashboard (docs/DASHBOARD.md), not with
reactions, which are not read.

Any reply in a card's thread is stored on the call's human_notes (a leading `note:` is
dropped). The feedback pass also edits each card whose decision differs from the ledger, so
the channel shows what was decided, by whom and when. It runs at the start of every pipeline
run and in the daily "velocity-bd-team feedback" task (`run.py --feedback-only`). Decisions
feed the next review as a RECENT HUMAN DECISIONS block in the prompt. A dry run prints the
cards instead of posting and makes no Slack calls. Set DASHBOARD_URL in `.env` once the
dashboard is hosted and cards and summaries link to it.

## Logs

- `data/logs/run_YYYY-MM-DD_HHMM.log`, one per run, same lines as stdout. The path is also
  stored in `runs.log_path`.
- Stage lines look like `FETCH: 60 rows (171.2s) status=completed`, `FILTER: 0 rows (0.4s)`,
  `REVIEW: 3 rows (12.9s)`, `NEW: 3 rows`.
- Timeouts log `FETCH TIMEOUT: Vulcan SOF exceeded 300s, skipping`.

## What runs.status means

| status | meaning | what to do |
|---|---|---|
| running | the run has started and not finished | if it is older than the fetch timeout plus a few minutes, the process died; check the log and the lock file |
| completed | all stages ran; stage_counts is filled | nothing |
| skipped_timeout | fetch exceeded its budget; the browser was force-closed; filter and review still ran on whatever was saved | look at the log for where it stalled; a one-off is normal, two in a row means the site changed |
| error | fetch or a later stage raised; `error` holds the message | read the log; fix; re-run (a re-run is safe, upserts are idempotent) |

`dry_run = 1` rows are from `--dry-run` runs. They exist only when the dry-run session
could not be rolled back, which should never happen; normally a dry run leaves no row.

## Failure alerts

When fetch times out, fetch errors, login returns False, or a later stage raises, the
pipeline posts one line to Slack (BD_SLACK_BOT_TOKEN and SLACK_CHANNEL_ID in `.env`) with the
portal, the stage, the error and the log path. Without those two settings the alert is
written to the log at WARNING instead, and the run continues.

## Re-triggering an OTP login

Vulcan SOF asks for an emailed six-digit code on a fresh login and remembers the browser
for a while after. Saved cookies live in `data/vulcan_sof/cookies.json`; every portal keeps
its own in `data/<slug>/cookies.json`.

- To force a fresh login: delete the cookie file, or run
  `python -m portals.vulcan_sof.test_login --fresh`. The code is read automatically from
  the OTP mailbox over IMAP (VELOCITY_GMAIL_APP_USERNAME and VELOCITY_GMAIL_APP_PASSWORD).
- If the login keeps failing at the passcode step, check that the app password still works:
  `python -c "from config import require; from portals.shared import otp; from portals.vulcan_sof.auth import VULCAN_OTP; print(len(otp.fetch_via_imap(VULCAN_OTP, require(VULCAN_OTP.mailbox_key))))"`
  should print a number, not an authentication error.
- Vulcan may skip the code entirely when it has seen this machine recently. That is normal.

## Scheduled runs

`scripts\install-schedule.ps1` registers a Windows Task Scheduler task named
"velocity-bd-team pipeline" that runs `run.py` from the venv weekly (default Monday 06:00).
The task's MultipleInstances policy is IgnoreNew, and the lock file is a second guard.

```powershell
.\scripts\install-schedule.ps1                 # install or replace
Start-ScheduledTask -TaskName "velocity-bd-team pipeline"   # run now
Get-ScheduledTaskInfo -TaskName "velocity-bd-team pipeline" # last run time and result
.\scripts\uninstall-schedule.ps1               # remove
```

The task runs as the current user with an interactive logon, so it fires only while that
user is logged on (locked screen is fine). `.env` and the cookie file are read from this
repo as usual. To run while logged off, re-register with a password-backed principal.

## Portal assistant

Try any tool from the command line, for example `python -m assistant explain <call id>` or
`python -m assistant deadlines`; `python -m assistant tools` lists them all. Three scheduled
jobs run from run.py: deadline reminders daily at 08:00 (`--remind`), the weekly summary on
Mondays at 09:00 (`--post-summary`), and approved change requests every 15 minutes
(`--apply-requests`). Every scan also alerts when it reads too many pages badly. Details in
docs/ASSISTANT.md.

Change requests:

- `python -m assistant requests` lists them; the dashboard's Requests page is where they
  are approved or rejected.
- An approved keyword change waits while this checkout is on a branch other than main, or
  while the portal's keywords.yaml has uncommitted edits. Its result on the Requests page
  says which. Switch back to main (or commit the edit) and the next pass applies it.
- The commit it makes is local. Push it with `git push origin main`.
- To carry out approved requests now instead of waiting for the next pass:
  `python run.py --apply-requests`.

## Dashboard

```powershell
cd dashboard
npm run dev      # http://localhost:8000
```

It reads `dashboard/.env.local` (DATABASE_URL, DASHBOARD_USERS). Pages, the decision buttons and
how they coexist with Slack are in docs/DASHBOARD.md.

## Running the stages separately

The stage commands from earlier phases still work and share the same ledger:
`python -m portals.vulcan_sof.run_scrape`, `python -m portals.vulcan_sof.run_filter [--all]`,
`python -m review.run_review [--limit N]`. Do not run them while the pipeline is running.
