# Ledger schema

The ledger is the one contract between components. Nothing talks HTTP to anything else;
every component reads and writes these tables through `ledger/queries.py`, and the
dashboard reads them directly. This document is complete enough to build against on its
own.

Current migration: `008_pursuits.sql`. The full current schema is in `ledger/schema.sql`.

## Conventions

- Database: PostgreSQL in production (DATABASE_URL in `.env`), SQLite for local work and
  tests (`DATABASE_URL=sqlite:///data/dev.db`). The SQL is portable: TEXT, INTEGER, REAL
  only. JSON is stored as TEXT. There are no Postgres-only types.
- Every timestamp column is ISO-8601 UTC text with second precision, for example
  `2026-10-15T14:03:09Z`. Compare and sort them as strings. Date-only columns
  (`posted_date`, `due_date`, `submitted_date`, `outcome_date`) are `YYYY-MM-DD` text as
  the portal supplied them, or NULL. The workspace's date-only columns
  (`pursuits.result_expected_by`, `checklist_items.due_date`) are `YYYY-MM-DD` text too.
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
| type | TEXT | the portal's opportunity type as shown (RFI, BAA, CSO, and so on). SSC Front Door reads it from the title; the review rates `Industry day`, `Webinar`, `Conference` and `Event` listings as events, on their topic. SAM.gov writes `Solicitation` (combined synopses too), `Presolicitation`, `Sources sought` or `Special notice` | portal adapter |
| department | TEXT | issuing office or command | portal adapter |
| naics_code | TEXT | NAICS code if the portal lists one | portal adapter |
| set_aside | TEXT | set-aside designation if listed | portal adapter |
| posted_date | TEXT | when the call opened, as the portal writes it: `YYYY-MM-DD`, or Vulcan's `04 Oct 2026 : 22:00 MDT` | portal adapter |
| due_date | TEXT | the deadline as the portal writes it: `YYYY-MM-DD`, or Vulcan's `30 OCT 2026 : 21:59 MDT`; `assistant/dates.py` reads both. SSC Front Door writes the event's end in that form, in the event's own zone, for example `28 OCT 2026 : 15:00 GMT`. SAM.gov writes its response deadline as ISO 8601 with the offset, for example `2026-11-05T17:00:00-05:00`, which `assistant/dates.py` and the dashboard also read | portal adapter |
| description | TEXT | full text as scraped | portal adapter |
| url | TEXT | link back to the portal detail page | portal adapter |
| source_type | TEXT | how it was obtained, for example `scrape`, `api` (SAM.gov), `rss`, `manual` | portal adapter |
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
| extra | TEXT JSON | object of portal-specific fields, keys prefixed by portal. Vulcan SOF writes `vulcan_closed` (bool, the page says the call has closed) and `vulcan_description_fallback` (bool, no Problem Statement text was found). SSC Front Door writes `sscfd_closed` (bool, the end date has passed), `sscfd_content_key`, `sscfd_start` and `sscfd_end` (UTC), `sscfd_time_zone`, `sscfd_location`, `sscfd_event_url`, `sscfd_registration`, `sscfd_audience`, and for notices reposted from SAM.gov `sscfd_sam_notice_id` and `sscfd_sam_url`. SAM.gov writes `samgov_closed` (bool, the deadline has passed or the notice is no longer active), `samgov_notice_id`, `samgov_solicitation_number`, `samgov_type` and `samgov_base_type` (SAM.gov's own type names), `samgov_set_aside_code`, `samgov_classification_code`, `samgov_naics_codes`, `samgov_place_of_performance`, `samgov_contacts` (list of name, email, phone, role), `samgov_attachments` (download links, not fetched) and `samgov_additional_info`. A notice reposted on Front Door is stored once, by whichever adapter sees it first. NSTXL writes `nstxl_closed` (bool, not open or the deadline has passed), `nstxl_post_id`, `nstxl_consortium`, `nstxl_statuses` (NSTXL's status names), `nstxl_modified`, `nstxl_deadline_text` (the sentence the deadline was read from), `nstxl_members_only` (bool, the public page is NSTXL's member-only notice) and `nstxl_no_deadline`. DIU writes `diu_closed` (bool, the close time has passed), `diu_number` (its PROJ number), `diu_project_type` (DIU's own, for example "2371b OT - CSO"), `diu_contracting_shop` and `diu_close` (DIU's wording of the close time). AFWERX writes `afwerx_closed` (bool, the close date has passed in Eastern time), `afwerx_branches` (the services whose topics the cycle includes, from AFWERX's AF and SF badges), `afwerx_pre_release` and `afwerx_open` (ISO dates, or null when AFWERX gives none) and `afwerx_no_deadline`. SpaceWERX writes the same five keys with the `spacewerx_` prefix (its page shares AFWERX's template). DOE SBIR writes `doe_closed` (bool, the hub's category is Closed or the deadline has passed), `doe_post_id`, `doe_status` (Active, Upcoming or Closed), `doe_modified`, `doe_deadline_text` (the words the deadline was read from) and `doe_no_deadline`. NASA Forecast writes `nasa_closed` (bool, the row is awarded, withdrawn or cancelled), `nasa_source_id`, `nasa_status` and `nasa_phase` (NASA's AcquisitionStatus and AcquisitionPhase), `nasa_solicitation_expected` and `nasa_award_expected` (for example "Q3 FY2026", or "FY2026" while NASA has not set the quarter), `nasa_estimated_value`, `nasa_requirement`, `nasa_contacts` (list of name, email, role) and `nasa_no_deadline` (always true). Space Florida writes `spacefl_closed` (bool, past the due date in Eastern time, or a notice of intent to award posted), `spacefl_documents` (the documents' names), `spacefl_document_links` (list of name, url), `spacefl_notes`, `spacefl_intent_to_award` and `spacefl_no_deadline`. APFIT writes `apfit_closed` (bool, the cycle's status says final selection, evaluation, closed or awarded), `apfit_cycle` (for example FY27-2), `apfit_post_id`, `apfit_status` (the post's words) and `apfit_no_deadline` (always true). Page fields any portal may store, found by suffix: `<prefix>_objectives`, `_documents`, `_files_required`, `_tags` (lists) and `_instructions` (text); Vulcan SOF writes all five. A row with `<prefix>_no_deadline` true has no deadline to read by design (for NSTXL: a coming-soon or member-only notice, or a post whose deadline is only in its documents; for AFWERX and SpaceWERX: a listing whose close date is TBD or N/A, or that takes submissions on a continuous basis; for DOE SBIR: an upcoming solicitation with no date yet, or TBD; for NASA Forecast: every row, since a forecast has no deadline; for Space Florida: a listing the page shows without a due date; for APFIT: every cycle, since each organization sets its own deadline), so the scan quality alert does not count its empty `due_date` | portal adapter |
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

## Table: decisions

Every triage decision, kept per person, so several people can decide on the same call and the
judges can be scored against each of them. `calls.human_status`, `human_by` and `human_at` stay
the team's current decision: the newest decision that changed it. Added by `004_decisions.sql`,
which also copied in every decision made before it (one row per decided call, with `human_by`
and `human_at`).

| Column | Type | Values | Written by |
|---|---|---|---|
| id | INTEGER, primary key, auto-increment | | database |
| call_id | TEXT, not null | `calls.id` | the dashboard's decide action, `set_human` |
| decided_by | TEXT, not null | the person's name from `DASHBOARD_USERS`; a Slack user id for decisions made in Slack before 2026-10-17 | same |
| status | TEXT, not null | `pursue`, `not_relevant`, `submitted`, `dismissed` | same |
| note | TEXT | the note given with the decision, also appended to `calls.human_notes` | same |
| decided_at | TEXT timestamp, not null | when the person decided | same |

Index: `(call_id, id)`. Rows are only added. A person who changes their mind adds a row; their
newest row is their decision. A row that does not change the call's decision (agreeing with
it, or any decision after the first made from the review queue while everyone decides every
call) leaves `calls` as it is.

## Table: briefs

The Monday brief, kept per week, so the dashboard shows the same week the Monday Slack
summary posted. Written by `run.py --post-summary`, and by `run.py --write-brief`, which posts
nothing. Added by `005_briefs.sql`.

| Column | Type | Values | Written by |
|---|---|---|---|
| id | INTEGER, primary key, auto-increment | | database |
| week_of | TEXT date, not null | `YYYY-MM-DD`, the Monday of the week | `save_brief` |
| portal | TEXT | `calls.portal` for one portal's week; NULL for the Top 10 across portals | same |
| body | TEXT JSON, not null | one portal's `weekly_summary()` plus `health`, its scraper line; or, with no portal, `top` (the Top 10 as call references), `ranked_by` and `judges` (`judge_records()`) | same |
| written_by | TEXT, not null | `pipeline`; a portal's bot may write its own later | same |
| created_at | TEXT timestamp, not null | | same |

Index: `(week_of, id)`. Writing a week's part again replaces that part, so a rerun never
duplicates it. The dashboard only reads this table.

## Table: call_tags

Tags from the set list in `review/tags.yaml` on each call: exactly one type, and any work,
customer and access tags that apply. Kept per source, so the dashboard can show who tagged
what. Added by `006_call_tags.sql` (PRO-556).

| Column | Type | Values | Written by |
|---|---|---|---|
| id | INTEGER, primary key, auto-increment | | database |
| call_id | TEXT, not null | `calls.id` | `set_tags`: the pipeline's rules (`tag_by_rules`), the review and second judge, `run.py --backfill-tags` |
| tag | TEXT, not null | a tag name from `review/tags.yaml` | same |
| source | TEXT, not null | `rule` (the call's own data makes it certain), `claude` or `grok` (the judge picked it) | same |
| tagged_at | TEXT timestamp, not null | when that source last tagged the call | same |

Unique: `(call_id, tag, source)`. Index: `(tag)`. Setting a source's tags on a call replaces
that source's rows and leaves the others. Rules tag every call a run sees, so their tags follow
the data; a judge's tags change only when it answers again, and an answer without tags changes
nothing. A tag renamed in `review/tags.yaml` stays under its old name until the call is tagged
again.

## Table: tag_list

The tag list from `review/tags.yaml`, so the dashboard can group and order each call's tags and
offer every tag in its filter without reading the pipeline's files. The pipeline rewrites it
whenever it tags (`tag_by_rules` on each run, `run.py --backfill-tags`). Added by
`007_tag_list.sql` (PRO-557).

| Column | Type | Values | Written by |
|---|---|---|---|
| name | TEXT, primary key | the tag | `save_tag_list` |
| tag_group | TEXT, not null | `type`, `work`, `customer`, `access` | same |
| covers | TEXT | what the tag covers, as the judges read it | same |
| position | INTEGER, not null | the tag's place in the list, from 0 | same |

A tag in `call_tags` with no row here was renamed or dropped from the list; the dashboard shows
it last.

## Table: pursuits

One row per call being drafted in the proposal workspace (spec P2 to P8 and PW1 to PW25;
docs/design/redesign-plan.md). The Register's past submissions stay in `proposals`; a pursuit
points at its Register row through `submission_id` once the submission is written there. Added
by `008_pursuits.sql` (PRO-568), with the other workspace tables below. Start the draft on the
dashboard writes a pursuit (PRO-576), and the Writer's worker (`python -m drafting.worker`,
PRO-577) runs its steps through the helpers in `ledger/queries.py`; the workspace page and the
Slack jobs arrive in later phases of the plan. The worker's record of what it did is these tables
and its heartbeat in `workers`, not `runs`.

| Column | Type | Values | Written by |
|---|---|---|---|
| id | INTEGER, primary key, auto-increment | | database |
| call_id | TEXT, not null | `calls.id`; unique, so a call is pursued once | Start the draft (`start_pursuit`) |
| owner | TEXT, not null | the `DASHBOARD_USERS` name of the person who started it; only they approve and decide (PW17) | same |
| collaborators | TEXT JSON | list of `DASHBOARD_USERS` names working with the owner (PW24), or NULL | Start the draft; People in the workspace header (the owner only) |
| format | TEXT | what is being written, in words, for example `white paper`, `RFI response`, `SBIR or STTR technical volume` | Start the draft |
| approval_mode | TEXT, not null, default `every_step` | `every_step`, or `key_gates`: the owner approves only Go or no-go, Outline and Submit (PW5) | same |
| direction | TEXT | the owner's direction; after Alignment, the one that carries forward (PW8). Locked once the Outline is approved | Start the draft, Alignment |
| builds_on | TEXT JSON | list of past work to build on, each `{"id": <drive_items.id>, "name": ...}`; locked once the Outline is approved (PW11) | Start the draft; the owner and the people working with them |
| drive_folder_id | TEXT | the pursuit's folder on the shared drive, `Submissions/<YYYY-MM-DD_portal_short-title>/` | the worker, after Start |
| drive_folder_name | TEXT | that folder's path, as the header shows it | same |
| current_step | TEXT, not null | the step the pursuit is on: the step of its newest attempt in `pursuit_steps` | every helper that queues an attempt |
| state | TEXT, not null, default `working` | `working`; `no_go` (stopped by a no-go); `submitted` (Mark submitted: waiting for the result, then holding it in `result`); `closed` (closed without a no-go) | see the lifecycle below |
| target_dates | TEXT JSON | object of step name to `YYYY-MM-DD` target, plus `submit_by`, the internal submit-by date one business day before the deadline (PW9, PW18) | the worker, at Requirements and checklist |
| cost_usd | REAL, not null, default 0 | what the pursuit's steps have cost so far, in US dollars | the worker (`finish_step`, `fail_step`, `stop_step`) |
| budget_usd | REAL, not null, default 200 | the spending cap (PW19); the owner can raise it | Start the draft; Raise the cap |
| submitted_at | TEXT timestamp | when Mark submitted was chosen | the Submit gate |
| submitted_by | TEXT | who chose it | same |
| confirmation_number | TEXT | the portal's confirmation number | same |
| result_expected_by | TEXT date | `YYYY-MM-DD`, when the result is expected (P4); No news yet moves it 30 days on | Discovery, the Submit gate, No news yet |
| result_expected_source | TEXT | where that date came from: the call's words and where they were found, or `default, 90 days after the deadline` | same |
| result | TEXT | `won`, `lost`, `withdrawn`, `cancelled_by_agency`, or NULL until recorded | Record result |
| result_at | TEXT timestamp | when the result was recorded | same |
| result_by | TEXT | who recorded it | same |
| debrief | TEXT | the optional debrief note | same |
| next_time | TEXT | the optional What to do differently next time, which the next alignment check reads | same |
| submission_id | TEXT | `proposals.submission_id` once the Register row is written | the Register write on submit |
| created_at | TEXT timestamp, not null | when the draft was started | Start the draft |
| updated_at | TEXT timestamp, not null | touched by every write | every writer |

Unique index: `(call_id)`. Start the draft is refused, with the reason, for a call that has a
pursuit already or is marked Not relevant. The result keeps the workspace's own values; when the
Register row is written, `cancelled_by_agency` becomes `no_award`, since `proposals.outcome`
cannot take a new value without a non-additive change.

Lifecycle: a pursuit starts `working`. A no-go on steps 1 to 4 or at the gate makes it `no_go`;
Mark submitted makes it `submitted`, and recording the result leaves it `submitted` with `result`
set; the owner can close a working pursuit (`closed`). Each change is guarded on
`state = 'working'`, and the worker only runs steps of a `working` pursuit.

## Table: pursuit_steps

One row per attempt at a workspace step. Asking for changes or retrying adds a new attempt and
leaves the old row as history; the newest attempt at each step is the one the page shows
(`latest_steps`). Added by `008_pursuits.sql`.

The steps, in order (PW3): `discovery` (Discovery), `summary` (Opportunity summary), `alignment`
(Alignment), `requirements` (Requirements and checklist), `go_no_go` (the Go or no-go gate),
`outline` (Outline), `draft` (First draft), `compliance` (Compliance check), `reviews` (Reviews),
`final` (Final checks), `submit` (the Submit gate). `step` is free text checked against `STEPS` in
`ledger/queries.py`, so the list can change without a constraint change.

| Column | Type | Values | Written by |
|---|---|---|---|
| id | INTEGER, primary key, auto-increment | | database |
| pursuit_id | INTEGER, not null | `pursuits.id` | whoever queues the attempt |
| step | TEXT, not null | one of the steps above | same |
| attempt | INTEGER, not null, default 1 | 1, then one more for each redo or retry | same |
| state | TEXT, not null, default `queued` | `queued`, `working`, `ready`, `approved`, `changes_asked`, `failed`, `blocked`, `stopped`, `skipped` | see the lifecycle below |
| requested_by | TEXT, not null | who queued it: the person who started, approved, asked for changes or retried, or `worker (key gates only)` | same |
| request_note | TEXT | what to change, on an attempt queued by Ask for changes; the worker puts it in its prompt | Ask for changes (`ask_changes`) |
| summary | TEXT | the key points shown on the step (PW4) | the worker (`finish_step`) |
| files | TEXT JSON | list of the files saved to Drive, each with `name`, `id` (the Drive file id) and `link`; until Drive (phase 6b), `name`, `local` (the Markdown's path under `data/drafting/pursuits/`) and `word` (its Word file's, PRO-579) | same |
| content | TEXT JSON | what the step shows beyond its summary, per step. Every step: `document` (its Markdown) and `question` (the owner's question on the card, PW4). Discovery: `tasks` (as in `task_states`), `owner_fetch` (pages and files for the owner to fetch) and `result_expected` (`date`, `source`). Opportunity summary: `worth_it` (`yes`, `no`, `unsure`). Alignment: `verdict`, `angle`, `comparison`, `direction`, `points` (each `tag`: `fits`, `past work`, `depends`, `risk`, `needs` or `no clash`; `text`; `source`). Requirements and checklist: `checklist_items`, `submit_by`, `milestones`, `requirements` (`volumes`, `page_limit`, `evaluation`, `eligibility`, `keywords`, a line each), `format` (the Word files' `font`, `size` in points, `margins` in inches and line `spacing`) and `format_source` (`the call` or `plain defaults`). Go or no-go: `fit` (Strong, Moderate, Stretch or Poor fit), `fit_reason`, `win_themes`, `gaps` (each `gap` and `mitigation`), `effort`, `recommendation` (`go`, `go_with_conditions`, `no_go`), `recommendation_text`, `conditions`. Outline: `sections` (each `title`, `criteria`, `share`, `evidence`), `page_limit`, `unmapped_criteria`, `evidence`, `direction`. First draft: `words`, `placeholders` (by kind), `slop` (the AI slop check's verdict on Draft v1). Compliance check: `corrections`, `warnings`, `slop` (on Draft v2). Reviews: `passes` (each `pass`, `code` and `reviewer`, `status`, the evaluators' `ratings` (each `criterion`, `rating` in words, `strengths`, `weaknesses`; PW25), `changes` proposed, `dropped` (changes whose text was not in the draft), `points`), and `changes`, the total; the changes themselves are `step_changes` rows. Final checks: `verdict`, `ready`, `band`, `open_placeholders`, `person_writes`, `dashes_fixed`, `changes_applied` and `changes_missed` (the decided changes put into Draft v3, and those whose text no longer matched). Submit gate: `checks` (each `check`, `ok` true, false or null when not known, `detail`), `files` (each `file` and its portal `slot`), `portal_steps`, `deadline`, `call_page` | same |
| task_states | TEXT JSON | Discovery's tasks and their states (PW6): `call_page`, `attachments`, `parent_instructions`, `key_facts`, `past_work`, `clashes`, `record` and `summary`, each `working` while the step runs, then `done` or `for_owner` (it needs a page, a login or a file the worker cannot reach) | the worker, while it works (`set_task_states`) |
| error | TEXT | why it failed, or what it waits for when blocked (`budget reached`), in words: the model's error, `The worker cannot run <step> yet.`, or `The worker stopped while it worked on this step. Retry runs it again.` for a step a stopped worker left working | the worker (`fail_step`, `block_step`) |
| cost_usd | REAL, not null, default 0 | what this attempt cost, in US dollars | the worker |
| decision | TEXT | `approved`, `go`, `go_with_conditions`, `changes_asked`, `no_go`, `retried`, `submitted` | the owner's actions; the worker with key gates only |
| decided_by | TEXT | who decided: the owner, or `worker (key gates only)` (PW5) | same |
| decided_at | TEXT timestamp | | same |
| decision_note | TEXT | the note given with the decision: the change asked for, the no-go reason, the conditions | same |
| notified_at | TEXT timestamp | when Slack said the step is ready, so it says so once (PW18) | the Slack job |
| queued_at | TEXT timestamp, not null | | whoever queues the attempt |
| started_at | TEXT timestamp | when the worker claimed it | the worker (`claim_next_step`) |
| finished_at | TEXT timestamp | when the worker saved, failed, blocked or stopped it | the worker |
| updated_at | TEXT timestamp, not null | touched by every write except `notified_at`, so a form carrying it goes stale only when the step changed | every writer |

Unique: `(pursuit_id, step, attempt)`. Index: `(state, id)`.

Lifecycle of a row:

- **Queued.** Start the draft queues `discovery`; approving a step queues the next one; Ask for
  changes and Retry queue the same step again as a new attempt. Each sets
  `pursuits.current_step`.
- **The worker.** It claims the oldest `queued` row of a `working` pursuit (`working`, guarded on
  `state = 'queued'`), then saves it (`ready`), or sets `failed` with `error`, or `blocked` when it
  cannot run until a person acts (budget reached, PW19). Saving is guarded on the pursuit still
  being `working`; when it stopped meanwhile, the worker sets the row `stopped` and records the cost.
- **The owner.** On a `ready` row the owner approves (`approved`; at the gate the decision is `go`
  or `go_with_conditions`), asks for changes (`changes_asked`, with the note), or, on steps 1 to 4
  and the gate, chooses no-go (`stopped` with decision `no_go`, and the pursuit becomes `no_go`).
  Each is guarded on `state = 'ready'` and the pursuit being `working`, and on `updated_at` when the
  form carried it (spec C8's pattern), so a stale form changes nothing. With key gates only, the
  worker approves every step except `go_no_go`, `outline` and `submit`, as
  `worker (key gates only)`.
- **Retry.** A `failed` or `blocked` row is retried once: its `decision` becomes `retried`
  (guarded on `decision IS NULL`) and a new attempt is queued.
- **Submit.** `submit` is not approved like a step: Mark submitted records it (decision
  `submitted`) and makes the pursuit `submitted`.
- **Closing.** Closing a pursuit stops its `queued`, `ready` and `blocked` rows; a `working` row is
  left to the worker, which stops it at its next phase boundary.
- **Skipped.** Kept for a step a format does not need; nothing sets it yet.

## Table: step_changes

The changes the review passes propose to a draft, one per row, each decided by the owner (PW12).
Added by `008_pursuits.sql`.

| Column | Type | Values | Written by |
|---|---|---|---|
| id | INTEGER, primary key, auto-increment | | database |
| step_id | INTEGER, not null | `pursuit_steps.id` of the Reviews attempt that proposed it | the worker (`add_step_changes`) |
| reviewer | TEXT, not null | `evaluator_1`, `evaluator_2` or `leadership`: the external evaluator, the second evaluator and the Velocity leadership pass | same |
| section | TEXT | where in the draft, for example the section heading | same |
| before_text | TEXT | the text now | same |
| after_text | TEXT | the suggestion | same |
| reason | TEXT | why | same |
| state | TEXT, not null, default `proposed` | `proposed`, `accepted`, `rejected`, `edited` | the owner on the dashboard (Accept, Reject, Edit, Accept all), guarded on `state = 'proposed'` and the Reviews attempt still `ready`; Undo sets a decided change back to `proposed` while Reviews is ready, guarded on the decision the page showed; `decide_change` in Python; with key gates only, the worker accepts every open change as `worker (key gates only)` (`accept_open_changes`) |
| edited_text | TEXT | the owner's own wording, when they edit the suggestion | same |
| decided_by | TEXT | | same |
| decided_at | TEXT timestamp | | same |
| created_at | TEXT timestamp, not null | | the worker |

Index: `(step_id, id)`. The draft is approved once every change on it is decided (the dashboard's
Approve refuses while one is `proposed`); Final checks puts
the accepted and edited changes into Draft v3, in order, each where its `before_text` still matches
(PRO-565, phase 8a). A reviewer's change is kept only when its `before_text` is in the draft it
reviewed.

## Table: pursuit_events

A pursuit's history, for Show history (PW16), including material people add. Rows are only
added. Added by `008_pursuits.sql`.

| Column | Type | Values | Written by |
|---|---|---|---|
| id | INTEGER, primary key, auto-increment | | database |
| pursuit_id | INTEGER, not null | `pursuits.id` | the helpers in `ledger/queries.py`, the dashboard's actions, the worker |
| step_id | INTEGER | the `pursuit_steps.id` the line is about, when there is one | same |
| at | TEXT timestamp, not null | | same |
| who | TEXT, not null | a person's name, `worker`, or `worker (key gates only)` | same |
| kind | TEXT, not null | one of `EVENT_KINDS` in `ledger/queries.py`: `started`, `step_saved`, `approved`, `auto_approved`, `go`, `go_with_conditions`, `changes_asked`, `retried`, `failed`, `blocked`, `stopped`, `no_go`, `closed`, `material`, `collaborators`, `builds_on`, `direction`, `checklist`, `budget`, `submitted`, `result`, `result_date` | same |
| text | TEXT, not null | the line in words, for example `Discovery approved`, or the link someone added | same |

Index: `(pursuit_id, id)`. Add material (PW4: a link or a note) writes a `material` row; the
worker reads the pursuit's `material` rows when it next works a step (PRO-580). The workspace's actions
write `approved`, `go`, `go_with_conditions`, `changes_asked`, `retried`, `no_go`, `material`, `budget` and
`checklist` rows, as the helpers in `ledger/queries.py` do.

## Table: checklist_items

The submission checklist (PW9), one row per item, so several people can tick items at the same
time. Added by `008_pursuits.sql`.

| Column | Type | Values | Written by |
|---|---|---|---|
| id | INTEGER, primary key, auto-increment | | database |
| pursuit_id | INTEGER, not null | `pursuits.id` | the worker, at Requirements and checklist (`save_checklist`); the Go or no-go gate |
| part | TEXT, not null | `registrations` (registrations and eligibility), `documents` (required documents and volumes), `inputs` (inputs needed from the owner and the team), `formatting` (formatting and packaging), `reviews` (reviews and approvals), `submission` | same |
| position | INTEGER, not null | the item's place in the checklist, from 0 | same |
| text | TEXT, not null | the item, specific to the call | same |
| source | TEXT | where the call asks for it, for example a section of the solicitation | same |
| owner | TEXT | who does it: a person's name, or a party such as the research partner | same |
| due_date | TEXT date | `YYYY-MM-DD` | same |
| origin | TEXT, not null | `requirements` (Requirements and checklist made it) or `condition` (a condition from Go with conditions, owned by the pursuit's owner) | same |
| done | INTEGER, not null, default 0 | 1 once ticked; items already met start ticked | the worker; the owner and the people working with them |
| done_by | TEXT | who ticked it: `worker` for an item already met when the checklist was made | same |
| done_at | TEXT timestamp | | same |
| created_at | TEXT timestamp, not null | | the worker; the gate |
| updated_at | TEXT timestamp, not null | touched by every write | every writer |

Index: `(pursuit_id, position)`. A tick is guarded on the `done` value the person saw.

## Table: drive_items

The Drive index the Builds on picker searches (P6, PW11), so the dashboard never calls Google.
Added by `008_pursuits.sql`.

| Column | Type | Values | Written by |
|---|---|---|---|
| id | TEXT, primary key | the Drive file or folder id | the worker's Drive refresh |
| name | TEXT, not null | the file or folder name | same |
| mime | TEXT | Drive's MIME type, for example `application/vnd.google-apps.folder` | same |
| path | TEXT | the folders above it, from the top of the shared drive, for example `Submissions/2025-01-15_sbir_c2` | same |
| parent_id | TEXT | the folder it is in | same |
| web_link | TEXT | the link that opens it in Drive | same |
| modified_at | TEXT timestamp | when it last changed in Drive | same |
| indexed_at | TEXT timestamp, not null | when a refresh last saw it | same |

Index: `(parent_id)`. The worker refreshes the index every 15 minutes and when someone chooses
Refresh (a `drive_refresh` job); a file gone from Drive leaves the index.

## Table: slop_scans

Each AI slop check of a draft (PW20 to PW23). The scanner runs in the worker, from
`AI_SLOP_SCAN`, never in the browser; the page reads the newest row for the pursuit's newest
draft. Added by `008_pursuits.sql`.

| Column | Type | Values | Written by |
|---|---|---|---|
| id | INTEGER, primary key, auto-increment | | database |
| pursuit_id | INTEGER, not null | `pursuits.id` | the worker |
| step_id | INTEGER | the `pursuit_steps.id` of the attempt whose draft was scanned | same |
| draft_file_id | TEXT | the draft's Drive file id | same |
| draft_name | TEXT | the draft's file name, shown as the draft the scan ran on | same |
| scanned_at | TEXT timestamp, not null | | same |
| words | INTEGER | the words scanned | same |
| band | TEXT | the scanner's band, for example `clean` or `light`; NULL below 150 words (PW21) | same |
| confidence | TEXT | the band's confidence; low below 300 words | same |
| points | REAL | the band's points | same |
| provisional | INTEGER, not null, default 1 | 1 until the bands are calibrated on 20 or more past Velocity proposals | same |
| ready | INTEGER, not null, default 0 | 1 when no placeholder is open and the band is clean or light; below 150 words, when no placeholder is open (PW21) | same |
| verdict | TEXT, not null | the one line from `drafting/slop_gate.py`, for example `Not ready: 1 PERSON WRITES; band light (provisional)` | same |
| fixed_count | INTEGER, not null, default 0 | the fixes the worker made before this scan | same |
| result_json | TEXT JSON, not null | the scanner's JSON report as it returned it | same |
| text_lines | TEXT | the scanned text, whose lines are the report's line numbers, so the page can show a line without opening Word | same |

Index: `(pursuit_id, id)`. Everything shown from these rows follows PW23: writing patterns and
their fixes only, never whether a text was or was not written by AI.

## Table: profiles

Each person's Profile settings (U2 to U6), so names and settings follow the person across
devices. Added by `008_pursuits.sql`.

| Column | Type | Values | Written by |
|---|---|---|---|
| name | TEXT, primary key | the person's name in `DASHBOARD_USERS` | Profile settings |
| display_name | TEXT | the name shown on votes, notes and the account menu; NULL shows `name` | same |
| initials | TEXT | the letters on the avatar; NULL takes them from the name | same |
| opens | TEXT, not null, default `home` | where the dashboard opens: `home` or `calls` (U3) | same |
| default_filters | TEXT JSON | the filters Calls opens with (U4): `{"portals": [...], "tag": "", "state": ""}`, state `open`, `closed` or empty; NULL for none | same |
| time_zone | TEXT | an IANA time zone such as `America/New_York` (U5); NULL keeps the dashboard's `America/Denver` | same |
| updated_at | TEXT timestamp, not null | | same |

## Table: worker_jobs

The worker's jobs other than steps: a Drive refresh, or Check again on the AI slop check (PW22).
Added by `008_pursuits.sql`.

| Column | Type | Values | Written by |
|---|---|---|---|
| id | INTEGER, primary key, auto-increment | | database |
| kind | TEXT, not null | `drive_refresh` or `slop_scan`; free text the worker checks | the dashboard (Check again queues `slop_scan`, one queued or working per pursuit), `run.py` |
| pursuit_id | INTEGER | `pursuits.id`, for a job about one pursuit | same |
| payload | TEXT JSON | what the job needs beyond its kind | same |
| state | TEXT, not null, default `queued` | `queued`, `working`, `done`, `failed` | the worker, each change guarded on the state before it |
| requested_by | TEXT, not null | a person's name, or the job that asked | the dashboard, `run.py` |
| requested_at | TEXT timestamp, not null | | same |
| started_at | TEXT timestamp | when the worker took it; the page shows working since then | the worker |
| finished_at | TEXT timestamp | | same |
| result | TEXT | what happened, in words | same |
| updated_at | TEXT timestamp, not null | touched by every write | every writer |

Index: `(state, id)`.

## Table: workers

The worker's heartbeat, so the dashboard can tell whether drafting is set up (P8) and when the
worker was last seen. Added by `008_pursuits.sql`.

| Column | Type | Values | Written by |
|---|---|---|---|
| name | TEXT, primary key | the worker's name, `worker` | the worker (`worker_started`, `worker_beat`) |
| started_at | TEXT timestamp, not null | when it last started | same |
| seen_at | TEXT timestamp, not null | updated on every poll, every 20 seconds, and every 30 seconds while a step runs | same |
| state | TEXT, not null | `idle`, `working`, or `stopped` when it shut down cleanly | same |
| doing | TEXT | what it is working on, in words | same |

No row means drafting is not set up yet. A `seen_at` more than ten minutes old means the
worker is not running (the dashboard says offline), and queued steps wait for it.

## Table: schema_migrations

Bookkeeping for `ledger/migrate.py`. `version` is the migration filename, `applied_at`
the timestamp. Nothing else reads it.

## How to build a dashboard against this

`dashboard/` is the working example (see DASHBOARD.md). Connect with DATABASE_URL and read the
tables directly; no API exists or is planned.
Treat the ledger as read-only from the dashboard except for the `human_*` columns on
`calls` and new rows in `decisions`, which the dashboard writes with its decide action (the
equivalent of `set_human` and `append_note`), and the decision columns of `change_requests` (`status` from
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

### Judge scoreboard

Each judge against the team's decisions, the same as `judge_records()`. Pursue and submitted
count as yes, not relevant and dismissed as no. A verdict counts only if it was given before
the call's first decision, because decided calls are among the examples in the judges'
prompt. A miss is a no on a call the team pursued; a false alarm is a yes on one it passed on.

```sql
SELECT j.judge,
       COUNT(*) AS decided,
       SUM(CASE WHEN (j.verdict = 'yes' AND c.human_status IN ('pursue', 'submitted'))
                  OR (j.verdict = 'no' AND c.human_status IN ('not_relevant', 'dismissed')) THEN 1 ELSE 0 END) AS matches,
       SUM(CASE WHEN j.verdict = 'no' AND c.human_status IN ('pursue', 'submitted') THEN 1 ELSE 0 END) AS misses,
       SUM(CASE WHEN j.verdict = 'yes' AND c.human_status IN ('not_relevant', 'dismissed') THEN 1 ELSE 0 END) AS false_alarms
FROM calls AS c
JOIN judgments AS j ON j.call_id = c.id
WHERE c.human_status IS NOT NULL
  AND j.id = (SELECT MAX(e.id) FROM judgments AS e
              WHERE e.call_id = c.id AND e.judge = j.judge
                AND e.rated_at < COALESCE((SELECT MIN(d.decided_at) FROM decisions AS d WHERE d.call_id = c.id),
                                          c.human_at))
GROUP BY j.judge
ORDER BY j.judge;
```
