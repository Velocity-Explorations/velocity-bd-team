# Dashboard

A Next.js app in `dashboard/` that reads the ledger directly, using the same DATABASE_URL as
the pipeline. No API layer sits between them. It can replace Slack as the triage surface, or
run beside it. How to run and deploy it is in [dashboard/README.md](../dashboard/README.md).

## Pages

| Path | What it shows |
|---|---|
| `/` | **Review queue.** Calls with ai_verdict yes or maybe and no human decision, newest first: verdict, title linked to the portal, due date, match tier, the AI's reason, first seen, and four buttons (Pursue, Not relevant, Submitted, Dismiss) with an optional note. Filters: portal, verdict, and "open calls only", which hides calls a portal adapter flagged as closed. Counts at the top: waiting, yes, maybe, and new this week. |
| `/calls` | **All calls**, newest first, up to 200 at a time. Filters: title text, portal, filter_result, ai_verdict (or not reviewed), human_status (or undecided). Shows the filter tier and filter_reason for rejected rows, the AI's reason behind a toggle, who decided and when, and every note. |
| `/runs` | **Scan history.** The most recent run sits at the top with its status, start time, duration, stage counts, error and log. Below it, the last 100 runs. A run still marked running two hours after it started is flagged as having no finish recorded. |
| `/proposals` | **Past submissions** from the proposals table, with win rate by portal. Shows an empty state until the Proposal Corpus plan fills the table. |

The queue and the proposals tiles use the "Triage backlog" and "Win rate by portal" queries
from [LEDGER_SCHEMA.md](LEDGER_SCHEMA.md); the "new this week" count uses its "New calls this
week" predicate.

"Closed" comes from calls.extra: any key ending in `_closed` set to true (Vulcan SOF writes
`vulcan_closed`). A future portal adapter gets the badge and the filter by following the same
convention.

Log links open `/runs/<id>/log`, which serves the file named in runs.log_path, but only from
the pipeline's log directory on the same machine. On any other host it says the log is not
there.

## The write action

`decide` in `dashboard/app/actions.ts` is the dashboard's only write. One UPDATE on `calls`:

- `human_status`: pursue, not_relevant, submitted or dismissed
- `human_by`: the viewer's name (see below)
- `human_at` and `updated_at`: now, in the ledger's ISO-8601 UTC format
- `human_notes`: when a note is typed, one line appended in the pipeline's `[at by] text`
  format, the same as `append_note()` and Slack thread replies

These are the columns a Slack reaction writes, so the reviewer's RECENT HUMAN DECISIONS block
learns from dashboard decisions exactly as it does from Slack ones.

The action only changes undecided rows. If someone decided the call elsewhere after the page
loaded, nothing is overwritten and the page says who decided it. After a successful decision
the queue re-renders without the row and shows a one-line confirmation.

## Who is deciding

There is no login yet. Decisions are attributed by one of two means:

1. **Allowlist** (default). DASHBOARD_USERS lists the people who may decide. With one name,
   that person is assumed; with several, the "Deciding as" picker in the top bar sets a
   cookie. Anyone who can reach the dashboard can pick any listed name, so keep it on the
   local machine or behind an access proxy.
2. **Header**. With DASHBOARD_USER_HEADER set, the viewer is taken from that request header
   only, as set by an access proxy, and must be on the allowlist when there is one.

`human_by` therefore holds a name for dashboard decisions and a Slack user id for Slack ones.
Writing `Name=<Slack id>` in DASHBOARD_USERS makes the dashboard show both under the name.

## Slack and the dashboard together

Both write the same columns, so both can stay active:

- A decision in either place takes the call off the dashboard queue.
- Slack keeps polling decided cards for thread notes and for a later X reaction, which still
  dismisses a call decided on the dashboard.
- Dismiss on the dashboard does not delete the Slack card. The Slack poll stops checking
  dismissed rows, so the card simply stays in the channel.

Moving triage off Slack entirely means removing the Slack reaction mapping in
`slack/sink.py` (`REACTION_STATUS` and `collect_feedback`) and the card posting step in
`run.py` (`deliver`). Leaving both active is equally valid: the two surfaces are compatible.
