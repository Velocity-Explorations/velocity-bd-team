# Handover discovery: dashboard redesign and proposal workspace

Read on 27 Oct 2026 from commit `65a5fce` (main, after PR #56). Discovery only: no code was changed. Citations are `path:line` in this repo unless marked as outside it. "Not built" means nothing for it exists on main.

## The biggest gaps

1. **No worker runs agent steps.** Nothing in the codebase starts work when someone approves on the dashboard. Approved requests wait for a twice-daily pass, and the Writer's always-on worker and drafts queue are planned but not built (questions 2 and 7).
2. **No Google Drive access and no Word output.** There is no service account, no OAuth client and no Google or .docx library. The drafting pipeline writes Markdown to a local folder (questions 5 and 6).
3. **The `proposals` table name is taken** by the Proposal Register's past submissions, and its outcome values do not include "cancelled by the agency" (question 1).
4. **No real identity until Google sign-in (PRO-477).** Anyone who can open the dashboard can pick any name, and there are no owners or roles, so owner and leadership approvals cannot be enforced yet (question 3).
5. **Three versions of the proposal workflow** (two claude.ai skills on David's PC, the repo's `drafting/` pipeline, and the design) and two Drive folder conventions. One of each has to be chosen (questions 5 and 10).
6. **The spec is behind the design.** View cards, the full workspace, badges on every row, results with an expected-by date and the "no news yet" reminder are not in the spec, and the build prompts and tests key off the spec's requirement IDs (question 13).
7. **No CI.** Tests run locally before each pull request (question 11).

## 0. The spec

Pasted verbatim from `docs/design/dashboard-design-spec.md` at commit `65a5fce8f42d1e5e3254b6babe6331c3fa695c4d`. Two differences from what was asked: the Proposals section now runs to P8 (P5 to P8 were added on 26 Oct, PRO-562), and the Deciding section is pasted whole (V1 to V9; V1 to V4 are the rows asked for).

### Pages (N1 to N6), lines 31 to 58

```markdown
## Pages

Four sections share one top bar; they replaced seven pages on 26 Oct. The bar carries the brand (Velocity BD), the four section links with the current one highlighted, a count badge on Automation when requests wait, and the account menu (section Account menu and profile). A section with more than one view shows tabs under the page title.

| Section | Tab and path | What it is for | What it shows |
| --- | --- | --- | --- |
| Home | /, no tabs | What needs attention now | Ready for review, the Top 10, calls due in the next 14 days, submissions waiting on a response, and a status line (section Home) |
| Calls | To review, /review | Triage: decide each call rated yes or maybe | Today's review queue: five metric cards, the filter bar, then one row per call with decide buttons (section Calls: To review) |
| Calls | All, /calls | Find any call, change a decision, read votes and notes | Every call scanned, rejected ones too, up to 200 rows, with a Showing N of M line (section Calls: All) |
| Proposals | Pursuing, /proposals | The calls being worked toward a submission | Calls decided Pursue in two sections: Ready to draft, with a Draft button, and Drafting (section Proposals) |
| Proposals | Submitted, /proposals/submitted | Submissions waiting on a response | Calls decided Submitted, longest waiting first (section Proposals) |
| Proposals | Results, /proposals/results | Past submissions and win rate | Today's Proposals page: the proposals table with win rate by portal; an empty state until the Proposal Library fills it |
| Automation | Requests, /requests | Approve the portal assistant's change requests | Waiting requests first (who asked, why, a preview of the change, Approve and Reject with a note), then the last 50 decided with their result |
| Automation | Scans, /runs | Scan health (today's Runs page) | The latest run on top (status, start, duration, stage counts, error, log link), then the last 100 runs; a run still running after two hours is flagged |
| Automation | Judges, /judges | How Claude and Grok compare with people | Per judge: matched, misses, false alarms, maybes; per person: calls decided and how often each judge matched them; between people: agreement; pursued calls a judge said no to |

Past weekly briefs keep a page at /brief, outside the top bar and linked from Home, because Monday's Slack post links there. It shows the week as the Monday 9:00 job posted it: a Top 10 across portals, then a bulletin board per portal (new calls by verdict, calls waiting, top picks, pursued calls closing within 14 days, the week's decisions, the scraper line), each call's decision as of now, and earlier weeks linked at the top.

| ID | Requirement |
| --- | --- |
| N1 | The top bar shows four sections: Home, Calls, Proposals and Automation. The current section is highlighted whichever of its tabs is open. Automation opens on Requests. |
| N2 | Tabs sit under the page title and show which one is open. Each tab has its own address, so a link opens the right view. |
| N3 | While requests wait, their count shows as a badge on Automation and on the Requests tab. |
| N4 | Old addresses keep working: /calls with its filters (the vote notice and shared links use them), /brief (Monday's Slack post), /judges, /requests, /runs and /proposals. A bookmark to / now opens Home, which links to To review. |
| N5 | The account menu sits at the right of the top bar on every page (U1). |
| N6 | The Calls tabs share the filter bar: switching between To review and All keeps the portal, tag and open or closed filters. |

The rest of this spec calls To review the queue and All the All calls page. They get the most use and carry most of the requirements below.
```

### Home (H1 to H7), lines 60 to 74

```markdown
## Home

Home is the landing page: one screen that answers what needs attention now. Each block reads the ledger live, links to the full list behind it, and has an empty state.

| ID | Requirement |
| --- | --- |
| H1 | Ready for review: how many calls wait for the viewer (for anyone, in shared mode), split into yes and maybe, and how many arrived this week, with a link to To review. These are the counts the queue's metric cards show (Q2). |
| H2 | Top 10: the best open calls nobody has decided, across portals, ranked as the Monday brief ranks them: yes before maybe, then the nearest deadline, then the newest. Each shows both judges' verdicts, the title linked to its portal page, the portal and the deadline, and links to the call on All calls. |
| H3 | Due in the next 14 days: pursued calls first, then undecided calls rated yes or maybe, soonest first, each with its deadline and days left. A call whose deadline is not a date (a forecast quarter, members only, no close date) is left out. |
| H4 | Submitted, waiting on a response: every call whose decision is Submitted, longest waiting first, with its portal, who marked it Submitted and when, and days waiting, then a link to Proposals, Submitted. |
| H5 | A status line: requests waiting (linked to Automation, Requests), the last scan's result and when it ran (linked to Scans) (a failed scan says so in words), and how often Claude and Grok agree. |
| H6 | A link to the past weekly briefs (/brief). |
| H7 | Home records nothing; decisions stay on Calls. |

Recording whether a submission was won or lost is not part of Home yet; until it is, Results reads the Proposal Register.
```

### Proposals (P1 to P8), lines 110 to 123

```markdown
## Proposals

Proposals follows a call from Pursue to its result. Pursuing and Submitted read each call's decision; Results reads the Proposal Register.

| ID | Requirement |
| --- | --- |
| P1 | Pursuing: calls whose decision is Pursue, in two sections, Ready to draft and Drafting (P5 to P8), nearest deadline first in each: the title linked to its portal page, the portal, the deadline and days left, who decided and when, and the notes. |
| P2 | Submitted: calls whose decision is Submitted, longest waiting first: the title, the portal, who marked it Submitted and when, days waiting, and the notes. |
| P3 | Results: past submissions from the Proposal Register with their outcome, and win rate by portal (today's Proposals page). |
| P4 | Decisions change on All calls, as today; each row here links to its call there. |
| P5 | Ready to draft: pursued calls that are still open (the deadline has not passed), have no draft yet, and have solicitation text the Writer can read; each has a Draft button. A pursued call that cannot be drafted says why in place of the button, for example needs the solicitation first for a members-only page. |
| P6 | Draft starts a draft at once: the click is the person's approval, since a draft takes 20 to 60 minutes and costs money. The call moves to Drafting. A second draft of the same call, or a call marked not relevant, is refused with the reason. |
| P7 | Drafting: queued and running drafts with their progress and Cancel; finished drafts with their readiness line (for example Not ready: 1 PERSON WRITES, 34 NEEDS INPUT) and Open; failed drafts with the reason and Retry. |
| P8 | The Draft button and draft progress need the drafts queue and worker from the Draft-Ready Upgrade (U1) and the Writer Plan (W2a), in docs/plans. Until they exist, both sections list their calls and Draft says Drafting is not set up yet. |
```

### Account menu and profile (U1 to U6), lines 205 to 216

```markdown
## Account menu and profile

The account menu at the right of the top bar is each person's own corner: who is deciding, their settings, and signing out (26 Oct).

| ID | Requirement |
| --- | --- |
| U1 | The menu opens from the person's initials and name, with Deciding under the name. It holds the name with Decisions are recorded as you, Profile settings, Table settings, Switch user (until Google sign-in, V1) and Log out (V2). |
| U2 | Profile settings is a page at /profile. It shows the person's display name and initials and, after Google sign-in (PRO-477), the account they are signed in with. |
| U3 | Where the dashboard opens: Home (the default) or To review. Opening / takes the person there. |
| U4 | Default filters for Calls: portals, tags and open or closed, applied when Calls opens with no filters in its address; a shared link's own filters still win (F10). |
| U5 | Time zone: every time and converted deadline (T1, T2) shows in the person's zone in place of the dashboard's America/Denver. |
| U6 | Profile settings are kept for this browser until sign-in identifies people; keeping them per person across devices needs sign-in and a ledger table (Not built yet). |
```

### Deciding (V1 to V9), lines 174 to 188

```markdown
## Deciding

There is no login until the dashboard is hosted behind Google's sign-in (PRO-477); until then the account menu says who is deciding, and every person's every decision is kept.

| ID | Requirement |
| --- | --- |
| V1 | Deciding as: the account menu shows who is deciding. Until Google sign-in is live, its Switch user list holds the other allowed people (DASHBOARD_USERS), with a line saying why; choosing one applies at once, with no Set step (PRO-553). |
| V2 | Log out in the account menu clears the choice, as Clear User Selection does today; behind Google's sign-in it signs the person out. |
| V3 | With one allowed person the menu has no Switch user list. Behind Google's sign-in it shows the signed-in person, or that the account cannot decide. |
| V4 | Deciding with nobody chosen refuses with: Choose who you are (top right) before deciding. |
| V5 | Decisions are Pursue, Not relevant, Submitted and Dismiss. Pursue and Submitted count as yes, Not relevant and Dismiss as no, when scoring the judges. |
| V6 | On the queue, the first decision becomes the call's decision; later ones are added beside it without changing it. A call's decision changes only from All calls. |
| V7 | Every decision is kept per person, with its note and time, so the judges page can score each judge against each person. |
| V8 | Notices after an action show at the top of the page: green for done, red for refused, with what happened in one sentence. |
| V9 | Slack informs and never decides: each run posts a card per new yes or maybe call, card threads become notes, and cards are edited to show the decision made here. |
```

### Q9 under Calls: To review, line 90

```markdown
| Q9 | Decide cell: a Decide menu listing Pursue (green), Not relevant (grey), Submitted (blue) and Dismiss (grey); choosing one records it. Add a note under the menu opens an optional note (up to 2,000 characters). The menu replaced four one-click buttons on 26 Oct. |
```

### The 26 Oct rows of the Decision log, lines 363 to 366

```markdown
| Date | Decision | Ticket |
| --- | --- | --- |
| 26 Oct | The Portals menu lists every portal that has scanned, with its call count, so a portal with nothing open no longer looks missing | PRO-563 |
| 26 Oct | Pursuing splits into Ready to draft, with a Draft button per call, and Drafting, with progress and finished drafts; a call is ready when it is pursued, still open, without a draft and with readable solicitation text | PRO-562 |
| 26 Oct | The fourth section is Automation, not Admin, with tabs Requests, Scans (today's Runs) and Judges; an account menu replaces the Deciding as picker and the Settings button, with Profile settings (name, where the dashboard opens, default filters, time zone); deciding on To review uses a Decide menu in place of four buttons | PRO-561 |
| 26 Oct | Seven pages become four sections: Home (a new landing page in place of the Monday brief page, whose weeks stay at /brief), Calls (To review and All), Proposals (Pursuing, Submitted, Results) and Admin (Requests, Runs, Judges); submissions waiting on a response come from calls marked Submitted | PRO-560 |
```

## 1. Data

**What stores the ledger.** One database, chosen by `DATABASE_URL`:
- **Production:** hosted Postgres on Supabase, reached through the Session pooler (`docs/STATUS.md:7-14`).
- **Tests and local work:** SQLite (`ledger/db.py:3-13`, `ledger/db.py:65-77`). Each test gets a fresh migrated SQLite file (`tests/conftest.py:12-15`).
- **Connections:** Python keeps one connection per thread (`ledger/db.py:107-146`, PRO-550). The dashboard reads Postgres only, through postgres.js (`dashboard/lib/db.ts:1`).
- **Out of date:** `AGENTS.md:11` still says "one SQLite ledger database".

**How migrations work.** `python -m ledger.migrate` applies `ledger/migrations/NNN_name.sql` in order. Each runs in one transaction and is recorded in `schema_migrations`, so a rerun skips it (`ledger/migrate.py:6`, `ledger/migrate.py:42-66`).
- **Portable SQL:** TEXT, INTEGER and REAL only, JSON stored as TEXT, timestamps as ISO-8601 UTC text (`ledger/migrations/001_initial.sql:2`).
- **Dialect token:** `@@AUTOINCREMENT@@` becomes AUTOINCREMENT on SQLite or GENERATED BY DEFAULT AS IDENTITY on Postgres (`ledger/migrate.py:23-24`).
- **Parsing:** comment lines are dropped and statements are split on semicolons (`ledger/migrate.py:33-39`).
- **Rules:** only the Coordinator changes the schema, additive only (add tables or columns, never rename or drop). Every schema PR updates `docs/LEDGER_SCHEMA.md` and `ledger/schema.sql` in the same commit; `schema.sql` must equal the result of all migrations (`ledger/schema.sql:1-2`; AGENTS.md, "Working alongside other agents", rule 3).
- **Count:** migrations 001 to 007 exist.

**Where things live.**

| Data | Where | Defined at |
|---|---|---|
| Calls | `calls`: id, portal, title, type, department, naics_code, set_aside, posted_date, due_date (as the portal wrote it), description, url, first and last seen, filter_result, filter_reason, match_tier, matched_keywords, ai_verdict, ai_reasoning, reviewed_at, slack_channel, slack_ts, human_status, human_by, human_at, human_notes, extra (portal fields, JSON as text), updated_at | `ledger/migrations/001_initial.sql:20-53` |
| Judge verdicts and reasons | `calls.ai_verdict` and `ai_reasoning` hold Claude's, the verdict that decides what is posted. `judgments` keeps every judge's verdict per call: judge, model, verdict, reasoning, rated_at; the newest row per judge wins | `001_initial.sql:41-43`, `ledger/migrations/003_judgments.sql:7-15` |
| Votes and decisions | `decisions`: one row per person's decision (decided_by, status, note, decided_at). `calls.human_status`, `human_by` and `human_at` hold the call's current decision | `ledger/migrations/004_decisions.sql:6-13`, `001_initial.sql:47-49` |
| Notes | Lines appended to `calls.human_notes` as `[time name] note`, from the dashboard and from Slack thread replies; a decision's own note is also in `decisions.note` | `ledger/queries.py:201` (`append_note`), `slack/sink.py:400-428` |
| Tags | `call_tags` (call_id, tag, source: rule, claude or grok) and `tag_list` | `ledger/migrations/006_call_tags.sql:5-14`, `007_tag_list.sql:5` |
| Past submissions | `proposals`, keyed by submission_id, filled from the Proposal Register | `001_initial.sql:55-79` |
| Agent requests | `change_requests` | `ledger/migrations/002_change_requests.sql:7-25` |
| Scans | `runs` | `001_initial.sql:7-18` |
| Weekly briefs | `briefs` | `ledger/migrations/005_briefs.sql:5-14` |

**Could we add `proposals` and `proposal_steps`?** Not under those names.
- **The name is taken:** `proposals` already holds the Register's past submissions (`001_initial.sql:55-79`). The Register sync upserts it by submission_id (`library/register.py:134`, `ledger/queries.py:299`), so workspace rows in the same table would collide with or be overwritten by the sync.
- **Use new tables instead:** for example `pursuits` (one per call being worked) and `pursuit_steps`, with a link to the Register row (`proposals.submission_id`) once the proposal is submitted.
- **Result values differ:** `proposals.outcome` allows won, lost, no_award, pending, withdrawn and shortlisted (`001_initial.sql:67`). The design's "cancelled by the agency" is not one of them. Changing a CHECK constraint is not additive (Postgres needs DROP and ADD CONSTRAINT, SQLite a table rebuild). So keep the workspace result in the new table with its own values, and map it when the Register row is written (cancelled by the agency becomes no_award), unless the team agrees to an exception.
- **Reviews need a third table:** the reviewer and leadership passes, approved change by change, need a table of proposed changes.

A migration in the repo's style (portable SQL, additive):

```sql
-- 008_pursuits: proposals being worked on the dashboard, one per call, their steps, and the
-- changes reviewers propose. JSON is stored as TEXT; timestamps are ISO-8601 UTC text.

CREATE TABLE IF NOT EXISTS pursuits (
  id                  INTEGER PRIMARY KEY @@AUTOINCREMENT@@,
  call_id             TEXT NOT NULL REFERENCES calls (id),
  owner               TEXT NOT NULL,
  format              TEXT,
  approval_mode       TEXT NOT NULL DEFAULT 'every_step' CHECK (approval_mode IN ('every_step', 'key_gates')),
  direction           TEXT,
  builds_on           TEXT,
  drive_folder_id     TEXT,
  current_step        TEXT,
  state               TEXT NOT NULL DEFAULT 'working' CHECK (state IN ('working', 'waiting', 'no_go', 'submitted', 'closed')),
  checklist           TEXT,
  submitted_at        TEXT,
  confirmation_number TEXT,
  result_expected_by  TEXT,
  result              TEXT CHECK (result IS NULL OR result IN ('won', 'lost', 'withdrawn', 'cancelled_by_agency')),
  result_at           TEXT,
  submission_id       TEXT,
  created_at          TEXT NOT NULL,
  updated_at          TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pursuits_call ON pursuits (call_id);

CREATE TABLE IF NOT EXISTS pursuit_steps (
  id             INTEGER PRIMARY KEY @@AUTOINCREMENT@@,
  pursuit_id     INTEGER NOT NULL REFERENCES pursuits (id),
  step           TEXT NOT NULL,
  attempt        INTEGER NOT NULL DEFAULT 1,
  state          TEXT NOT NULL DEFAULT 'queued' CHECK (state IN ('queued', 'working', 'ready', 'approved', 'changes_asked', 'failed', 'skipped')),
  files          TEXT,
  summary        TEXT,
  error          TEXT,
  decided_by     TEXT,
  decided_at     TEXT,
  decision_note  TEXT,
  started_at     TEXT,
  finished_at    TEXT,
  updated_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pursuit_steps_pursuit ON pursuit_steps (pursuit_id, step, id);
CREATE INDEX IF NOT EXISTS idx_pursuit_steps_state ON pursuit_steps (state, id);

CREATE TABLE IF NOT EXISTS step_changes (
  id           INTEGER PRIMARY KEY @@AUTOINCREMENT@@,
  step_id      INTEGER NOT NULL REFERENCES pursuit_steps (id),
  location     TEXT,
  before_text  TEXT,
  after_text   TEXT,
  reason       TEXT,
  state        TEXT NOT NULL DEFAULT 'proposed' CHECK (state IN ('proposed', 'accepted', 'rejected')),
  decided_by   TEXT,
  decided_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_step_changes_step ON step_changes (step_id, id);
```

Notes on the sketch:
- **JSON columns:** `builds_on`, `files` (name, Drive file id, link per file) and `checklist` are JSON stored as TEXT, like `calls.extra`.
- **Free-text step:** `step` has no CHECK, so the step list can change without a constraint change; the code validates it.
- **One pursuit per call:** the unique index matches "start a draft once the call is marked Pursue". If a call can be started again, drop the index and keep the newest pursuit.
- **Same PR:** `docs/LEDGER_SCHEMA.md`, `ledger/schema.sql` and `tests/test_migrate.py` (which lists every expected table) change with the migration.

## 2. Jobs

**Today.** Windows Task Scheduler on David's PC runs everything. `scripts/install-schedule.ps1` registers the tasks, each starting the venv's python through `conhost.exe --headless` (`scripts/install-schedule.ps1:33-46`).

| Task | Command | When | Registered at |
|---|---|---|---|
| Pipeline | `run.py --wait-lock 30`: every portal's fetch, filter, tags, Claude's review, Grok's verdict and Slack cards | Sunday 22:00 | `install-schedule.ps1:16-27`, `:49-62` |
| Feedback | `run.py --feedback-only`: Slack replies into notes, dashboard decisions onto the cards | Daily 18:00 | `:73-80` |
| Reminders | `run.py --remind`: pursued calls due within 14 days | Daily 08:00 | `:86` |
| Weekly summary | `run.py --post-summary` | Monday 09:00 | `:89-90` |
| Requests | `run.py --apply-requests` | Daily 12:07 and 17:07 | `:97-99` |

- **The judges** are not a separate job. Claude reviews and Grok gives its verdict inside each portal's run (`run.py:246-251`, `run.py:285`).
- **The lock:** `data/pipeline.lock` keeps one pipeline at a time. A lock older than two hours, or whose process has gone, is taken over (`run.py:68-70`, `run.py:110-143`).
- **Records:** each run writes a `runs` row and `data/logs/run_*.log` (`run.py:22-26`, `ledger/queries.py:46`).

**Could a proposal agent use the same mechanism?** Yes, with changes:
- **Nothing runs continuously today.** A step should start within minutes of an approval. That needs either a scheduled task repeating every few minutes (Task Scheduler supports repetition) or an always-on worker. The Writer Plan already designs the worker: a `drafts` queue in the ledger and a worker on the PC that picks a request up within about 20 seconds (`docs/plans/writer-plan.html:121`, `:257`). It is not built.
- **Separate lock.** The worker must not take `data/pipeline.lock`. A 20 to 60 minute step would otherwise hold up Sunday's scan for its 30-minute wait, then make it give up.
- **One step at a time works.** The drafting pipeline already runs from any phase to any phase, loading what earlier phases saved (`drafting/cli.py:49-55`, `--from-phase` and `--to-phase`; `drafting/pipeline.py:410`).
- **Status reporting.** The worker claims a queued step with a guarded update, the pattern of `claim_request` (`ledger/queries.py:436`). It sets working, then ready, or failed with the error, as `runs` and `change_requests` already do, and the dashboard reads those rows.
- **Where it runs.** The PC must be on for steps to move. The Anthropic key, and any Drive credentials, live there.

## 3. Sign-in

- **Google sign-in (PRO-477) is not live.** The container and the check are built (PRO-511). With `DASHBOARD_IAP_AUDIENCE` set, `proxy.ts` refuses any request without IAP's signed header, and every server action verifies it again (`dashboard/proxy.ts:8-11`; `dashboard/lib/iap.ts:3-13`, `:32`; `dashboard/lib/viewer.ts:22-31`). Hosting it on GKE with Alec is still open (`docs/STATUS.md:31-33`); the deploy steps are in `dashboard/README.md:44-79`.
- **Who is deciding today:**
  - The `bd_viewer` cookie, set by the Deciding as picker (`dashboard/app/actions.ts:95-104`). It counts only if it names someone on the allowlist; with one allowlisted person, that person is used (`dashboard/lib/people.ts:41-54`, `dashboard/lib/viewer.ts:26-39`).
  - It is self-asserted: anyone who can open the dashboard can pick any name.
  - Today the dashboard runs only on David's PC (`docs/STATUS.md:33`).
- **Who may decide:** the `DASHBOARD_USERS` environment variable, with entries of the form `Name <email>=SlackId` (`dashboard/lib/people.ts:11-26`, `dashboard/lib/viewer.ts:7-9`). It has listed David and Shaun since 20 Oct (`docs/STATUS.md:27`). There are no roles: everyone on it can decide, approve requests and change settings.
- **Risk:** owner-only approvals and leadership passes cannot be enforced until IAP is live. Even then they need an owner and role model the ledger does not have.

## 4. Slack

- **What is connected:**
  - One bot (`BD_SLACK_BOT_TOKEN`) posts to one channel (`SLACK_CHANNEL_ID`), with the scopes chat:write, channels:history and channels:join (`slack/bd-bot.manifest.json:13-19`; `slack/sink.py:63`, `:101-102`).
  - **Existing digests:** a daily 08:00 reminder of pursued calls due within 14 days (`run.py:450`), and the Monday summary, which links to `/brief` (`slack/sink.py:311`).
- **Thread per call: only for calls that got a card.** The pipeline posts one card per new call rated yes or maybe and stores its `slack_channel` and `slack_ts` on the call (`slack/sink.py:190-208`, `001_initial.sql:44-45`). These have no thread:
  - rejected calls;
  - calls found before Slack delivery started;
  - calls marked Pursue from All calls without ever getting a card.
- **Posting into a thread is not built.** Every post goes to the channel's top level; `slack/sink.py:219-232` sends no `thread_ts`.
  - Adding `thread_ts` is small and needs no new scope.
  - "Step ready", "step behind" and a daily digest would be new `run.py` jobs reading the ledger.
  - The dashboard has no Slack client and, under AGENTS rule 1, should not call Slack itself (`AGENTS.md:39`).
- **Thread replies come back as notes: yes, once a day at 18:00.** The feedback pass reads each card's thread with `conversations.replies` and appends new human replies to `calls.human_notes` (`run.py:399`; `slack/sink.py:376`, `:400-440`).
  - The author is stored as a Slack user id and shown by name through `DASHBOARD_USERS`.
  - Replies are deduplicated by their text.
  - The same pass edits the card to show the dashboard decision.

## 5. Google Drive

- **Access: none from the code.** There is no service account, no OAuth client and no Google library in `requirements.txt`, and the `gog` CLI is not installed (`AGENTS.md:129`). Only the Library folder's id is configured (`LIBRARY_DRIVE_FOLDER_ID`, `config.py:27`, `.env.example:35`). The Register sync reads JSON files that Claude writes after reading the sheet through David's Google connectors in a chat session (`library/register.py:7-11`, `docs/STATUS.md:63-66`).
- **Folder conventions: there are two, and they disagree.**
  - **Proposal Library** (`docs/LIBRARY_CONVENTIONS.md:5-16`): at the top, `00 README`, `00 Proposal Register` and `01 Company Reference/`. Each submission gets `Submissions/<YYYY-MM-DD_portal_short-title>/`, dated the day it was submitted, holding `00_solicitation/`, `01_submitted/`, `02_working/` (drafts: "the drafting pipeline writes here") and `03_outcome/`.
  - **The opportunity-assessment playbook** (outside the repo; see question 10): creates an active `Submissions/{TopicNumber}_{ShortTitle}/` at discovery, and moves it to `Past Submissions` once it is sent or passed.
  - The Library conventions have no "Past Submissions" folder. The build has to pick one convention, including what the folder is called before a submission date exists.
- **Create, list, pick or upload: not possible today.** It needs a Google Cloud project with the Drive API, plus one of:
  - a service account added to a shared drive (simplest for a background worker);
  - OAuth for each person (needed for Google's file picker in the browser).

  The worker would create folders and upload files; the dashboard would list a folder's files on the server or use Google's picker.
- **Word files: nothing writes .docx.** The drafting pipeline writes Markdown into a local folder (`drafting/pipeline.py:32-38`, `:129-130`). Its Deliver phase leaves the files there: "W3 uploads to Drive; here it stays local" (`drafting/pipeline.py:375-379`). python-docx, or a conversion step, would be new.

## 6. Proposal Library

- **What it is:** Velocity's past proposals, white papers and RFI responses with their outcomes, kept in the "BD Proposal Library" Drive folder with the `00 Proposal Register` sheet (`docs/LIBRARY_CONVENTIONS.md:1-16`).
- **Where its data comes from:** the Register is filled by hand. `python -m library.register sync` copies it into the ledger's `proposals` table from JSON files Claude writes (`library/register.py:1-11`, `:134`). The dashboard's Proposals page reads that table (`docs/DASHBOARD.md:21`).
- **Not built:** AGENTS.md lists Drive sync, text extraction, chunking and embeddings for `library/` (`AGENTS.md:24`), but only `library/register.py` exists. There is no search over past proposals yet; the later Library phases are open (PRO-475).
- **API or export:** none, beyond reading the ledger table.
- **Writing results and debriefs back: no.** The sync only reads the sheet. Places to hold results do exist:
  - the ledger table has outcome, outcome_date, award_value and why_won_or_lost (`001_initial.sql:67-72`);
  - the folder convention has `03_outcome/` for debriefs (`docs/LIBRARY_CONVENTIONS.md:16`).

  Writing to the sheet or to Drive needs the Google access from question 5. The Proposal Library plan already intends a "Submitted step" that creates a Register row for each call marked submitted, matched through a new `proposals.source_call_id` (`docs/plans/proposal-library-plan.html:452`, `:107`). It is not built.

## 7. Agent update requests

**How it works today:**
1. A propose tool inserts a `change_requests` row as proposed (`ledger/queries.py:346`).
2. On the Requests page, Approve or Reject calls the server action `decideRequestAction` (`dashboard/app/actions.ts:70-90`). It updates the row only while it is still proposed, so a request is decided once (`dashboard/lib/queries.ts:502-524`).
3. Nothing runs at that moment. `run.py --apply-requests` (`run.py:718`), scheduled at 12:07 and 17:07, claims each approved row (approved to applying, guarded; `ledger/queries.py:436`).
4. It carries the request out (`run.py:600-716`):
   - a keyword change commits the portal's keywords.yaml to main;
   - a re-review reruns the review on the call;
   - a scan runs one portal;
   - a fault report files a GitHub issue.
5. It finishes the row as applied or failed, with a result (`ledger/queries.py:446`).

The page tells people a request runs "at its next pass (12:07 or 17:07)" (`dashboard/lib/requests.ts:19`). Draft requests are left out of the apply pass and stay approved, waiting for a Writer that does not exist yet (`run.py:78`).

**Reusing it for step approvals.** The pattern can be reused (guarded state changes, a worker that claims and finishes), but not the table or the schedule:
- `change_requests.kind` has a CHECK constraint (`002_change_requests.sql:9`). A new kind means changing it, which is not additive.
- Twice a day is too slow for a step-by-step workflow.
- A step approval belongs to a pursuit, with its files and change-by-change decisions, which `change_requests` cannot hold.

So build a `pursuit_steps` state machine (question 1) and a worker (question 2), using the same guarded-update helpers.

## 8. Routing and actions

- **Framework:** Next.js 16.4.2 App Router with React 19.3.1 (`dashboard/package.json:15-17`).
  - Pages are server components rendered on every request (`export const dynamic = "force-dynamic"`, for example `dashboard/app/calls/page.tsx:22`) and read the ledger directly; there is no API layer.
  - Client code is three components: ViewerPicker, SettingsDialog and MenuController.
- **Real paths and query parameters: yes.** The current pages already work this way: every filter and sort is a URL parameter, read with helpers such as `pickMany`, `pickState` and `pickSort` (`dashboard/lib/filters.ts`; `dashboard/app/calls/page.tsx:38-45`).
  - `/calls?portal=NSTXL&sort=due&dir=asc` works today.
  - A `view` parameter, or new routes such as `/review` and `/proposals/submitted`, are ordinary additions. Old links must keep working (spec N4).
- **Write actions:** Next.js server actions in `dashboard/app/actions.ts` (`"use server"` at line 1):

  | Action | Where |
  |---|---|
  | `decide` | `:34` |
  | `decideRequestAction` | `:70` |
  | `setViewer`, `clearViewer` | `:95-109` |
  | `saveColumns`, `resetColumns` | `:113-122` |

  - **Authorisation:** each action reads the viewer with `currentViewer()` and refuses when there is none. There is no other check: no roles and no owners.
  - **Writing:** writes go straight to the ledger through postgres.js, and pages refresh with `revalidatePath`.

## 9. Concurrency

**For decisions, it is already built (C8):**
- The decide form carries the decision the page showed (`expected`; `dashboard/app/actions.ts:26-42`).
- `decideCall` opens a transaction and locks the call row (`SELECT ... FOR UPDATE`, `dashboard/lib/queries.ts:274`).
- It compares the call's current decision with `expected` (`:278`). If they differ, it writes nothing and returns what the call is now, which the page shows as its notice.
- Request approvals are guarded by `WHERE id = ... AND status = 'proposed'`, and the refusal names who decided first (`dashboard/lib/queries.ts:511-523`).

**Limits:**
- The guard compares the decision itself, not who made it or when. Two people choosing the same decision both succeed; by design, the second is added beside the first.
- Notes are append-only and unguarded.
- The review queue's "keep" mode deliberately skips the check while everyone decides every call.

**For proposal steps, use the same two patterns:**
- Every step form carries the step's state and `updated_at` (or a version number).
- The action updates `WHERE id = ... AND state = 'ready' AND updated_at = ...`. If no row matches, it says what the step is now.
- The worker claims a step with the same kind of guard, so a step cannot be approved while it is being redone.

## 10. Skills

**Where they live:** none are in the repo.
- **opportunity-assessment and proposal-drafting** are claude.ai skills synced to David's PC, under `C:\Users\<user>\.claude\skills\synced\<org>_<account>\`. The folder is per Claude account, and it changed when the Claude account in Claude Code changed on 26 Oct.
- **ai-slop-detection** is a local Claude Code skill at `C:\Users\<user>\.claude\skills\ai-slop-detection\`, with its scanner at `scripts/slop_scan.py`.

**Inputs and outputs:**
- **opportunity-assessment** (its SKILL.md, lines 12 to 113):
  - in: a URL, a PDF or a topic number;
  - out: a submission folder, an opportunity summary and an alignment assessment (both in the conversation), and `{TopicNumber}_Requirements_and_Submission_Checklist.docx`, made with the docx skill;
  - it stops for David at the end of each of its four phases;
  - the synced copy ends at the heading of its "Section 2" (the submission checklist), with nothing under it. It looks cut off and should be checked against the claude.ai original.
- **proposal-drafting** (its SKILL.md, lines 12 to 173):
  - in: the submission folder and the requirements document;
  - out: versioned Word drafts (`{TopicNumber}_Technical_Volume_DRAFT_v1.docx` and on), a solicitation compliance check, three review cycles (two independent evaluators, then Velocity leadership, each followed by a check-in), and finalisation.
- **The slop scanner:**
  - in: a draft file and, optionally, the solicitation;
  - out: JSON findings;
  - the repo already runs it as a subprocess in drafting phase 7.7, finds it through the `AI_SLOP_SCAN` path (`drafting/slop_gate.py:25`, `:65-84`), and turns the JSON into a ready or not ready verdict (`:94-117`).

**Can an app-run agent call them?** Not as they are. They are written for an interactive Claude session (claude.ai or Claude Code) that checks in with David, uses the docx skill and saves into a folder it can reach. An agent run by the app would call the Anthropic API through the repo's client (`drafting/llm.py`, default model claude-sonnet-5-5 at line 25), and it needs:
- the skill text vendored into the repo, or uploaded through the API's Skills support;
- the check-ins replaced by the dashboard's approvals;
- Word and Drive output, which it does not have (questions 5 and 6).

**The repo's own pipeline is a third version of the same work.** `drafting/` ports the earlier RFP agent (`reference/yukon/rfp_response_agent.py`) as phases 1 to 8 (`drafting/phases.py:14-28`). The phases are Listing, Attachments, Past experience, Requirements, Alignment, Outline, Draft, four review passes, Compliance, Checklist, Polish, Opening (a person writes it), Slop check and Deliver. It is fully automatic and writes Markdown. The design's steps follow the two skills more closely (Discovery, Opportunity summary, Go or no-go). The build should choose one source of truth for the steps and their prompts.

## 11. Testing and deployment

**Tests:**
- **pytest:** 58 files in `tests/`. 531 pass and 13 skip without a dashboard; with `DASHBOARD_TEST_URL` pointing at a running dashboard, 546 pass (26 Oct). Python tests get a fresh migrated SQLite ledger (`tests/conftest.py:12-15`).
- **Dashboard unit tests:** `node --test` over `dashboard/lib/**/*.test.ts` (`dashboard/package.json:9`), 91 passing. They cover display logic, not the SQL queries.
- **Browser tests:** `tests/test_dashboard_*.py` drive a running dashboard with Playwright. They only read and set cookies, because they run against the live ledger.
- **The brief:** `tests/test_design_brief.py` keeps `docs/design` consistent: links, requirement IDs, prompt numbering and no dashes.

**CI:** none. There is no `.github/` folder. Tests run locally before each pull request, and PRs are squash-merged once verified.

**Deployment:**
- **The pipeline** runs on David's PC through Task Scheduler (`scripts/install-schedule.ps1`, tested by `tests/test_schedule_script.py`).
- **The dashboard** runs locally with `npm run dev` on port 8000. A production container exists for GKE behind IAP (`dashboard/Dockerfile`: Node 24, port 8080, `/healthz` for the load balancer), but it is not deployed (`dashboard/README.md:44-79`, PRO-477).

**What a new feature should include:**
- a Linear ticket and a branch named `<agent>/<task>`;
- failing tests first: pytest for Python, `node --test` for new dashboard logic, and a read-only browser test for new UI behaviour;
- any schema change as a Coordinator migration, with `docs/LEDGER_SCHEMA.md`, `ledger/schema.sql` and `tests/test_migrate.py` updated in the same commit;
- `docs/DASHBOARD.md` and `docs/STATUS.md` updated, plus `docs/RUNBOOK.md` for a new scheduled job;
- no en or em dashes anywhere;
- nothing login-gated, no credentials and no CUI in commits, fixtures or screenshots (`AGENTS.md:59`);
- a squash-merged PR whose subject ends in the ticket id, with a `ref` line.

## 12. Call descriptions

**Yes: every stored call has a description.** In the live ledger on 27 Oct, all 187 calls had one (a query over `calls` grouped by portal).
- **Where:** `calls.description` (`ledger/migrations/001_initial.sql:30`), as plain text cut to a limit each adapter sets.
- **Not on the dashboard yet:** the dashboard neither selects nor shows it (`dashboard/lib/queries.ts` never reads `description`).
- **Used in review:** Claude and Grok read its first 1,500 characters in their prompt (`review/reviewer.py:38`, `:187`, `:199`).

| Portal | What the description is | Limit (characters) | Stored on 27 Oct: calls, average length, longest |
|---|---|---|---|
| Vulcan SOF | The description from the call's detail page. When that pattern misses, a slice of the page body, flagged `vulcan_description_fallback` in `extra` | 1,500 (`portals/vulcan_sof/scrape.py:47`, `:92`, `:100`) | 61, 1,461, 1,500 |
| SAM.gov | The notice's description, read with one extra API request per notice | 4,000 (`portals/sam_gov/records.py:21`, `portals/sam_gov/api.py:174-180`) | 4, 509, 1,089 |
| NASA Forecast | A sentence the adapter builds from the forecast row (office, expected quarters, value, NAICS), then the row's own Summary and Description | 4,000 (`portals/nasa_forecast/records.py:17`, `:51-66`) | 94, 829, 1,306 |
| NSTXL | The project page's text. For a members-only page, only "Member-only page on NSTXL: sign in as a member to read it." | 3,000 (`portals/nstxl/records.py:21-23`, `:199`) | 16, 1,436, 3,000 |
| SSC Front Door | The listing's text | 1,500 (`portals/ssc_front_door/records.py:22`, `:129`) | 7, 422, 580 |
| DIU | The area of interest's text | 4,000 (`portals/diu/records.py:21`, `:65`, `:79`) | 2, 4,000, 4,000 |
| AFWERX, SpaceWERX | Not a synopsis: a few sentences the adapter writes (what the listing is, its dates, the DSIP or Phase II note) | none (`portals/shared/funding_list.py:225-240`, `:262`) | 2 and 1, about 300 to 360 |
| DOE SBIR | The solicitation's summary and body | 4,000 (`portals/doe_sbir/records.py:23`, `:150`) | none stored yet |
| Space Florida | The RFP's text | 4,000 (`portals/space_florida/records.py:19`, `:84`) | none stored yet |
| APFIT | A fixed paragraph about APFIT plus the cycle's status | none (`portals/apfit/records.py:21`, `:60`) | none stored yet |

**For the design's Description column:**
- **No scanner change is needed to show it.** The dashboard's queries add the column.
- **How much fits in a cell.** The longest descriptions are 3,000 to 4,000 characters, so 200 rows of All calls could carry up to 800 KB of text. Select the first few hundred characters for the table and load the rest when a row is opened.
- **Some text isn't the portal's own synopsis.** The adapters write the text for AFWERX, SpaceWERX and APFIT, and NASA's first sentence. NSTXL's members-only note is a placeholder. The design should say whether these show as they are or are labelled.
- **SAM.gov text costs quota.** SAM.gov stores a notice only after reading its description, at one request per notice (`portals/sam_gov/scrape.py:1-12`). With 10 requests a day, 266 notices were still waiting on 26 Oct.
- **Vulcan SOF text is login-gated.** It's fine on the dashboard, which will sit behind sign-in once hosted, but never in the public repo, the snapshot or test fixtures.
- **The spec is out of date here.** Its "Data per call" row says "Up to 1,500 characters"; the limits run from 1,500 to 4,000, so that row needs correcting.

## 13. Anything else

**Conflicts between the codebase and the design:**
1. **The `proposals` table name is taken** (question 1).
2. **The dashboard cannot run the agent, call Slack or call Drive itself.** Components talk only through the ledger (`AGENTS.md:39`). Every workspace button writes a ledger row that a worker on the PC acts on, and the page shows that row's state.
3. **Missing pieces:** no worker, no Drive access, no Word output and no thread posts (questions 2, 4 and 5).
4. **Two folder conventions and three step lists** (questions 5 and 10).
5. **Different result values** from the Register's outcome list (question 1).
6. **No identity yet.** Owner approvals and leadership passes need Google sign-in (PRO-477), plus an owner and role model; today any name can be picked.
7. **One fact in two places.** A call's Submitted decision and the workspace's Submit gate both record the submission. Today Submitted is a triage decision anyone can choose (`004_decisions.sql:10`). The Submit gate should set it, and the triage menu should not let the two disagree.
8. **Cost and time.** A full draft takes 20 to 60 minutes and real money (`docs/plans/draft-ready-upgrade.html:118`). The "only key gates" approval mode lets several paid steps run unattended, so a budget or step cap is worth having.
9. **Sensitive material.** Solicitations from login-gated portals (Vulcan SOF, NSTXL member pages), and possibly CUI, would go to the Anthropic API and into Drive. AI vendor clearance (PRO-473) is still open (`docs/session-archives/active/INTEGRATION_MEMORY.md:36`). The repo is public, so generated files, logs and test fixtures must stay out of it.
10. **Slack threads exist only for carded calls,** so step updates for a call with no card need a card posted first (question 4).
11. **Dates are portal text.** Deadlines are stored as each portal wrote them (`001_initial.sql:29`). Reminders and expected-by dates need parsed dates. The dashboard shows times in America/Denver unless Profile settings change it (spec U5).
12. **AGENTS.md is out of date.** It says the ledger is SQLite (`AGENTS.md:11`); production is Postgres, and the dashboard reads Postgres only.
13. **A skill copy looks cut off.** The opportunity-assessment skill's synced copy stops at its submission checklist heading (question 10).

**Missing from the design:** the spec (`docs/design/dashboard-design-spec.md`) is behind it.
- The spec has tabs (N2) where the design has view cards.
- The spec has a Pursuing tab with Ready to draft and Drafting sections (P5 to P8) where the design has a full workspace.
- The spec lists recording won or lost as not built.
- The spec has no rules for badges on every row, starting a draft from any row, the expected-by date or the "no news yet" reminder.

The build prompts and `tests/test_design_brief.py` key off the spec's requirement IDs, so these need writing into the spec first.
