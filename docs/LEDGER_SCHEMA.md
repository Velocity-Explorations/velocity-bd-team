# Ledger schema

The ledger is the one contract between components. Nothing talks HTTP to anything else;
every component reads and writes these tables through `ledger/queries.py`, and the
dashboard reads them directly. This document is complete enough to build against on its
own.

Current migration: `002_change_requests.sql`. The full current schema is in `ledger/schema.sql`.

## Conventions

- Database: PostgreSQL in production (DATABASE_URL in `.env`), SQLite for local work and
  tests (`DATABASE_URL=sqlite:///data/dev.db`). The SQL is portable: TEXT, INTEGER, REAL
  only. JSON is stored as TEXT. There are no Postgres-only types.
- Every timestamp column is ISO-8601 UTC text with second precision, for example
  `2026-10-15T14:03:09Z`. Compare and sort them as strings. Date-only columns
  (`posted_date`, `due_date`, `submitted_date`, `outcome_date`) are `YYYY-MM-DD` text as
  the portal supplied them, or NULL.
- Booleans are INTEGER 0/1.
- Placeholders: `ledger/queries.py` writes `?` and `ledger/db.py` rewrites to `%s` for
  Postgres. Raw SQL against Postgres uses `%s` (psycopg) or `$1` (psql).
- Schema changes are additive only and arrive as new numbered files in
  `ledger/migrations/`. This document changes in the same commit.
- Only the Coordinator changes the schema. Portal-specific data goes in `calls.extra`
  as JSON with a key prefix (for example `vulcan_`), never in a new column.

## Table: runs

One row per execution of a component. Written by the component itself through
`start_run` and `finish_run`. Read by the Coordinator and the dashboard.

| Column | Type | Values | Written by |
|---|---|---|---|
| id | INTEGER, primary key, auto-increment | | database |
| component | TEXT, not null | `vulcan_sof`, `review`, `library`, `pipeline`, or any later component slug | the component, at start |
| portal | TEXT | portal slug when the run is portal-scoped, else NULL | the component, at start |
| started_at | TEXT timestamp, not null | | the component, at start |
| finished_at | TEXT timestamp | NULL while running | the component, at finish |
| status | TEXT, not null | `running`, `completed`, `skipped_timeout`, `error` | start sets `running`; finish sets the rest |
| stage_counts | TEXT JSON | object such as `{"fetched":12,"filtered":5,"reviewed":5,"new":2}` | the component, at finish |
| error | TEXT | traceback or message when status is `error` | the component, at finish |
| log_path | TEXT | path to the run log under `data/<component>/` | the component, at finish |
| dry_run | INTEGER, not null, default 0 | 1 when the run wrote nothing downstream | the component, at start |

## Table: calls

One row per opportunity ("call") ever seen on any portal. The primary key is stable
across runs so re-scraping updates rather than duplicates. Columns fall into groups by
the component that owns them. A component never writes another group's columns.

| Column | Type | Values | Written by |
|---|---|---|---|
| id | TEXT, primary key | `<portal-prefix>-<stable id>`, for example `vulcan-<collectionUuid>` | portal adapter (insert only) |
| portal | TEXT, not null | portal slug, for example `vulcan_sof` | portal adapter |
| title | TEXT | | portal adapter |
| type | TEXT | the portal's opportunity type as shown (RFI, BAA, CSO, and so on) | portal adapter |
| department | TEXT | issuing office or command | portal adapter |
| naics_code | TEXT | NAICS code if the portal lists one | portal adapter |
| set_aside | TEXT | set-aside designation if listed | portal adapter |
| posted_date | TEXT | when the call opened, as the portal writes it: `YYYY-MM-DD`, or Vulcan's `04 Oct 2026 : 22:00 MDT` | portal adapter |
| due_date | TEXT | the deadline as the portal writes it: `YYYY-MM-DD`, or Vulcan's `30 OCT 2026 : 21:59 MDT`; `assistant/dates.py` reads both | portal adapter |
| description | TEXT | full text as scraped | portal adapter |
| url | TEXT | link back to the portal detail page | portal adapter |
| source_type | TEXT | how it was obtained, for example `scrape`, `rss`, `manual` | portal adapter |
| first_seen_at | TEXT timestamp, not null | set once on insert | `upsert_call` |
| last_seen_at | TEXT timestamp, not null | refreshed every time the call is scraped | `upsert_call` |
| first_run_id | INTEGER | `runs.id` of the run that first saw it | `upsert_call` |
| last_run_id | INTEGER | `runs.id` of the latest run that saw it | `upsert_call` |
| filter_result | TEXT, not null, default `pending` | `pending`, `kept`, `rejected` | filter stage (`set_filter`) |
| filter_reason | TEXT | why rejected (or why kept) | filter stage |
| match_tier | TEXT | which keyword tier matched, as the filter defines it | filter stage |
| matched_keywords | TEXT JSON | array of strings | filter stage |
| ai_verdict | TEXT | NULL, `yes`, `no`, `maybe` | Reviewer (`set_review`) |
| ai_reasoning | TEXT | the model's reasoning | Reviewer |
| reviewed_at | TEXT timestamp | | Reviewer |
| slack_channel | TEXT | channel id the card was posted to | Slack delivery (`set_slack`) |
| slack_ts | TEXT | Slack message timestamp (its id) | Slack delivery |
| posted_at | TEXT timestamp | | Slack delivery |
| human_status | TEXT | NULL, `pursue`, `not_relevant`, `submitted`, `dismissed` | the dashboard's decide action (`set_human` from Python); Slack reactions set it before 2026-10-17 |
| human_by | TEXT | the deciding person's name; a Slack user id on calls decided by reaction before 2026-10-17 | same |
| human_at | TEXT timestamp | when they decided | same |
| human_notes | TEXT | newline-separated lines `[<timestamp> <by>] <text>` | `append_note`, Slack thread replies, the dashboard's decide action |
| extra | TEXT JSON | object of portal-specific fields, keys prefixed by portal. Vulcan SOF writes `vulcan_closed` (bool, the page says the call has closed) and `vulcan_description_fallback` (bool, no Problem Statement text was found). Page fields any portal may store, found by suffix: `<prefix>_objectives`, `_documents`, `_files_required`, `_tags` (lists) and `_instructions` (text); Vulcan SOF writes all five | portal adapter |
| updated_at | TEXT timestamp, not null | touched by every write | every writer |

Indexes: `(portal, first_seen_at)`, `(human_status)`, `(ai_verdict)`.

Lifecycle of a row: portal adapter inserts it (`filter_result = 'pending'`); the filter
sets `kept` or `rejected`; the Reviewer sets `ai_verdict` on kept rows; Slack delivery
posts rows with verdict `yes` or `maybe` and records `slack_ts`; a person decides on the
dashboard and `human_status` is set. Later runs refresh only the scraped
fields and `last_seen_at`. An approved keyword change (see `change_requests`) filters every
stored call of its portal again, so `filter_result` can change on old rows.

## Table: proposals

One row per past submission, keyed by the Drive folder name. Filled by the library sync
(Proposal Library plan, Phase A); `brief` is generated later.

| Column | Type | Values | Written by |
|---|---|---|---|
| submission_id | TEXT, primary key | `YYYY-MM-DD_portal_short-title`, equal to the Drive folder name | library sync |
| title | TEXT | | library sync |
| portal | TEXT | portal or program slug (`sbir`, `vulcan_sof`, `sam`, and so on) | library sync |
| agency | TEXT | | library sync |
| solicitation_id | TEXT | the government's identifier | library sync |
| type | TEXT | response type (SBIR Phase I, white paper, BAA response, and so on) | library sync |
| role | TEXT | `prime`, `sub`, `team member` or similar | library sync |
| partners | TEXT | free text or JSON array | library sync |
| submitted_date | TEXT date | `YYYY-MM-DD` | library sync |
| due_date | TEXT date | `YYYY-MM-DD` | library sync |
| requested_value | TEXT | dollar amount as text | library sync |
| outcome | TEXT | NULL, `won`, `lost`, `no_award`, `pending`, `withdrawn`, `shortlisted` | library sync |
| outcome_date | TEXT date | | library sync |
| award_value | TEXT | dollar amount as text | library sync |
| strength_rating | INTEGER | 1 to 5, or NULL | library sync (hand-entered) |
| strength_reason | TEXT | | library sync |
| why_won_or_lost | TEXT | | library sync |
| use_as_exemplar | INTEGER, not null, default 0 | 1 when the Writer may quote it | library sync |
| themes | TEXT JSON | array of strings | library sync |
| drive_link | TEXT | URL of the Drive folder | library sync |
| brief | TEXT | one-paragraph summary | library brief generator |
| synced_at | TEXT timestamp | last sync from the register | library sync |
| updated_at | TEXT timestamp, not null | | every writer |

Index: `(portal, outcome)`.

## Table: change_requests

The portal assistant's approval queue (docs/ASSISTANT.md, "Approvals"). A propose tool
records what it wants changed and a preview of the effect; a person approves or rejects it
on the dashboard; `run.py --apply-requests` carries out approved requests. Added by
`002_change_requests.sql`.

| Column | Type | Values | Written by |
|---|---|---|---|
| id | INTEGER, primary key, auto-increment | the number people see, as in "request #12" | database |
| kind | TEXT, not null | `keyword_change`, `rereview`, `scan`, `draft`, `fault_report` | propose tool (`create_request`) |
| portal | TEXT | portal slug the request concerns, for example `vulcan_sof` | propose tool |
| call_id | TEXT | `calls.id`, for `rereview` and `draft` | propose tool |
| summary | TEXT, not null | one line in words, for example `Vulcan SOF keywords: add broad keyword 'digital twin'` | propose tool |
| reason | TEXT | why the person asked, in their words | propose tool |
| payload | TEXT JSON | what to do: `{"changes": {...}}` for a keyword change, with the lists `add_broad`, `remove_broad`, `add_tight`, `remove_tight`, `add_block`, `remove_block`; `{"context": "..."}` for a re-review; `{"notes": "..."}` for a draft; `{"title": "...", "body": "..."}` for a fault report; `{}` for a scan | propose tool |
| preview | TEXT JSON | object with at least `text`: what approving would do, shown on the dashboard | propose tool |
| status | TEXT, not null, default `proposed` | `proposed`, `approved`, `rejected`, `applying`, `applied`, `failed` | see the lifecycle below |
| requested_by | TEXT, not null | who asked: a person's name, or `command line`; set by the code running the tool, never by the model | propose tool |
| requested_at | TEXT timestamp, not null | | propose tool |
| decided_by | TEXT | the name of the person who approved or rejected it | the dashboard's Requests page (`decide_request` from Python) |
| decided_at | TEXT timestamp | | same |
| decision_note | TEXT | optional note given with the decision | same |
| applied_at | TEXT timestamp | when it was carried out | `run.py --apply-requests` (`finish_request`) |
| result | TEXT | what happened, or `Waiting: ...` while an approved request cannot run yet | `run.py --apply-requests`; the Writer, for drafts |
| updated_at | TEXT timestamp, not null | touched by every write | every writer |

Index: `(status, id)`.

Lifecycle of a row: a propose tool inserts it as `proposed`. A person approves it
(`approved`) or rejects it (`rejected`) on the dashboard; that update is guarded on
`status = 'proposed'`, so a request is decided once. `run.py --apply-requests` claims an
approved row (`applying`, guarded on `status = 'approved'`), carries it out, and sets
`applied` or `failed` with `result`. An approved request that cannot run yet (the scan
machine is not on `main`, the repo has no GitHub remote) stays `approved`, and `result`
says what it waits for. A row left `applying` by a job that stopped is marked `failed` on
the next pass. Drafts stay `approved` for the Writer, which claims and finishes them the
same way.

## Table: judgments

How each judge rated each call, so the judges can be compared (docs/DASHBOARD.md shows both).
The Claude review still writes `calls.ai_verdict`, the verdict that decides what is posted; it
also writes a row here, and Grok, the second judge, writes its own when `BD_XAI_API_KEY` is set.
Added by `003_judgments.sql`.

| Column | Type | Values | Written by |
|---|---|---|---|
| id | INTEGER, primary key, auto-increment | | database |
| call_id | TEXT, not null | `calls.id` | the review (`review_calls`), the second judge (`judge_calls`), `run.py --backfill-judgments` |
| judge | TEXT, not null | `claude` or `grok` | same |
| model | TEXT, not null | the model that answered, for example `claude-haiku-5-5` or `grok-4.7` | same |
| verdict | TEXT, not null | `yes`, `maybe`, `no` | same |
| reasoning | TEXT | the judge's one-sentence reason | same |
| rated_at | TEXT timestamp, not null | when it judged; for backfilled Claude rows, the call's `reviewed_at` | same |

Index: `(call_id, judge, id)`. A newer row for the same call and judge supersedes the older
one (a re-review writes a new row); older rows stay as history. A review error is not a
judgment and writes no row.

## Table: schema_migrations

Bookkeeping for `ledger/migrate.py`. `version` is the migration filename, `applied_at`
the timestamp. Nothing else reads it.

## How to build a dashboard against this

`dashboard/` is the working example (see DASHBOARD.md). Connect with DATABASE_URL and read the
tables directly; no API exists or is planned.
Treat the ledger as read-only from the dashboard except for the `human_*` columns on
`calls`, which the dashboard sets with its decide action (the equivalent of `set_human`
and `append_note`), and the decision columns of `change_requests` (`status` from
`proposed` to `approved` or `rejected`, `decided_by`, `decided_at`, `decision_note`), which
its Requests page sets (the equivalent of `decide_request`). Since 2026-10-17 the dashboard is the only place decisions are made;
Slack reactions are no longer read. Use the `runs` table for health: the latest row per component tells you
when it last ran and whether it finished.

Timestamps are text, so "this week" is a text comparison against a cutoff the caller
computes. The queries below use `?` placeholders; substitute `%s` or `$1` for raw
Postgres. Each one is executed by `tests/test_schema_doc.py` so the document cannot
drift from the schema.

### New calls this week

Parameter: the ISO timestamp seven days ago, for example `2026-10-08T00:00:00Z`.

```sql
SELECT id, portal, title, type, due_date, ai_verdict, human_status, first_seen_at
FROM calls
WHERE first_seen_at >= ?
ORDER BY first_seen_at DESC, id;
```

### Triage backlog

Calls the Reviewer rated yes or maybe that nobody has decided on yet, soonest due first.
A call that a later keyword change dropped keeps its verdict but leaves the backlog, which
is why the query also asks for `filter_result = 'kept'`.

```sql
SELECT id, portal, title, due_date, ai_verdict, posted_at
FROM calls
WHERE ai_verdict IN ('yes', 'maybe')
  AND human_status IS NULL
  AND filter_result = 'kept'
ORDER BY due_date, first_seen_at;
```

### Win rate by portal

Counts only decided outcomes (`won` or `lost`); pending, withdrawn, no_award and
shortlisted are excluded from the denominator.

```sql
SELECT portal,
       SUM(CASE WHEN outcome = 'won' THEN 1 ELSE 0 END) AS won,
       SUM(CASE WHEN outcome IN ('won', 'lost') THEN 1 ELSE 0 END) AS decided,
       ROUND(100.0 * SUM(CASE WHEN outcome = 'won' THEN 1 ELSE 0 END)
             / NULLIF(SUM(CASE WHEN outcome IN ('won', 'lost') THEN 1 ELSE 0 END), 0), 1) AS win_rate_pct
FROM proposals
GROUP BY portal
ORDER BY decided DESC, portal;
```

### Judge agreement

Of the calls both judges rated, how many verdicts match, using each judge's newest verdict.

```sql
SELECT COUNT(*) AS both_judged,
       SUM(CASE WHEN c.verdict = g.verdict THEN 1 ELSE 0 END) AS agree
FROM judgments AS c
JOIN judgments AS g ON g.call_id = c.call_id AND g.judge = 'grok'
WHERE c.judge = 'claude'
  AND c.id = (SELECT MAX(id) FROM judgments WHERE call_id = c.call_id AND judge = 'claude')
  AND g.id = (SELECT MAX(id) FROM judgments WHERE call_id = g.call_id AND judge = 'grok');
```
