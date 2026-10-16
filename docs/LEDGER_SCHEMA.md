# Ledger schema

The ledger is the one contract between components. Nothing talks HTTP to anything else;
every component reads and writes these tables through `ledger/queries.py`, and the
dashboard reads them directly. This document is complete enough to build against on its
own.

Current migration: `001_initial.sql`. The full current schema is in `ledger/schema.sql`.

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
| component | TEXT, not null | `vulcan_sof`, `review`, `corpus`, `pipeline`, or any later component slug | the component, at start |
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
| posted_date | TEXT date | `YYYY-MM-DD` | portal adapter |
| due_date | TEXT date | `YYYY-MM-DD` | portal adapter |
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
| human_status | TEXT | NULL, `pursue`, `not_relevant`, `submitted`, `dismissed` | Slack feedback or dashboard (`set_human`) |
| human_by | TEXT | who decided (Slack user id or name) | same |
| human_at | TEXT timestamp | when they decided | same |
| human_notes | TEXT | newline-separated lines `[<timestamp> <by>] <text>` | `append_note` |
| extra | TEXT JSON | object of portal-specific fields, keys prefixed by portal. Vulcan SOF writes `vulcan_closed` (bool, the page says the call has closed) and `vulcan_description_fallback` (bool, no Problem Statement text was found) | portal adapter |
| updated_at | TEXT timestamp, not null | touched by every write | every writer |

Indexes: `(portal, first_seen_at)`, `(human_status)`, `(ai_verdict)`.

Lifecycle of a row: portal adapter inserts it (`filter_result = 'pending'`); the filter
sets `kept` or `rejected`; the Reviewer sets `ai_verdict` on kept rows; Slack delivery
posts rows with verdict `yes` or `maybe` and records `slack_ts`; a person reacts or
uses the dashboard and `human_status` is set. Later runs refresh only the scraped
fields and `last_seen_at`.

## Table: proposals

One row per past submission, keyed by the Drive folder name. Filled by the corpus sync
(Proposal Corpus plan, Phase A); `brief` is generated later.

| Column | Type | Values | Written by |
|---|---|---|---|
| submission_id | TEXT, primary key | `YYYY-MM-DD_portal_short-title`, equal to the Drive folder name | corpus sync |
| title | TEXT | | corpus sync |
| portal | TEXT | portal or program slug (`sbir`, `vulcan_sof`, `sam`, and so on) | corpus sync |
| agency | TEXT | | corpus sync |
| solicitation_id | TEXT | the government's identifier | corpus sync |
| type | TEXT | response type (SBIR Phase I, white paper, BAA response, and so on) | corpus sync |
| role | TEXT | `prime`, `sub`, `team member` or similar | corpus sync |
| partners | TEXT | free text or JSON array | corpus sync |
| submitted_date | TEXT date | `YYYY-MM-DD` | corpus sync |
| due_date | TEXT date | `YYYY-MM-DD` | corpus sync |
| requested_value | TEXT | dollar amount as text | corpus sync |
| outcome | TEXT | NULL, `won`, `lost`, `no_award`, `pending`, `withdrawn`, `shortlisted` | corpus sync |
| outcome_date | TEXT date | | corpus sync |
| award_value | TEXT | dollar amount as text | corpus sync |
| strength_rating | INTEGER | 1 to 5, or NULL | corpus sync (hand-entered) |
| strength_reason | TEXT | | corpus sync |
| why_won_or_lost | TEXT | | corpus sync |
| use_as_exemplar | INTEGER, not null, default 0 | 1 when the Writer may quote it | corpus sync |
| themes | TEXT JSON | array of strings | corpus sync |
| drive_link | TEXT | URL of the Drive folder | corpus sync |
| brief | TEXT | one-paragraph summary | corpus brief generator |
| synced_at | TEXT timestamp | last sync from the register | corpus sync |
| updated_at | TEXT timestamp, not null | | every writer |

Index: `(portal, outcome)`.

## Table: schema_migrations

Bookkeeping for `ledger/migrate.py`. `version` is the migration filename, `applied_at`
the timestamp. Nothing else reads it.

## How to build a dashboard against this

Connect with DATABASE_URL and read the tables directly; no API exists or is planned.
Treat the ledger as read-only from the dashboard except for the `human_*` columns on
`calls`, which the dashboard may set through `set_human` and `append_note` (or the
equivalent UPDATE) so decisions made on the dashboard flow back the same way Slack
reactions do. Use the `runs` table for health: the latest row per component tells you
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

```sql
SELECT id, portal, title, due_date, ai_verdict, posted_at
FROM calls
WHERE ai_verdict IN ('yes', 'maybe')
  AND human_status IS NULL
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
