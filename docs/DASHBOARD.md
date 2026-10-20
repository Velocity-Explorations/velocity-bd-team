# Dashboard

A Next.js app in `dashboard/` that reads the ledger directly, using the same DATABASE_URL as
the pipeline. No API layer sits between them. Since 2026-10-17 it is the only place triage
decisions are made; Slack posts the cards and carries the discussion. How to run and deploy
it is in [dashboard/README.md](../dashboard/README.md).

## Pages

| Path | What it shows |
|---|---|
| `/` | **Review queue.** Calls with ai_verdict yes or maybe, still kept by the keyword filter, and no decision yet, newest first: verdict, title linked to the portal, due date, match tier, the AI's reason, first seen, and four buttons (Pursue, Not relevant, Submitted, Dismiss) with an optional note. Filters, in a panel on the left: portals (tick any; none ticked shows every portal), open or closed (closed means a portal adapter flagged the call as closed), sort (newest first, or closing soonest, which puts upcoming deadlines first and past ones last), and verdict. Counts at the top: waiting, yes, maybe, and new this week. |
| `/calls` | **All calls**, newest first, up to 200 at a time. Filters, in the same left panel: portals, open or closed, sort, title text, filter_result, ai_verdict (or not reviewed), human_status (or undecided). Shows the filter tier and filter_reason for rejected rows, the AI's reason behind a toggle, who decided and when, and every note. Each row has a "decide" or "change" control, for example to move a call from Pursue to Submitted, or to add a note to a decided call. |
| `/requests` | **Change requests** from the portal assistant (docs/ASSISTANT.md, "Approvals"). Requests waiting for approval come first, oldest first, each with who asked, why, and the preview of what approving would do, plus Approve and Reject buttons and an optional note. Below them, the last 50 decided requests with their status, who decided, and the result, or what an approved request is waiting for. The Requests link in the top bar shows how many are waiting. |
| `/runs` | **Scan history.** The most recent run sits at the top with its status, start time, duration, stage counts, error and log. Below it, the last 100 runs. A run still marked running two hours after it started is flagged as having no finish recorded. |
| `/proposals` | **Past submissions** from the proposals table, with win rate by portal. Shows an empty state until the Proposal Library plan fills the table. |

The queue and the proposals tiles use the "Triage backlog" and "Win rate by portal" queries
from [LEDGER_SCHEMA.md](LEDGER_SCHEMA.md); the "new this week" count uses its "New calls this
week" predicate.

"Closed" comes from calls.extra: any key ending in `_closed` set to true (Vulcan SOF writes
`vulcan_closed`). A future portal adapter gets the badge and the filter by following the same
convention.

Log links open `/runs/<id>/log`, which serves the file named in runs.log_path, but only from
the pipeline's log directory on the same machine. On any other host it says the log is not
there.

## The write actions

`dashboard/app/actions.ts` has two writes.

`decideRequestAction` approves or rejects a change request on `/requests`: one UPDATE on
`change_requests` setting `status` (approved or rejected), `decided_by` (the viewer),
`decided_at`, `decision_note` and `updated_at`, only while the request is still `proposed`.
A request decided in another tab is not overwritten; the page says who decided it. The scan
machine carries out approved requests twice a day, at 12:07 and 17:07 (`run.py --apply-requests`).

`decide` records triage decisions, used by the queue's buttons and by the control on
`/calls`. One UPDATE on `calls`:

- `human_status`: pursue, not_relevant, submitted or dismissed
- `human_by`: the viewer's name (see below)
- `human_at` and `updated_at`: now, in the ledger's ISO-8601 UTC format
- `human_notes`: when a note is typed, one line appended in the pipeline's `[at by] text`
  format, the same as `append_note()` and Slack thread replies

Saving the same decision with a note appends the note and leaves the decision, its author and
its time alone. Saving the same decision with no note changes nothing.

Every form carries the decision the page showed. If the call was decided or changed by
someone else after the page loaded, nothing is written and the page says what the call is
now. A queue row therefore cannot overwrite a decision made in another tab.

The reviewer's RECENT HUMAN DECISIONS block reads these columns, so every decision made here
shapes the next review.

## Who is deciding

There is no login yet. Decisions are attributed by one of two means:

1. **Allowlist** (default). DASHBOARD_USERS lists the people who may decide. With one name,
   that person is assumed; with several, the "Deciding as" picker in the top bar sets a
   cookie. Anyone who can reach the dashboard can pick any listed name, so keep it on the
   local machine or behind an access proxy.
2. **Header**. With DASHBOARD_USER_HEADER set, the viewer is taken from that request header
   only, as set by an access proxy, and must be on the allowlist when there is one.

`human_by` holds the person's name. Calls decided with Slack reactions before 2026-10-17 hold
a Slack user id instead; writing `Name=<Slack id>` in DASHBOARD_USERS shows those under the
name too.

## Slack's role

Slack informs; it does not decide.

- Each run posts one card per new yes or maybe call, then a summary that says to decide on
  the dashboard. With DASHBOARD_URL set in the repo's `.env`, both link to it.
- Reactions on cards are not read.
- Every reply in a card's thread becomes a note on that call, before or after a decision.
- Each feedback pass (at the start of every pipeline run, and the daily 18:00 task) edits any
  card whose decision differs from the ledger. The card gains a first line such as
  "Decision: Not relevant by David Wood" with the time, or loses it if a decision is cleared.
  Cards are never deleted; a dismissed call's card says Dismissed.

Until the dashboard is hosted, only people who can open it can decide. Everyone else can
still read the cards and add notes in their threads.
