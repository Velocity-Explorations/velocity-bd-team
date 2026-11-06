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
| `--deliver-run N` | Post run N's Slack summary, held by `--hold-slack` or lost to a Slack failure (for example after `not_in_channel`), then exit. |
| `--hold-slack` | Judge and save as usual, but post no run summary. The run prints its number, and `--deliver-run N` posts the summary once someone has looked at the calls on the dashboard. |
| `--linear-sync` | Open and move issues in Linear's Pursuits project to match the calls the team pursues, then exit. The "velocity-bd-team linear" task runs it at 08:07 and 13:07 (Linear's Pursuits project, below). |

Exit codes: 0 all portals completed, 1 at least one portal did not complete, 2 unknown
portal slug, 3 another pipeline holds the lock.

Only one pipeline runs at a time. `data/pipeline.lock` holds the owning pid; a lock whose
pid is dead or that is older than two hours is treated as stale and replaced.

## Slack delivery and feedback

Every full run posts a one-line summary to SLACK_CHANNEL_ID: calls scanned and the new ones by
verdict, with a link to the dashboard. Since 4 Nov 2026 no card goes out per call (David; the
first full SAM.gov scan found 119 new calls): calls are decided on the dashboard
(docs/DASHBOARD.md), and reactions are not read.

Cards posted before then keep working. Any reply in a card's thread is stored on the call's
human_notes (a leading `note:` is dropped). The feedback pass also edits each card whose
decision differs from the ledger, so the channel shows what was decided, by whom and when. It
runs at the start of every pipeline run and in the daily "velocity-bd-team feedback" task
(`run.py --feedback-only`). Decisions feed the next review as a RECENT HUMAN DECISIONS block in
the prompt. A dry run prints the summary instead of posting and makes no Slack calls.
DASHBOARD_URL in `.env` sets where summaries link: the hosted dashboard since 4 Nov.

### Workspace notices in Slack

The proposal workspace can post to Slack too (PW18), in two scheduled jobs that never take the
pipeline's lock:
- **Every 5 minutes** (`run.py --workspace-slack`, task "velocity-bd-team workspace slack"): a card
  for any pursued call that has none, so its notices have a thread; then each step newly ready for
  its owner, in the call's thread. Steps the worker approves itself (key gates only) are not posted.
- **At 08:00** (`run.py --workspace-morning`, task "velocity-bd-team workspace morning"): each step
  past its target date (worked back from the internal submit-by date) in its call's thread, then one
  message per owner listing what waits on them: steps ready, failed (Retry) or past the budget.

They post nothing until `WORKSPACE_SLACK=on` is in `.env`: the team asked on 28 Oct for fewer
automatic posts in the channel, so they start off. Each notice goes out once; what was posted is kept
in the pursuit's history (`slack_ready`, `slack_behind`), and the digest's day in
`data/slack/workspace_digest.txt`. To mention people, copy DASHBOARD_USERS (`Name=<Slack id>`, comma
separated) from `dashboard/.env.local` into `.env`; a name without a Slack id is written out. Rerun
`scripts/install-schedule.ps1` once to register the two tasks.

## Linear's Pursuits project

Each call the team marks Pursue on the dashboard gets an issue in the Pursuits project of Velocity's
Operations team on Linear (David, 4 Nov 2026). The "velocity-bd-team linear" task runs
`run.py --linear-sync` at 08:07 and 13:07 (David, 5 Nov), without the pipeline's lock, in a hidden
console like every task here (linear/pursuits.py):

- A newly pursued call gets an issue in Backlog titled "Submit (the call) by (its day)", due on the
  deadline, assigned to whoever marked Pursue (their address in DASHBOARD_USERS, else their dashboard
  sign-in, matched to a Linear user by email), Urgent within 7 days of the deadline, High within 14,
  Medium after that. The description holds Claude's summary and reason, Grok's verdict, the portal's
  details and links to the call on its portal and on the dashboard (DASHBOARD_URL).
- The issue moves to In Progress when drafting starts and to Done when the call is marked Submitted,
  with a comment saying who and when; a recorded result adds a comment; a withdrawn Pursue, a no-go or
  a closed draft moves it to Canceled with the reason. A call pursued again gets a new issue, since a
  canceled one is never reopened.
- `linear_issues` (migration 012) keeps each call's issue and the stage it last showed, so the sync
  acts only when the call moves on, and a person may move an issue by hand meanwhile. A call already
  submitted when the sync first runs, or whose deadline has passed, gets no issue.

To set it up, once:

1. In Linear, open Settings, then Account, Security & access, Personal API keys, and create a key named
   "BD pipeline" with Read and Write on the Operations team. Linear shows it once.
2. Add it to the repo's `.env` as `BD_LINEAR_API_KEY=...`, and nowhere else.
3. Apply the migration: `python -m ledger.migrate`.
4. Rerun `scripts/install-schedule.ps1`, or run one sync by hand: `python run.py --linear-sync`.

Without the key the task prints that it is not set and writes nothing.

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
"velocity-bd-team pipeline" that runs `run.py` from the venv weekly (default Sunday 22:00, so the
results are in before the Monday meeting). The scan PC is a desktop set never to sleep or hibernate
on mains power, and the scan task may wake it if it was put to sleep by hand.
The task's MultipleInstances policy is IgnoreNew, and the lock file is a second guard.

```powershell
.\scripts\install-schedule.ps1                 # install or replace
Start-ScheduledTask -TaskName "velocity-bd-team pipeline"   # run now
Get-ScheduledTaskInfo -TaskName "velocity-bd-team pipeline" # last run time
.\scripts\uninstall-schedule.ps1               # remove
```

The task runs as the current user with an interactive logon, so it fires only while that
user is logged on (locked screen is fine). `.env` and the cookie file are read from this
repo as usual. To run while logged off, re-register with a password-backed principal.

Each task starts python through `conhost.exe --headless`, so no console window opens, for
python or for anything it starts. Task Scheduler's Last Run Result therefore reads 0 even
when a run fails: look for failures in data\logs and the Slack alerts.

## The worker (proposal workspace)

The worker runs the proposal workspace's steps on this PC. When someone chooses Start the draft on the
dashboard, Discovery waits in the ledger until the worker takes it, and so on, one step at a time. It is
one always-on program, `python -m drafting.worker`, that checks the ledger every 20 seconds and runs each
step with Claude (claude-sonnet-5-5, through `ANTHROPIC_API_KEY`). `WRITER_MODEL=grok-4.7` in `.env` would
switch it to Grok through `BD_XAI_API_KEY`; it is unset. It logs the model as it starts; after changing
WRITER_MODEL, restart it (Stopping it, below). Claude thinks before it answers and the thinking counts
against a call's output limit, so each call gets 32,000 tokens of room for it on top of the answer's
budget. A worker log line ending "(hit max_tokens, output cut off)" means an answer still ran out.

**Starting it.** Run the schedule script again in PowerShell from the repo folder. It adds a task named
"velocity-bd-team worker" and replaces the others unchanged:

```powershell
.\scripts\install-schedule.ps1                               # adds "velocity-bd-team worker"
Start-ScheduledTask -TaskName "velocity-bd-team worker"      # start it now rather than at the next logon
```

The task starts the worker when you log on, and checks every 5 minutes that it is running, starting it
again if not. As soon as the worker starts it records a heartbeat in the ledger, and the dashboard's
Start the draft buttons switch on; until then they say "Drafting is not set up yet". The dashboard shows
the worker as offline once its heartbeat is more than 10 minutes old (the PC is off or asleep, or the
worker stopped), and queued steps wait for it.

**What it spends.** Each step's cost is added to the step and its pursuit. Every pursuit has a $200 cap:
a step that would start past it waits as "budget reached", and a step whose spending crosses it stops
there and waits the same way. The prices are in `drafting/costs.py`; update them when Anthropic's or xAI's change.

**Stopping it.** Ending the task leaves the worker's Python running (seen on 29 Oct, when a restart found
the old worker still holding its lock), so end that process too, preferably while the dashboard shows the
worker idle:

```powershell
Stop-ScheduledTask -TaskName "velocity-bd-team worker"
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*drafting.worker*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-ScheduledTask -TaskName "velocity-bd-team worker"      # to restart it; the log's first line names its model
Disable-ScheduledTask -TaskName "velocity-bd-team worker"    # or keep it stopped; Enable-ScheduledTask undoes it
```

A step the worker was working on when it stopped shows as failed ("The worker stopped while it worked on
this step") the next time the worker starts, and Retry runs it again.

**Files and logs.** Until the Drive phase, each pursuit's documents are Markdown files in
`data\drafting\pursuits\pursuit-<id>\`, each with a Word file beside it in the format the call sets
(font, size, margins and spacing, found at Requirements and checklist; Times New Roman 12 with one-inch
margins until then), and each step's key points show on the dashboard. The drafts
are numbered: `draft_v1.md` (First draft), `draft_v2.md` (Compliance check), `draft_v3.md` (the
reviewers' changes the owner accepted, put in at the start of Final checks) and `draft_final.md`
(Final checks). Each new draft gets the AI slop check: the worker first replaces dashes and removes
tracking parameters from links, then runs the scanner from `AI_SLOP_SCAN`, or from the skill's default
place in your profile, and keeps the result in the ledger (`slop_scans`); without the scanner the step
says the check did not run. Check again on the dashboard queues a scan of the newest draft, which the
worker runs when no step is waiting. The result page (See the result in Reviews) shows the newest scan
and the text as scanned; to clear a placeholder, edit the newest draft in the pursuit's folder, then
choose Check again. Final checks also runs the compliance check once more on the final version (`final_compliance.md`).
What it can fix where it stands, such as a keyword, a reference the solicitation names or a glossary entry,
goes into the final version. A corrected version that would drop a placeholder or a heading, lose text or run
over the page budget is not used, and the check says why. Fix the rest by hand. The worker
cannot open portal pages or download attachments yet, so its steps work from what the scanner saved and
list what the owner should fetch. Login-gated text (Vulcan SOF, NSTXL member pages) goes to the Anthropic
API and these local files, by David's decision of 27 Oct, and never into the repo. The log is
`data\drafting\logs\worker.log`, a new file each midnight with the last 30 kept; it records step ids,
states and costs, never a call's text.

**One step by hand.** With the venv active, `python -m drafting.worker --once` runs the oldest queued
step, if there is one, and exits. While the scheduled worker runs it holds `data\drafting\worker.lock`,
and a second worker says so and leaves, so stop the task first.

## Portal assistant

Try any tool from the command line, for example `python -m assistant explain <call id>` or
`python -m assistant deadlines`; `python -m assistant tools` lists them all. Three scheduled
jobs run from run.py: deadline reminders daily at 08:00 (`--remind`), the weekly summary on
Mondays at 09:00 (`--post-summary`), and approved change requests daily at 12:07 and 17:07
(`--apply-requests`). Every scan also alerts when it reads too many pages badly. Details in
docs/ASSISTANT.md.

The weekly summary also stores its week for the dashboard's Monday brief (`/brief`).
`python run.py --write-brief` stores this week's brief without posting to Slack, for example to
fill the page before the first Monday run.

Change requests:

- `python -m assistant requests` lists them; the dashboard's Requests page is where they
  are approved or rejected.
- An approved keyword change waits while this checkout is on a branch other than main, or
  while the portal's keywords.yaml has uncommitted edits. Its result on the Requests page
  says which. Switch back to main (or commit the edit) and the next pass applies it.
- The commit it makes is local. Push it with `git push origin main`.
- To carry out approved requests now instead of waiting for the next pass:
  `python run.py --apply-requests`.

## GitHub token

Approved fault reports become GitHub issues through `gh issue create`. With `BD_GITHUB_TOKEN`
in `.env`, the pipeline files them with its own token, which has its own name and expiry and
can be revoked without signing anyone out of gh. Without it, gh uses whoever is signed in on
the scan machine.

The token is a classic token with the `repo` scope, so like the gh login it reaches every
repo its owner can. A token limited to this repo's issues is a fine-grained token with
Velocity-Explorations as its resource owner, which the org's settings did not offer when the
token was set up (2026-10-19).

To create the token (about five minutes):

1. Go to https://github.com/settings/tokens/new (profile picture, Settings, Developer
   settings, Personal access tokens, Tokens (classic), Generate new token (classic)).
2. Set Note to `velocity-bd-team pipeline` and Expiration to 90 days, and tick the `repo`
   scope only. Creating issues in a private repo needs it.
3. Click Generate token and copy it. It starts with `ghp_`, and GitHub shows it only once.
4. If the token list shows Configure SSO next to the new token, authorize Velocity-Explorations.
5. Open `.env` in VS Code, set `BD_GITHUB_TOKEN=` followed by the token, and save.
6. Check it: `python -m config` should show `BD_GITHUB_TOKEN` as `set` instead of `MISSING`.

To renew it, open the token on the Tokens (classic) page, choose Regenerate token, and
replace the value in `.env`. GitHub emails a reminder before it expires.

If Velocity-Explorations later allows fine-grained tokens, switch to one: resource owner
Velocity-Explorations, only velocity-bd-team, and Issues set to Read and write.

When the token expires or loses access, the fault report's result on the Requests page names
`BD_GITHUB_TOKEN` and says what to fix. Replace the value in `.env`; the next pass files the
report.

## Company facts

Everything the Writer says about Velocity comes from the BD Proposal Library's `01 Company Reference` folder on
Drive: 00 Company Facts (F-numbered facts), 01 Past Performance Register (PP-), 02 Products & Capabilities (PR-),
03 People (PE-), the Brand Guide in 04 Brand, and 05 Conflicts & Open Questions (CF-). Edit the facts there; the
repo keeps none of them. `.env` names each file by its Drive id:

```
COMPANY_FACTS_DOC_ID=        PAST_PERFORMANCE_SHEET_ID=    PRODUCTS_SHEET_ID=
PEOPLE_SHEET_ID=             BRAND_GUIDE_DOC_ID=           FACT_CONFLICTS_SHEET_ID=
```

The worker reads all six through its service account at the start of every step (`drafting/facts.py`). It sends
them first in every call, as the only source for claims about the company, and each prompt says where they are
and when they were read. It saves what it read to `data\drafting\facts\`; when Drive cannot be read, that copy
stands in for up to 24 hours and the prompt says so. With no copy that recent, or with an id missing from
`.env`, the step fails and its card says why.

The facts, about 26,000 tokens, are marked for Claude's prompt cache. The first call writes them to the cache
(about $0.065 on Sonnet 5.5), and each call within five minutes of the last one that used them reads them for
about $0.003. Steps that run back to back share it, so a pursuit's facts cost about $0.30 rather than $1. The
worker log shows both counts on each call: "(25947 from the cache, 0 written to it)".

The files' rules are applied in code before the model sees anything:
- A person marked FORMER EMPLOYEE in 03 People is left out of bios and key personnel. A partner stays, named as
  one.
- An item marked SENSITIVE, and each column marked SENSITIVE (a clearance), is marked [SENSITIVE] and used only
  when the solicitation requires it.
- An item naming a 05 Conflicts question that is not resolved is marked [OPEN: CF-nn]. The draft must not state
  it as settled, and writes [NEEDS FACT: settle CF-nn, ...] where it needs it. An answer "confirmed by David,
  evidence pending" is marked [EVIDENCE PENDING: CF-nn] and may be used.
- The proposing company is Velocity Explorations. Hoverslam Designs LLC's facts appear only when the owner's
  direction (or material the team added) names Hoverslam; then its SAM renewal is flagged for confirmation.
- Title-page fields come from the fact `drafting/company.yaml` names for each, such as `cage: "[F-03: CAGE]"`.
  00 Company Facts leaves contact emails and phones out on purpose, so they stay [NEEDS FACT: ...] and are
  filled in at submission.

Since 2026-11-04 the First draft gives each success measure a starting target: a figure drawn from the
solicitation, the published literature or the system's own measured record, stated as a target the work will
test, never as a result. One [NEEDS INPUT: confirm the proposed targets with the stakeholder] follows for the
owner. No target rests on a figure the Company Reference marks DO NOT USE.

A company fact the files do not hold is written [NEEDS FACT: what is missing]. It counts as an open item, like
NEEDS INPUT, at every gate. After the First draft, the Compliance check and Final checks, one more call lists
the facts the draft rests on. Those steps then save `facts_used_v1.md`, `facts_used_v2.md` and
`facts_used_final.md`, each with:
- every id the draft cites, and where;
- what to review: SENSITIVE items, open or pending questions, and a Hoverslam bid's SAM renewal;
- claims with no fact behind them;
- ids the files do not have.

The step's card counts them, for example "Facts used: 24 cited, 3 to review, 1 with no fact". The check costs
about $0.10 to $0.20 a draft; if it fails, the draft stands and the card says the check did not run.

## Page budget

Drafts are held to the call's page limit. The Outline records the limit and each section's share as page
counts. Every later step turns them into words at 350 a page (`WORDS_PER_PAGE` in `drafting/write.py`). That is
about what Velocity's submitted technical volumes run: 39 measured in the library ran a median 303 words a page,
the technical volumes alone about 380, and a winning 2025 volume 315.

Every count leaves placeholders out (`text_words` in `drafting/steps.py`), since filling one replaces its words.
On 2 Nov a final version ran 5,320 words, 1,110 of them inside 92 placeholders; its own text, 4,210 words, fit
13 pages.

- **First draft:** writes to the budget, section by section.
- **Compliance check:** writes to it too, and sees the draft's length against it.
- **Reviewers:** see the length too, and what the changes earlier reviewers proposed would make it. They must
  pay for any addition with a cut when the draft is over. In the 1 Nov rerun their changes had added about
  1,300 words.
- **Final checks:** when Draft v3's own words run more than a twentieth over, it cuts it to the budget in a pass of
  its own, before the formatting pass, whose prompt may not change wording. A pass can stop short (on 2 Nov one
  asked for 4,550 words stopped at 4,912, placeholders counted), so it aims a twentieth under the budget. A second
  pass follows when the first falls short. The cut keeps every section, fact, figure, name, table row and placeholder.
  A cut that loses a placeholder or a heading, or cuts nothing, is thrown away and the text before it stands;
  the card says which.
- **Page fit:** one of the eight final checks. It passes up to a twentieth over the budget, since 350 words a
  page is an estimate with a wider margin than that, and says how many words are left for the placeholders still
  to fill. Check again measures it once more on the final version as the owner left it, and the card shows that.
- **Submit gate:** checks the page fit again on the final version as the owner left it in the pursuit's folder,
  since filling the placeholders adds words. A version over the budget shows on the gate's card with how much to
  cut.

A call with no page limit gets no budget, and Page fit reads not run.

## Past bids in drafts

The Outline and the First draft also read the past bids nearest the call (`drafting/past_bids.py`):
- **Which:** the first three Register rows in the Writer's ranking whose folder in 02 Submissions holds files. The
  ranking favors the same agency, an exemplar, a win, its strength, and words its title and themes share with
  the call.
- **What:** each one's `01_submitted/` and `03_outcome/`, read live through the service account. Volumes and
  papers come first, then slides; cost files, cover sheets, letters, forms and other paperwork in `01_submitted/`
  are left out. Text comes from PDFs, Word files, slide decks and Google Docs or Slides, at most 12,000
  characters a file and 20,000 a bid.
- **How it's used:** the prompt says to reuse their language, structure and lessons only, and to take every fact
  from VELOCITY FACTS, never a figure, price or name from an old bid.

The step's card says which bids were read, and `past_bids.md` beside the draft holds the text the Writer saw.
When Drive cannot be read, the step goes on and the card says so.

## Second judge (Grok)

Every call the Claude review rates is also judged by Grok (`grok-4.7`) with the same prompt,
and both verdicts are kept in the `judgments` table for the dashboard. Claude's verdict still
decides what is posted. Grok runs only when `.env` has `BD_XAI_API_KEY` (the key named
velocity-bd-team on Velocity's xAI team, limited to grok-4.7, expiring 2027-01-17); remove
the line to turn it off. A Grok failure logs a warning and the run carries on.

To fill the history once, after migration 003: `python run.py --backfill-judgments` copies
Claude's past verdicts and has Grok judge every kept call it has not judged yet. It is safe
to rerun.

## Tags

Every call carries tags from `review/tags.yaml`: one type, plus work, customer and access tags
(PRO-556). Rules set the tags a call's own data makes certain, on every call each run sees;
Claude and Grok pick the rest on a TAGS line of the review answer they already give, so tags cost
no extra model calls. A tagging failure only logs a warning.

Fit score (PRO-487, `review/fit.py`). Each judge names a call's main work on the MAIN WORK line of its answer.
The team rates each tag, keyword and NAICS code on the dashboard's Fit ratings page (Automation, `/fit`); a change queues
a `fit_scores` job and the worker scores every call again within about a minute, so the worker must be running.
`python run.py --fit-scores` does the same by hand (`--dry-run` counts the bands and writes nothing).
`python run.py --load-fit-ratings FOLDER` loaded the first ratings from an export of the page used before `/fit`; it
replaces every row, so it would undo changes made on `/fit`. Each scan scores the calls it saw. A Never rules a call out only on
its main work, its type or its NAICS code; on what the judges name, only when they agree. `python run.py --rejudge-open`
has both judges rate every open, undecided call again and name its main work, for after a profile change;
`--dry-run` counts and prices it, and a rerun skips calls already done. Ratings never go in the repo, which is public.
A call both judges rate no is weak at best. `python run.py --refilter` puts every stored call through the keyword filter
again after its rules change (`--dry-run` counts). A keyword of three characters or fewer matches only as a whole word.

After migration 006, `python run.py --backfill-tags` tags every stored call by its rules and has
Claude and Grok tag the kept, reviewed calls, asking for tags alone. Grok takes about 20 s a call,
so a full pass over about 120 calls runs some 40 minutes. It is safe to rerun: each pass only asks
about calls a judge has not tagged.

## Executive summaries

The review also asks Claude for a SUMMARY line, two plain sentences for an executive, kept in
`calls.ai_summary` (migration 009); the dashboard's Description column shows it, with the portal's
own words on hover. Apply the migration once with `python -m ledger.migrate`. For calls reviewed
before it, `python run.py --backfill-summaries --dry-run` counts every call with no summary,
the keyword filter's rejects and decided calls too, and prices the run; without `--dry-run` it
summarizes them with claude-haiku-5-5, asking for the summary alone. It is safe to rerun: each pass
only asks about calls with no summary. Each scan also summarizes the calls its review did not, the
keyword filter's rejects above all, so every call has one. Migration 009 and the backfills ran on
the live ledger on 28 and 29 Oct: all 187 calls, about $0.04 in all.

To change the list, edit `review/tags.yaml`: each tag with a few words on what it covers, which
the judges read. Names must differ across groups. The next run (or `--backfill-tags`) copies the
list into the ledger's `tag_list`, which the dashboard's Tag filter reads.

## SAM.gov

The SAM.gov portal reads the public Opportunities API with `BD_SAM_API_KEY` from `.env`
(portals/sam_gov/NOTES.md). Each request counts against the key's daily limit, and each new
notice's description is a request of its own. A run spends at most 900 requests, then stops
cleanly; so does a run when SAM.gov answers 429 (the day's limit is reached). The notices it
did not read wait for the next run. Every run reads the soonest deadlines first.

- The run log's last SAM.gov line gives the counts: open notices, dropped, already on Front
  Door, stored (new), waiting, failed, and requests spent.
- If many notices are waiting after the first ingest, run it again the next day:

```powershell
python run.py --portal sam_gov
```

- To try it without storing anything or posting to Slack, cap the new notices it reads:
  `python run.py --portal sam_gov --dry-run --limit 25` (about 30 requests).
- HTTP 401 or 403 means the key has expired (personal keys last 90 days): generate a new one
  in the SAM.gov account profile and replace it in `.env`.
- NAICS codes, offices (IARPA) and title words (TRMC) searched whatever their codes, notice types
  and set-asides are in `portals/sam_gov/search.yaml`; the next run uses any change.

## Proposal Register

The "00 Proposal Register" sheet in the BD Proposal Library Drive folder lists past submissions
(docs/LIBRARY_CONVENTIONS.md). After rows are filled in or changed, or a folder is added to 02 Submissions, ask
Claude to "sync the register". It first appends a starter row for any folder without one (submission_id,
submitted_date and portal from the folder name, no date for a `nodate_` folder, drive_link to the folder) and never changes a row people
have filled in. Then it reads the sheet and the folder names in 02 Submissions through the Google connectors,
writes them to
`data/library/register_rows.json` and `data/library/folders.json`, and runs

```powershell
python -m library.register sync --rows data/library/register_rows.json --folders data/library/folders.json
```

It upserts every valid row into `proposals`, skips a row with a problem (its ledger row keeps its last
good values), and lists the problems, folders with no row and rows with no folder. Exit code 0 when every
row synced, 1 when some were skipped.

## Google Drive and Sheets (setup for the proposal workspace)

The proposal workspace's worker uses Google Drive to make each proposal's folder, save its Word files and
index past work for Builds on, and Google Sheets to add the Proposal Register row when a proposal is
submitted. It signs in as a **service account**, a Google account for a program rather than a person, so
nothing depends on anyone's own login. The dashboard itself never calls Google (AGENTS rule 1). The OAuth
client for people's Google sign-in is a separate step, done with the sign-in phase.

You need to be signed in to Google as a Velocity admin, or have one with you, for steps 1, 4 and 5. It takes
about 20 minutes. Nothing from these steps goes into the repo, a commit, a ticket or a chat: the key file
stays on this PC.

1. **Create the project.** Open https://console.cloud.google.com, sign in with your Velocity account, open
   the project picker at the top of the page, choose **New project**, name it `velocity-bd-team`, keep
   velocityexplorations.com as the organization, and choose **Create**. Make sure the new project is
   selected in the picker before the next step.
2. **Turn on the two APIs.** In the left menu choose **APIs and services**, then **Library**. Search for
   **Google Drive API**, open it and choose **Enable**. Go back to the Library, search for
   **Google Sheets API**, and enable it the same way.
3. **Create the service account.** In the left menu choose **IAM and admin**, then **Service accounts**,
   then **Create service account**. Name it `bd-worker`, choose **Create and continue**, skip the optional
   roles, and choose **Done**. Copy its email address (it ends in `iam.gserviceaccount.com`); step 5 needs it.
4. **Make its key file.** Open `bd-worker`, go to the **Keys** tab, choose **Add key**, then
   **Create new key**, keep **JSON**, and choose **Create**. A file downloads.
   - If Google says key creation is turned off by an organization policy (new Google Cloud
     organizations block it by default), an admin opens **IAM and admin**, then **Organization policies**,
     finds **Disable service account key creation**, and sets an exception for the `velocity-bd-team`
     project only. Then repeat this step.
   - Move the file out of Downloads to a folder outside the repo, for example
     `C:\Users\<you>\.velocity\bd-worker.json`. Do not open it in a chat, email it, or put it in Drive.
5. **Give it the Proposal Library on a shared drive.** The worker can only reach files shared with its email,
   and a shared drive keeps the files owned by Velocity rather than by one person.
   - In Google Drive choose **Shared drives** in the left menu. If the BD Proposal Library is not on one
     yet, choose **New**, name the shared drive `BD Proposal Library`, and move the existing
     "BD Proposal Library" folder into it (right-click the folder, **Organize**, **Move**, then pick the
     shared drive). The folder keeps its id, so `LIBRARY_DRIVE_FOLDER_ID` in `.env` stays as it is.
   - Open the shared drive, choose **Manage members**, paste the service account's email from step 3,
     set its access to **Content manager**, untick **Notify people**, and choose **Share**.
   - Shared drives need a Google Workspace plan that includes them. If **Shared drives** is missing from the
     menu, the plan does not include them; tell Claude, and the worker will use a folder shared with the
     service account instead.
   - If the library folder is already on a shared drive, as Velocity's is (checked 29 Oct), nothing moves: add
     the service account to the folder itself, as a Content manager. It can then list, create, move and trash
     there. It cannot delete for good, so the worker only ever trashes.
6. **Point the repo at the key file.** Open `.env` in the repo folder in a text editor and add one line with
   the file's full path, for example:
   ```
   GOOGLE_SERVICE_ACCOUNT_FILE=C:\Users\<you>\.velocity\bd-worker.json
   ```
   Save the file. `.env` is never committed. Google names the downloaded key after the project and the key's
   id; either rename it to the name on this line or put its own name here.
7. **Check it.** In the repo folder, with the venv active, run `python -m config`. It should list
   `GOOGLE_SERVICE_ACCOUNT_FILE` as set (it never shows values). Then `python -m drafting.worker --drive-check`
   reads the library folder through the service account and says what it found; it never writes. Run
   `pip install -r requirements.txt` first for Google's libraries.

Once Drive is set up, the worker (docs/RUNBOOK.md, The worker) makes each pursuit's folder,
`02 Submissions/<YYYY-MM-DD_portal_short-title>/` with its four folders, the first time one of its steps runs;
the date is the day the draft started. Each step's Word files go to its `02_working/`, a new version replacing
the last under the same link, and the step's card links to them. If Drive fails, the files stay on this PC
and the card says so. While idle the worker refreshes the library's index for Builds on every quarter of an hour
(`drive_items`), and moves a no-go pursuit's folder to `02 Submissions/_no-go/`.

Once a proposal is marked submitted at its Submit gate, the idle worker files it:
- **The folder** is renamed to the day it went in. The library's submission_id carries that date.
- **The final version** goes into `01_submitted/` under its volume's name, for example `white-paper.docx`.
- **The Register row** is added to the "00 Proposal Register" sheet with what the workspace knows: the id, title, portal, agency, type where the format settles it, dates, outcome `pending` and the folder's link. People fill in the rest, and the next sync brings it into the ledger.

When its result is recorded, the outcome note goes to `03_outcome/`. The outcome goes onto that row, cancelled by the agency as `no_award`, with its date; the debrief fills why won or lost only while that cell is blank. Replace the file in `01_submitted/` with what actually went in if it differs. Calls marked Submitted outside the workspace are not filed, so their rows are never duplicated.

If a key file is ever exposed (pasted, emailed or committed), delete that key on the service account's
**Keys** tab, make a new one (step 4), and replace the file on this PC.

## Dashboard

The workspace's browser tests press its buttons, so they run against a throwaway Postgres, never the
ledger: build the dashboard first (`npm run build` in dashboard/), make sure Docker Desktop is running,
then in PowerShell from the repo folder:

```powershell
$env:WORKSPACE_TESTS = "1"; pytest tests/test_dashboard_workspace.py; Remove-Item Env:WORKSPACE_TESTS
```

They start a `postgres:17-alpine` container and the built dashboard on port 8002 against it, seed
pursuits in every state, and remove both at the end.

```powershell
cd dashboard
npm run dev      # http://localhost:8000
```

It reads `dashboard/.env.local` (DATABASE_URL, DASHBOARD_USERS). Pages, the decision buttons and
how they coexist with Slack are in docs/DASHBOARD.md.

To add a person, append `, Name=<Slack id>` to DASHBOARD_USERS in `dashboard/.env.local` and
restart the dashboard. With more than one name, each person picks who they are in the top bar.
Everyone's decisions are kept in the `decisions` table (migration 004) and scored on `/judges`;
the Monday summary ends with one line scoring each judge against the team's decisions.

While the judges are being trained, everyone decides every call: each person's review queue
holds the calls they have not decided. To go back to one decision per call, set
`DASHBOARD_QUEUE=shared` in `dashboard/.env.local` and restart the dashboard.

### Google sign-in

With Google sign-in set up, every page of the dashboard needs a session (phase 11). Anyone at Velocity
signs in at `/login` with their Velocity Google account; nobody else gets in. Who decides then comes
from the session: the name picker goes, and owner-only actions are the owner's alone. Each sign-in
is recorded in the ledger's people table (migration 010), which names the person from then on. A
session lasts 12 hours. Until the three settings below are in `dashboard/.env.local`, the dashboard
keeps the name picker. It takes about 10 minutes in the browser, in the same `velocity-bd-team`
Cloud project as the service account.

1. **The consent screen.** In https://console.cloud.google.com, with `velocity-bd-team` selected, open
   **APIs and services**, then **OAuth consent screen**. If there is no app yet, choose **Get started**:
   - name it `BD Team` and choose your email for support;
   - set the audience to **Internal**, so only velocityexplorations.com accounts can use it;
   - give your email as the contact, and choose **Create**.
2. **The OAuth client.** Open **Clients** (or **Credentials**, then **Create credentials**, then
   **OAuth client ID**):
   - choose **Web application** and name it `BD Team dashboard`;
   - under **Authorized redirect URIs**, add `http://localhost:8000/api/auth/callback/google`. Once the
     dashboard is hosted, add `https://<its address>/api/auth/callback/google` as well;
   - choose **Create**. Google shows a client ID and a client secret. Keep that window open for step 3,
     and never paste them in a chat or a ticket.
3. **The settings.** Open `dashboard/.env.local` in VS Code and add the two values Google showed:
   ```
   AUTH_GOOGLE_ID=<the client ID>
   AUTH_GOOGLE_SECRET=<the client secret>
   ```
   Then, in a terminal in the `dashboard` folder, run `npx auth secret`. It adds a random `AUTH_SECRET`
   to `.env.local` for you.
4. **The people (optional).** Anyone at Velocity can sign in without being listed. To give someone a
   set name and their Slack id, list them on DASHBOARD_USERS with their Google email, as
   `David Wood <david@velocityexplorations.com>=<Slack id>`.
5. **Restart the dashboard.** Opening it now goes to the sign-in page. Choose **Sign in with Google**.
   Log out is in the account menu at the top right.

If the client secret is ever exposed, open the OAuth client, add a new secret, delete the old one, and
put the new one in `.env.local`.

## Running the stages separately

The stage commands from earlier phases still work and share the same ledger:
`python -m portals.vulcan_sof.run_scrape`, `python -m portals.vulcan_sof.run_filter [--all]`,
`python -m review.run_review [--limit N]`. Do not run them while the pipeline is running.
