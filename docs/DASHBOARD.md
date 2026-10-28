# Dashboard

A Next.js app in `dashboard/` that reads the ledger directly, using the same DATABASE_URL as
the pipeline. No API layer sits between them. Since 2026-10-17 it is the only place triage
decisions are made; Slack posts the cards and carries the discussion. How to run and deploy
it is in [dashboard/README.md](../dashboard/README.md).

The brief for redesigning it in the Velocity Theme, including the planned move from seven pages
to four sections (Home, Calls, Proposals, Automation), is in [docs/design/](design/README.md).

## Look

The dashboard is dark only and wears the BD Team theme from Claude Design's handoff (PRO-569).

- **Tokens:** `dashboard/app/theme.css` copies the handoff's `tokens-app.css` and `card.css`
  (`docs/design/handoff/velocity-theme/`), and `tests/test_dashboard_theme.py` keeps the two equal.
  `app/globals.css` takes every colour, size and font from those tokens.
- **Fonts:** Inter Tight and Chakra Petch are served from `dashboard/public/fonts/`, so no page
  reaches Google Fonts. The container image copies `public/` beside the standalone build.
- **Icons:** `lucide-react`, pinned to one version.
- **Components:** each follows its guide in `docs/design/handoff/velocity-theme/components/`.
  - Buttons fill by function on hover: green to approve, blue to change or add, red to stop or
    reject.
  - Badges are a tone square and the word. Tags sit on their own line, with the type tag in the
    info tone.
  - Notices (Done, Refused) have a close button that also drops the notice from the address.
- **Keyboard:** menus take focus when they open, the arrow keys move between items, and Escape
  hands focus back to the menu's button. Hover-only text (a detail's source, a tag's setter) shows
  as a tooltip on keyboard focus too. `tests/test_dashboard_components.py` checks both against a
  running dashboard.

## Pages

The top bar holds the Velocity mark and BD Team (a link to Home), four sections with their icons,
and the account menu (PRO-570). The open section is marked, and each section shows a count chip
labelled with what it counts:
- **Calls:** calls waiting for you.
- **Proposals:** pursued calls with no draft, plus workspace steps ready for you.
- **Automation:** requests waiting.

Each section opens on a row of view cards in place of a page title. The open view's card is marked,
and switching cards keeps the portal, tag and open or closed filters while dropping the sort and the
column filters. The account menu shows who is deciding.
- **Its items:** Table settings (on Calls), Switch user (the other people in DASHBOARD_USERS, until
  Google sign-in) and Log out.
- **Log out** clears the name and returns to Home with "You are logged out of BD Team."
- **With nobody chosen,** the bar shows Log in, which lists the people to choose from.

| Path | What it shows |
|---|---|
| `/` | **Home** (section Home). Five link cards: Needs review (yes and maybe), Due soon (closing within 14 days), Agent update requests, Proposals to draft (pursued, open, no draft yet), and Submitted and waiting (marked Submitted with no result yet). Then the Top 10 from the newest Monday brief, or the live ranking before the first brief, with each call's logo, deadline and days left, both verdicts, its decision now, its description and Claude's reason (the last two hidden below 1280px). Under the table, a status line (requests waiting, the last scan, how often Claude and Grok agree) and a link to the briefs. Home records nothing. |
| `/review` | **Needs review** and its views (section Calls; the queue was `/` until PRO-570). Needs review lists the calls with ai_verdict yes or maybe, still kept by the keyword filter, that you have not decided yet (with DASHBOARD_QUEUE=shared, that nobody has decided), newest first. The views (PRO-571): Top 10 (`?view=top10`: this week's Top 10 from the newest Monday brief, decided or not, in the brief's order), Due soon (`?view=due-soon`: closing within 14 days, soonest first), Judges agree and Judges disagree (`?view=judges-agree`, `?view=judges-disagree`; under disagree, yes against no comes first), and New this week (`?view=new`: first seen in the last 7 days). Each card counts under the bar's filters, and a column filter that matches no view leaves no card pressed. Columns: Call (the portal's logo, the title with its external-link icon, the details line with the portal's facts separated by dots, badges on their own line, with Top 10, #N for a call in this week's Top 10, then tags), Votes (Claude and Grok, each with a note button that opens the reasons panel under the row: both reasons, and where the details come from; then each person's latest vote, with a note button for anyone who left a note, which opens the notes panel: each note with its time and whether it came from the dashboard or a Slack thread reply; flagged people disagree), Description (300 characters over four lines, in full on hover and keyboard focus; Scanner summary where an adapter wrote it, Members only for NSTXL's placeholder), AI reason (Claude's), Due (the deadline and the days left), First seen (hidden by default) and Decide (PRO-572): the Decide menu lists Pursue, Not relevant, Submitted and Dismiss, and Pursue and start the draft, which waits for the proposal workspace; Add a note opens a note sent with the decision. The button carries the accent border on a call waiting for you. On Top 10, which mixes decided and undecided calls, the cell says needs your decision (with due today or due in N days within 14 days) or You: and your decision with its time, and the button reads Decide, Change or Add yours. Every header has a menu: the column's sorts in words, its filters, a keyword search for the title, description or AI reason (`q`, `desc`, `why`), Hide column, and Table settings. Clicking a row in Home's Top 10, or Enter on it, opens Top 10 here with that call marked, focused and its reasons open (`focus`). Below 1280px the description hides and Claude's reason folds under the call. Filters in the bar (PRO-558): portals (none ticked shows every portal; the menu lists every portal that has completed a scan, with its number of calls, greyed at 0, PRO-563), tag, and open or closed (closed means a portal adapter flagged the call as closed). Each column header sorts by its column, and a second click reverses it; Votes' header filters Claude's verdict and whether the judges agree. Closing soonest puts upcoming deadlines first and past ones last. |
| `/brief` | **Past weekly briefs** (section Home, linked from Home, with a breadcrumb back to it; PRO-573). The week as the Monday 9:00 job posted it to Slack, from the briefs table: the Top 10 across portals as on Home (each call's logo, deadline and days left, both verdicts, its decision now and Claude's reason; a row opens Calls, Top 10 with that call focused), then one board per portal, a content card whose label band links to that portal's calls on All calls, with its new calls by verdict, the calls waiting, top picks, pursued calls closing within 14 days, the week's decisions and the scraper line. Earlier weeks are linked at the top. Before migration 005 it says to apply it. |
| `/calls` | **All calls** (section Calls), newest first, up to 200 at a time, with Showing N of M at the bar's right. The bar above the table has title search, portals, tag and open or closed. Columns (PRO-571, PRO-572): Call, Filter (filter_result, the tier, and the reject reason), Votes (both judges, then each person's latest vote, flagged people disagree, with the same reasons and notes panels as the queue), Description, AI reason, Due, First seen (hidden by default) and Decide. The headers sort, and Filter's, Votes' and Decide's headers filter filter_result, ai_verdict (or not reviewed) with the judges agreeing or not, and human_status (or undecided). Decide shows the call's decision, who made it and when, your status (needs your decision on a kept yes or maybe call you have not decided, or You: and yours), and the Decide menu, whose button reads Decide, Change or Add yours: Change moves your decision, for example from Pursue to Submitted, or adds a note; Add yours appears on a call someone else decided, so your decision is kept beside theirs. The header menus work as on Needs review. |
| `/judges` | **Judge scoreboard** (section Automation, card Judges agree). How Claude and Grok compare with your decisions, counting only verdicts given before anyone decided the call, because decided calls become examples in the judges' prompt. Pursue and submitted count as yes, not relevant and dismissed as no. Per judge: how many it matched, its misses (a no on a call the team pursued), false alarms (a yes on a call the team passed on) and maybes. Per person: calls decided and how often each judge matched them. Between people: how often two people agree on the calls both decided. Last, the pursued calls a judge said no to. Before migration 004 it says to apply it. |
| `/requests` | **Agent update requests** (section Automation, where it opens): change requests from the portal assistant (docs/ASSISTANT.md, "Approvals"). It shows the requests waiting for approval, oldest first, each with who asked, why, and the preview of what approving would do, plus Approve and Reject buttons and an optional note. Decided requests (`?view=decided`, PRO-573) lists the last 50 decided, with their status, who decided, and the result, or what an approved request is waiting for. Automation's five cards: Agent update requests, Decided requests, Scans, Scan problems, Judges agree. Automation's chip in the top bar shows how many are waiting. |
| `/runs` | **Scans** (section Automation; PRO-573). The most recent run as a content card (status, start, duration, stage counts, error and log), then the last 100 runs, with a Portals filter, each portal's logo, and a Started column that sorts newest or oldest first. Scan problems (`?view=problems`) keeps only the runs that failed, timed out, or still say running two hours after they started (the process probably died). |
| `/proposals` | **Proposals** (section Proposals; PRO-575): five view cards over the pursued, drafting and submitted calls and the Proposal Register, with the filter bar as on Calls and each view's key column sortable. To draft (`/proposals`): pursued calls with no draft whose deadline has not passed, nearest deadline first, each saying why it cannot be drafted when it cannot (closed, or needs the solicitation first); Start the draft waits for the worker. Closing in 14 days (`?view=closing`): pursued and drafting calls closing within 14 days. Drafting (`?view=drafting`): each pursuit with its current step, its state in words, the owner, Open workspace and the Drive folder. Submitted and waiting (`/proposals/submitted`): who submitted and when, days waiting, both verdicts, the confirmation number, and the result expected by date (the one Discovery found, else 90 days after the deadline), flagged result overdue once it passes. Results (`/proposals/results`): results recorded here and the Register's submissions, with win rate by portal. |

The queue and the proposals tiles use the "Triage backlog" and "Win rate by portal" queries
from [LEDGER_SCHEMA.md](LEDGER_SCHEMA.md); the "new this week" count uses its "New calls this
week" predicate; the judges page uses its "Judge scoreboard" query.

"Closed" comes from calls.extra: any key ending in `_closed` set to true (Vulcan SOF writes
`vulcan_closed`). A future portal adapter gets the badge and the filter by following the same
convention.

Under each call's title, the meta line shows its portal, then the details `lib/details.ts` reads
from its columns and `calls.extra` (PRO-535): the type, unless the portal name ends with it (NASA
Forecast's "Forecast"); the office (SAM.gov's agency path is shortened to its sub-tier, with the
whole path on hover); the set-aside ("set-aside to be determined" where NASA writes "To Be
Determined") and NAICS code when the portal gives them; SAM.gov's solicitation number, first
contact and attachment count; NSTXL's
members-only badge; Front Door's location, with a link when it reposts a SAM.gov notice; and for
AFWERX and SpaceWERX a badge per service whose topics a cycle includes, plus "opens <date>" until
submissions open, with the pre-release date on hover (PRO-542); NASA Forecast's expected
solicitation quarter (award quarter on hover), estimated value and first contact; DOE SBIR's
"upcoming" badge; and Space Florida's document count, linked to the first, with an "intent to
award" badge (PRO-549). Deadlines written as ISO timestamps (SAM.gov, DIU) show in the dashboard's
time zone, and hovering a due date shows where it came from when the portal says (NSTXL's or DOE's
sentence, DIU's wording), or why there is none: a Get Funded listing with no close date, a NASA
forecast (with its expected solicitation quarter), or an APFIT cycle, whose deadlines each
organization sets. An empty due cell says why in a word or two (forecast, members only, see
documents, no close date, set by sponsor), with the whole reason on hover.

Below the details, each call's tags show as badges (PRO-557): its one type first, in blue, then
its work, customer and access tags in the list's order. The type is the one the call's own data
sets, else Claude's, else Grok's. Hovering a tag says who set it ("the call's data", Claude,
Grok), and on the type, any other type a judge picked. A detail that repeats a tag, such as
NSTXL's "members only" badge, is left out. The review queue and All calls have a Tag filter,
grouped as the list is, and Settings can hide the tags. The tags come from `call_tags` and the
tag list from `tag_list` (migrations 006 and 007); before those exist the pages show no tags.

A contact is linked to its address unless no word of the name appears in the address. NASA's
forecast lists one person's name with another person's address on some rows, so there the name and
the address show apart, and a click never emails someone else by surprise (PRO-551).

Log links open `/runs/<id>/log`, which serves the file named in runs.log_path, but only from
the pipeline's log directory on the same machine. On any other host it says the log is not
there.

Every page follows the window's width, with 24px on each side. Tables wrap their text to fit
rather than hide columns behind a sideways scroll. The filters sit in a bar above the table,
which wraps on a narrow window. `tests/test_dashboard_layout.py` checks each page at widths from 1024 to 2560px against a
running dashboard, and is skipped without one (PRO-552):

```powershell
$env:DASHBOARD_TEST_URL = "http://localhost:8000"; pytest tests/test_dashboard_layout.py
```

Every filter and sort is a link, so a filtered view can be shared. Choices in the bar and the
header menus apply at once; the Portals menu applies when it closes (`components/MenuController.tsx`
also closes an open menu on a click outside it or Escape). `tests/test_dashboard_filters.py`
checks the bar and the headers against a running dashboard, the same way; it only reads.

Table settings, at the right of the Calls filter bar and in the account menu on Calls, opens a
dialog where each person turns Needs review's and All calls' columns on or off; Call and Decide (Decision on All calls) always show. The choice is
kept in a cookie for that browser, and Reset to defaults clears it. By default Tier, the keyword
filter's match strength, is hidden (PRO-555). `tests/test_dashboard_settings.py` checks the dialog
against a running dashboard, the same way.

## Profile settings

`/profile` (PRO-574), from Profile settings in the account menu, keeps each person's settings in
the ledger's `profiles` table, one row per name in DASHBOARD_USERS, so they follow the person to any
device (U6). Each person edits their own row; until Google sign-in that is whoever chose the name.
- **Display name and initials** show on votes, notes, decisions and the account menu. Decisions are
  still recorded under the name in DASHBOARD_USERS.
- **Where the dashboard opens:** Home, or Calls. Opening `/` from outside the dashboard (a bookmark,
  a typed address, a Slack link) takes a person who chose Calls to Needs review. Home stays one
  click away (U3).
- **Default filters for Calls:** portals, tag, and open or closed. The Calls link in the top bar
  carries them, and Needs review or All calls opened from outside the dashboard with no portal, tag
  or open or closed in its address gets them. A shared link's own filters win, and Clear filters
  shows everything (U4).
- **Time zone:** every time shows in it, in place of the dashboard's America/Denver. Deadlines a
  portal wrote as text stay as written (U5).
- **Reset to defaults** removes the row, so every default applies again.

## The write actions

`dashboard/app/actions.ts` has two writes.

`decideRequestAction` approves or rejects a change request on `/requests`: one UPDATE on
`change_requests` setting `status` (approved or rejected), `decided_by` (the viewer),
`decided_at`, `decision_note` and `updated_at`, only while the request is still `proposed`.
A request decided in another tab is not overwritten; the page says who decided it. The scan
machine carries out approved requests twice a day, at 12:07 and 17:07 (`run.py --apply-requests`).

`decide` records triage decisions, used by the queue's buttons and by the control on
`/calls`. One transaction: an UPDATE on `calls`, and a row in `decisions` (migration 004) with
who decided, what, when and the note, so every person's decision is kept. On `calls`:

- `human_status`: pursue, not_relevant, submitted or dismissed
- `human_by`: the viewer's name (see below)
- `human_at` and `updated_at`: now, in the ledger's ISO-8601 UTC format
- `human_notes`: when a note is typed, one line appended in the pipeline's `[at by] text`
  format, the same as `append_note()` and Slack thread replies

Choosing the decision a call already has, when someone else made it, adds your row in
`decisions` and leaves the call's decision, its author and its time alone (a note is still
appended). Saving your own current decision again with a note only appends the note; with no
note it changes nothing. Choosing a different decision changes the call's decision: the
newest change wins on `calls`, and both people's decisions stay in `decisions`.

On the review queue while everyone decides every call (the default; DASHBOARD_QUEUE=each), the
first decision becomes the call's decision and every later one is added beside it without
changing it, whatever it says. A call's decision changes only from All calls. A vote from the
queue takes the call out of your queue, so the notice says so and links to the call on All
calls, where every person's vote shows (PRO-554).

Every form carries the decision the page showed. On All calls, and on a shared queue, if the
call was decided or changed by someone else after the page loaded, nothing is written and the
page says what the call is now. While everyone decides every call, a queue button adds your
decision beside the one made meanwhile. Either way, a queue row cannot overwrite a decision
made in another tab.

The reviewer's RECENT HUMAN DECISIONS block reads these columns, so every decision made here
shapes the next review.

## Who is deciding

There is no login yet. Decisions are attributed by one of two means:

1. **Allowlist** (default). DASHBOARD_USERS lists the people who may decide. With one name,
   that person is assumed; with several, choosing a name in the account menu (Log in, or
   Switch user) sets a cookie at once, and Log out removes it (PRO-553, PRO-570).
   The cookie belongs to the host name, not the port, so two dashboards on one machine share it
   unless they are opened under different names (localhost and 127.0.0.1). Anyone who can reach
   the dashboard can pick any listed name, so keep it on the local machine or behind an access
   proxy. `tests/test_dashboard_viewer.py` checks the account menu against a running dashboard,
   the same way as the layout test.
2. **Header**. With DASHBOARD_USER_HEADER set, the viewer is taken from that request header
   only, as set by an access proxy, and must be on the allowlist when there is one.

`human_by` and `decisions.decided_by` hold the person's name. Calls decided with Slack
reactions before 2026-10-17 hold a Slack user id instead; writing `Name=<Slack id>` in
DASHBOARD_USERS shows those under the name too, and counts them as that person's on the judges
page.

Several people can decide. Each person's decisions are kept separately, so adding someone is
one more `Name=<Slack id>` entry in DASHBOARD_USERS (comma separated) and a restart of the
dashboard.

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
