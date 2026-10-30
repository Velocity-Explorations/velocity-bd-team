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
| `/` | **Home** (section Home). Five link cards: Needs review (yes and maybe), Due soon (closing within 14 days), Agent update requests, Proposals to draft (pursued, open, no draft yet), and Submitted and waiting (marked Submitted with no result yet). Then the Top 10 from the newest Monday brief, or the live ranking before the first brief, with each call's logo, deadline and days left, both verdicts, its decision now, its summary description (Claude's executive summary where there is one, shown whole, the portal's words on hover) and Claude's reason (the last two hidden below 1280px). Under the table, a status line (requests waiting, the last scan, how often Claude and Grok agree) and a link to the briefs. Home records nothing. |
| `/review` | **Needs review** and its views (section Calls; the queue was `/` until PRO-570). Needs review lists the calls with ai_verdict yes or maybe, still kept by the keyword filter, that you have not decided yet (with DASHBOARD_QUEUE=shared, that nobody has decided), newest first. The views (PRO-571): Top 10 (`?view=top10`: this week's Top 10 from the newest Monday brief, decided or not, in the brief's order), Due soon (`?view=due-soon`: closing within 14 days, soonest first), Judges agree and Judges disagree (`?view=judges-agree`, `?view=judges-disagree`; under disagree, yes against no comes first), and New this week (`?view=new`: first seen in the last 7 days). Each card counts under the bar's filters, and a column filter that matches no view leaves no card pressed. Columns: Call (the portal's logo, the title with its external-link icon, the details line with the portal's facts separated by dots, badges on their own line, with Top 10, #N for a call in this week's Top 10 and the draft badge for a call with a draft, then tags), Votes (Claude and Grok, each with a note button that opens the reasons panel under the row: both reasons, and where the details come from; then each person's latest vote, with a note button for anyone who left a note, which opens the notes panel: each note with its time and whether it came from the dashboard or a Slack thread reply; flagged people disagree), Summary description (Claude's executive summary of the call, shown whole with no label, where the review wrote one; otherwise 300 characters of the description over four lines, Scanner summary where an adapter wrote it, Members only for NSTXL's placeholder; the portal's own words in full on hover and keyboard focus. Before migration 009 the cell shows the description as before), AI reason (Claude's), Due (the deadline and the days left), First seen (hidden by default) and Decide (PRO-572): the Decide menu lists Pursue, Not relevant, Submitted and Dismiss, and Pursue and start the draft, which records Pursue and opens Start the draft on Proposals (held back until the worker has run, and on a call that cannot be drafted); Add a note opens a note sent with the decision. Under the menu, a pursued call with no draft shows Start the draft, and a call with a draft shows Open workspace with its current step (Q17, PRO-576). Marking a call Submitted while its draft is under way is refused: it is marked submitted at the Submit gate in its workspace (P7). The button carries the accent border on a call waiting for you. On Top 10, which mixes decided and undecided calls, the cell says needs your decision (with due today or due in N days within 14 days) or You: and your decision with its time, and the button reads Decide, Change or Add yours. Every header has a menu: the column's sorts in words, its filters, a keyword search for the title, description or AI reason (`q`, `desc`, `why`), Hide column, and Table settings. Clicking a row in Home's Top 10, or Enter on it, opens Top 10 here with that call marked, focused and its reasons open (`focus`). Below 1280px the description hides and Claude's reason folds under the call. Filters in the bar (PRO-558): portals (none ticked shows every portal; the menu lists every portal that has completed a scan, with its number of calls, greyed at 0, PRO-563), tag, and open or closed (closed means a portal adapter flagged the call as closed). Each column header sorts by its column, and a second click reverses it; Votes' header filters Claude's verdict and whether the judges agree. Closing soonest puts upcoming deadlines first and past ones last. |
| `/brief` | **Past weekly briefs** (section Home, linked from Home, with a breadcrumb back to it; PRO-573). The week as the Monday 9:00 job posted it to Slack, from the briefs table: the Top 10 across portals as on Home (each call's logo, deadline and days left, both verdicts, its decision now and Claude's reason; a row opens Calls, Top 10 with that call focused), then one board per portal, a content card whose label band links to that portal's calls on All calls, with its new calls by verdict, the calls waiting, top picks, pursued calls closing within 14 days, the week's decisions and the scraper line. Earlier weeks are linked at the top. Before migration 005 it says to apply it. |
| `/calls` | **All calls** (section Calls), newest first, up to 200 at a time, with Showing N of M at the bar's right. The bar above the table has title search, portals, tag and open or closed. Columns (PRO-571, PRO-572): Call, Filter (filter_result, the tier, and the reject reason), Votes (both judges, then each person's latest vote, flagged people disagree, with the same reasons and notes panels as the queue), Summary description, AI reason, Due, First seen (hidden by default) and Decide. The headers sort, and Filter's, Votes' and Decide's headers filter filter_result, ai_verdict (or not reviewed) with the judges agreeing or not, and human_status (or undecided). Decide shows the call's decision, who made it and when, your status (needs your decision on a kept yes or maybe call you have not decided, or You: and yours), and the Decide menu, whose button reads Decide, Change or Add yours: Change moves your decision, for example from Pursue to Submitted, or adds a note; Add yours appears on a call someone else decided, so your decision is kept beside theirs. The header menus work as on Needs review. |
| `/judges` | **Judge scoreboard** (section Automation, card Judges agree). How Claude and Grok compare with your decisions, counting only verdicts given before anyone decided the call, because decided calls become examples in the judges' prompt. Pursue and submitted count as yes, not relevant and dismissed as no. Per judge: how many it matched, its misses (a no on a call the team pursued), false alarms (a yes on a call the team passed on) and maybes. Per person: calls decided and how often each judge matched them. Between people: how often two people agree on the calls both decided. Last, the pursued calls a judge said no to. Before migration 004 it says to apply it. |
| `/requests` | **Agent update requests** (section Automation, where it opens): change requests from the portal assistant (docs/ASSISTANT.md, "Approvals"). It shows the requests waiting for approval, oldest first, each with who asked, why, and the preview of what approving would do, plus Approve and Reject buttons and an optional note. Decided requests (`?view=decided`, PRO-573) lists the last 50 decided, with their status, who decided, and the result, or what an approved request is waiting for. Automation's five cards: Agent update requests, Decided requests, Scans, Scan problems, Judges agree. Automation's chip in the top bar shows how many are waiting. |
| `/runs` | **Scans** (section Automation; PRO-573). The most recent run as a content card (status, start, duration, stage counts, error and log), then the last 100 runs, with a Portals filter, each portal's logo, and a Started column that sorts newest or oldest first. Scan problems (`?view=problems`) keeps only the runs that failed, timed out, or still say running two hours after they started (the process probably died). |
| `/proposals` | **Proposals** (section Proposals; PRO-575): five view cards over the pursued, drafting and submitted calls and the Proposal Register, with the filter bar as on Calls and each view's key column sortable. To draft (`/proposals`): pursued calls with no draft whose deadline has not passed, nearest deadline first, each saying why it cannot be drafted when it cannot (closed, or needs the solicitation first), or offering Start the draft (PRO-576). Closing in 14 days (`?view=closing`): pursued and drafting calls closing within 14 days. Drafting (`?view=drafting`): each pursuit with its current step, its state in words, the owner, Open workspace and the Drive folder. Submitted and waiting (`/proposals/submitted`): who submitted and when, days waiting, both verdicts, the confirmation number, and the result expected by date (the one Discovery found, else 90 days after the deadline), flagged result overdue once it passes; overdue results come first. Anyone logged in can choose No news yet (the date moves 30 or 60 days on, guarded on the date the page showed, and the history notes it) or Record result (Won, Lost, Withdrawn or Cancelled by the agency, with an optional debrief and an optional What to do differently next time, which the next alignment check reads; Lost adds a reminder to ask for a debrief). A call marked Submitted outside the workspace gets a pursuit the first time either is used, so its result is kept too. Overdue results count on the Submitted and waiting cards, here and on Home, and in the top bar's Proposals number. Results (`/proposals/results`): results recorded here, with their debrief and note for next time, and the Register's submissions, with win rate by portal. |
| `/proposals/{call id}` | **The proposal workspace** (PRO-580): one pursuit step by step, with its header, stage strip, step list and the open step's card and actions; `&view=slop` opens the AI slop check's result. See The proposal workspace below. |

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

## Start the draft and the draft badges

Start the draft (P6, PRO-576) opens a dialog from a pursued call's Start the draft button on To
draft or in its Decide cell, or on arrival at `/proposals?start=<call id>` after Pursue and start
the draft. It shows the call, its portal and deadline, and asks for:

- **Format:** read from the call's type (a Sources Sought or RFI gives RFI response; SBIR or STTR
  the technical volume; a solicitation, RFP or BAA a full proposal; anything else a white paper),
  and changeable.
- **User approval required:** every step, or key gates only (Go or no-go, the Outline, Submit).
- **Working with (optional):** anyone else in DASHBOARD_USERS. The owner is the viewer.
- **Direction (optional):** up to 2,000 characters for the worker.
- **Builds on (optional):** past work from the Proposal Library, as the worker last indexed it
  (`drive_items`): past submissions newest first, then the company reference files. Until the
  library is indexed the dialog says so. Only items the index holds are kept.

The dialog also names the Drive folder the worker will create,
`Submissions/YYYY-MM-DD_portal_short-title/` as in docs/LIBRARY_CONVENTIONS.md. Start is the
person's approval to spend: it writes
the pursuit, its Discovery step queued for the worker, and the first line of its history, in one
transaction that locks the call. Proposals' Drafting view opens next.

It is refused, with the reason, when:

- the worker has never run (Drafting is not set up yet: the dialog says so and holds Start back;
  P8);
- the call already has a draft (who started it, and when);
- the call is marked Not relevant, or is not pursued;
- the call is closed, or its page is members only so the worker cannot read the solicitation.

A worker that has gone quiet for ten minutes does not refuse: the dialog says when it was last seen,
and Discovery waits in the queue.

Wherever a call with a draft is listed (Home's Top 10, every Calls view, every Proposals view), a
badge on its own line under its details says where the draft stands (DB1, DB2): draft started, step
N, Go or no-go, draft finished at the Submit gate, submitted with its date, no-go, or draft closed.
The badge opens a menu (DB3): who owns the draft and its step, or who submitted it, when and when the
result is expected; the draft in Google Drive once the worker has made its folder; and View in
Proposals.

## The proposal workspace

`/proposals/{call id}` (PW1 to PW25, PRO-580) follows one pursuit step by step. Open workspace on Proposals'
Drafting view, in a call's Decide cell and in its draft badge's menu all lead here. The Writer is the
worker's model, Claude Sonnet 5.5 unless WRITER_MODEL names another on the scan PC, so the page calls
it the Writer rather than naming a model.

- **Header (PW1, PW19, PW24):**
  - the portal's logo, the breadcrumb with the stage (Qualifying to Submitting, or No-go, Submitted or Closed), and the title;
  - a line with the portal, the format, the deadline with the days left, the owner, the people working with them, the approval mode, what has been spent against the cap, and the folder (on the scan PC until Drive is set up);
  - at the right, People, Checklist (once Requirements and checklist has made one, with how many items are done) and Show history, each opening a panel under the header.
- **Stage strip and step list (PW1 to PW3):** Qualify, Plan, Draft, Review, Finalize and Submit, each done, now or next. Under them, the nine steps and two gates in their stages, each with its state in words: waiting, working, ready, done, failed, budget reached or stopped. A reached step opens with `?step=`; a done step opens read only.
- **The step card (PW4, PW15, PW19):**
  - what the step is for, and the note when the step was redone after Ask for changes;
  - its state: waiting for the worker (with a word when the worker is offline), working with its start time, failed with the reason and Retry, or budget reached with Raise the cap;
  - the files saved, what the Writer prepared (the key points), and the full document;
  - Your call: the step's question and its actions.
- **Actions.** Only the owner sees them (PW17, a courtesy check until sign-in); everyone else sees whom the step waits on. Each is guarded by the step's state and the time the page showed it, so a page left open while the step changed saves nothing and says so.
  - **Approve and continue:** the step is done and the next is queued for the worker.
  - **Ask for changes:** takes a note; the step is queued again with it, and the Writer redoes it with the note and its last version.
  - **Stop here, no-go:** steps 1 to 4. Takes the reason and what would change the answer; the draft stops and the call is marked Not relevant with that reason (P7).
  - **At the gate:** Go; Go with conditions, one per line, each joining the checklist as an item the owner owns; or No-go with its reason.
  - **Retry:** queues a failed step again.
  - **Raise the cap:** sets a higher budget and queues the step that reached the cap again.
- **What the people working with the owner do (PW24):** they add material (a note or a link, which the Writer reads from the next step on) and tick checklist items; the owner can too.
- **Show history (PW16):** every event with its time and who, newest first.

Each step also has its own screen (PRO-581):

- **Discovery (PW6):** the eight tasks with their states (done, working, for you) and a progress line, the pages and files left for the owner to fetch, and when the result is expected.
- **Opportunity summary (PW7):** the summary's opening paragraph with the call's agency, type, deadline and portal; the button reads Continue to Alignment.
- **Alignment (PW8):** the verdict and how the call aligns for Velocity, as tagged points (fits, past work, depends, risk, needs, no clash) with their sources; the owner's direction from Start the draft beside the Writer's proposed angle. Your call offers Keep mine, Use the Writer's angle or Write a new one; approving saves the chosen direction, which carries forward.
- **Requirements and checklist (PW9):** the volumes, page limit and format, evaluation, eligibility and keywords, the internal submit-by date, and the checklist in its six parts, tickable here as in the header's panel.
- **Go or no-go (PW10):** the decision brief (fit rating, win themes, critical gaps with how to address each, effort and timing, the recommendation) and what each choice does; Go with conditions starts with the Writer's conditions filled in.
- **Outline (PW11):** the direction and the past work, each a last chance to change (the owner edits the direction; the owner and the people working with them add past work from the Proposal Library's index, or by name or link, and remove it; Refresh the list asks the worker to index the library again, one refresh at a time), then the sections with the criterion each answers, their share and what they draw on, and any criterion with no section. Approving the Outline locks the direction and the past work.
- **First draft and Compliance check:** the draft's words and what is left to fill; what the check corrected and how many warnings to check; and the AI slop check's verdict on the draft the step saved, with a link to the latest result.
- **Reviews (PW12, PW25):** the AI slop check's row (the newest verdict, See the result, automatic), then the three reviewers in turn: the external evaluator and the second evaluator, each with their ratings in words per criterion (Outstanding and Good in green, Marginal amber, Unacceptable red, any other scale grey) and their strengths and weaknesses, then Velocity leadership, who does not rate. Each row says how many changes it suggested and how many are still to decide. Under them, each reviewer's changes: the section, the text now (struck through), the suggestion and why, with Accept, Reject and Edit at the right, and Accept all per reviewer. A decided change shows who decided it and when, with Undo while Reviews is still ready. Only the owner decides; the people working with the owner see the changes. Approve and continue stays disabled until every change is decided (the server refuses too), and approving queues Final checks, which puts the accepted and edited changes into Draft v3. The history and the notice say how many were accepted, edited and rejected.

- **Final checks (PW13):** the seven checks with their result in words (formatting, the compliance re-check, the placeholder sweep, the AI slop check's final pass with the dash check, the submission package check, the checklist, the final version saved), what is still open in the final version with its section, kind, whom it is for and a link to its line, then the checklist to tick. Approve and continue stays disabled until the newest scan of the final version says Ready, and the server refuses too; Check again sits beside it. A newer scan from Check again updates the placeholder sweep and the final pass.
- **The Submit gate (PW14):** the files with their portal slots, the portal and deadline with Open the call page at the end of its row, the checklist, what the gate checked, and the portal's steps. Your call takes the confirmation number, when it was submitted (in the viewer's time zone) and the result expected by date, which starts as the pursuit's, else Discovery's, else 90 days after the deadline. Mark submitted ends the workflow: the pursuit waits in Submitted and waiting and the call is recorded as Submitted (P7); the worker then files it in the Proposal Library, with its Register row (docs/RUNBOOK.md). A page left open while the call's decision changed saves nothing and says what the call is now (C8).

From People, the owner changes who works with them (PW24).

### The AI slop check's result

`?step=<step>&view=slop` (PW20 to PW23) opens the newest scan of the pursuit's drafts in the step's card,
from See the result in Reviews or the link on First draft and Compliance check. The worker runs the
scanner and saves each scan in `slop_scans`; the page only reads the newest row and never runs it.

- **The verdict line:** ready or not ready, the verdict as the worker's gate wrote it (for example "Not ready: 1 PERSON WRITES, 2 NEEDS INPUT; band light (provisional)"), the band, its points, the confidence and the words, and the time of the scan and the draft it ran on. Under 150 words there is no band; under 300 the band has low confidence; until the band lines are calibrated, every band is provisional (PW21).
- **Fixed on its own:** how many fixes the worker made before the scan (dashes, and tracking parameters in links).
- **Open placeholders** by kind (PERSON WRITES, NEEDS INPUT, NEEDS FACT, NEEDS EVIDENCE, other), each with its section and line. NEEDS FACT marks a company fact 01 Company Reference does not hold (docs/RUNBOOK.md, Company facts).
- **Paragraphs to revise first,** up to five, each with its section, its findings and its line range.
- **Findings by family,** with the family's tier, hits, rate per 1,000 words, points (or under its line), its fix and each finding by line and column; then the tiers with nothing left. The dated word lists read as one family, Overused words, and no label names a model or a chatbot.
- **Proposal faults,** listed apart: they do not count toward the band. Findings the solicitation's own words exempt are left out and counted.
- **Line links:** `&lines=88` or `&lines=86-94` shows the text as scanned beside the list, the linked lines marked and what was found on each line, and returns to the item that was clicked.
- **Check again (PW22):** the owner or anyone working with them queues a scan of the newest draft (a `worker_jobs` row), one at a time per pursuit. The page shows it queued or working with its start time, keeps the last result until the new one is saved, and says when a Check again did not run.
- **Words (PW23):** the page reports writing patterns and their fixes only, never who or what wrote the text; a unit test fails if any dashboard source speaks of AI authorship or a probability of it.

## Sign-in

`/login` (U7, phase 11) is the BD Team sign-in page: the Velocity mark, Sign in with Google, Reset
password (Google's account recovery) and Need access? Ask an admin. It says in words why someone is
there: signed out, timed out (the 12-hour session ended), not allowed (a Google account that is not
the company's), or cancelled. Dark only.

- **Who gets in:** Auth.js (`dashboard/auth.ts`) runs Google's sign-in for the velocityexplorations.com
  Workspace. Since 29 Oct any verified company account gets in, with nothing to sign up for; anyone
  else is refused (`lib/signin.ts`). Each sign-in is recorded in the ledger's people table, so the
  person can be chosen for Working with and the people panels from then on (`lib/team.ts`).
- **Their name:** DASHBOARD_USERS's name for their email when they are on it (which also gives their
  Slack id), else their Google name as first recorded; a name somebody else has gets the email after
  it, so two people's decisions are never mixed up.
- **Every page:** signed out, every page goes to `/login`, and back to the page asked for after
  sign-in (`proxy.ts`). The sign-in page, its files, Auth.js's routes and `/healthz` need no session.
- **Who decides:** the session alone says who is deciding, checked on every page and action. The name
  picker and its cookie count for nothing, so owner-only actions are enforced rather than courtesy
  checks. Log out is in the account menu and ends the session.
- **Until it is set up:** without `AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET` and `AUTH_SECRET`, the dashboard
  keeps the name picker, and `/login` says sign-in is not set up. Setup is in docs/RUNBOOK.md, Google
  sign-in.

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
