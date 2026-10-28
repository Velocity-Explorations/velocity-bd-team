# Spec updates for the redesign

Changes to `docs/design/dashboard-design-spec.md` (read at 65a5fce), section by section. "Changed" rows replace the row with that ID; "New" rows are added. New areas get new prefixes: VC (view cards), PW (proposal workspace) and DB (draft and submitted badges). If `tests/test_design_brief.py` expects one-letter prefixes, renumber on merge and keep the mapping in the Decision log row.

## Pages

Replace the opening paragraph and the page table with:

> Four sections share one top bar: Home, Calls, Proposals and Automation. Pages have no title and no tabs: each section opens on a row of view cards (VC1), and the selected card says which view is open. The bar carries the brand, the four section links with the current one highlighted, count badges (N3) and the account menu.

| Section | View card | Address | What it shows |
| --- | --- | --- | --- |
| Home | none | / | Five link cards, then the Top 10 table (section Home) |
| Calls | Needs review | /review | Calls rated yes or maybe that wait for the viewer |
| Calls | Top 10 | /review?view=top10 | This week's Top 10 in brief order |
| Calls | Due soon | /review?view=due-soon | Waiting calls closing within 14 days, soonest first |
| Calls | Judges agree, Judges disagree | /review?view=judges-agree, /review?view=judges-disagree | Waiting calls where Claude and Grok agree, or disagree |
| Calls | New this week | /review?view=new | Waiting calls first seen this week |
| Calls | All calls | /calls | Every call scanned, rejected ones too, up to 200 rows, with Showing N of M |
| Proposals | Closing in 14 days | /proposals?view=closing | Pursued and drafting calls closing within 14 days |
| Proposals | To draft | /proposals | Pursued calls with no draft yet |
| Proposals | Drafting | /proposals?view=drafting | Pursuits under way, with their current step |
| Proposals | Submitted and waiting | /proposals/submitted | Submitted calls waiting on a result |
| Proposals | Results | /proposals/results | Results recorded here and from the Proposal Register, with win rate by portal |
| Proposals | none | /proposals/{call id} | The proposal workspace for one call (section Proposal workspace) |
| Automation | Agent update requests | /requests | Waiting requests with Approve and Reject with a note |
| Automation | Decided requests | /requests?view=decided | The last 50 decided requests with their result |
| Automation | Scans | /runs | The latest run on top, then the last 100 runs |
| Automation | Scan problems | /runs?view=problems | Runs that failed or timed out |
| Automation | Judges agree | /judges | Judge scores against people, by person, between people |

| ID | Change | Requirement |
| --- | --- | --- |
| N1 | Changed | The top bar shows four sections: Home, Calls, Proposals and Automation. The current section is highlighted whichever view is open, including the proposal workspace under Proposals. Automation opens on Agent update requests. |
| N2 | Changed | Each section opens on a row of view cards in place of tabs (VC1). Each view has its own address, so a link opens the right view (table above). |
| N3 | Changed | Count badges on the section links: Calls, calls waiting for the viewer; Proposals, pursued calls with no draft plus workspace steps ready for the viewer; Automation, requests waiting. Each badge has a label saying what it counts. |
| N4 | Changed | Old addresses keep working: /review, /calls with its filters, /brief, /judges, /requests, /runs, /proposals, /proposals/submitted and /proposals/results each open their view. |
| N6 | Changed | Switching view cards within a section keeps the portal, tag and open or closed filters, and resets the column filters and sort to the view's own. |

## View cards (new section)

| ID | Change | Requirement |
| --- | --- | --- |
| VC1 | New | A view card shows a label band, a count and one line of description, aligned across the row (the theme's card, `velocity-theme/components/view-cards`). Choosing one changes the table below; the chosen card is marked pressed. |
| VC2 | New | Counts follow the filter bar: a portal or tag filter narrows every card's count as well as the table. |
| VC3 | New | Home's cards are links that open their view: Needs review, Due soon, Agent update requests, Proposals to draft, and Submitted and waiting. |
| VC4 | New | A column filter that matches no card's view leaves no card pressed. |

## Home

Replace H1 to H7 with:

| ID | Change | Requirement |
| --- | --- | --- |
| H1 | Changed | Five link cards (VC3), each with its count and one line, in this order: Needs review, Due soon, Agent update requests, Proposals to draft, Submitted and waiting. |
| H2 | Changed | Top 10 is the only table: the best open calls across portals, ranked as the Monday brief ranks them (yes before maybe, then the nearest deadline, then the newest). Each row: rank, logo, the title linked to its portal page, the portal, the deadline and days left, both verdicts, the decision now, the description and Claude's reason (up to six lines each). Below 1280px the description and the reason are hidden. |
| H3 | Changed | A status line under the table: requests waiting, the last scan's result in words and when it ran, and how often Claude and Grok agree, each linked to its view. |
| H4 | Changed | A link to this week's brief and the past weekly briefs (/brief). |
| H5 | Changed | Home records nothing. Was H7. |
| H6 | Removed | Folded into H4. |
| H7 | Removed | Now H5. |

## Calls

| ID | Change | Requirement |
| --- | --- | --- |
| Q9 | Changed | Decide cell: a Decide menu listing Pursue, Not relevant, Submitted and Dismiss, each with its word; choosing one records it. When the call has no pursuit, the menu adds Pursue and start the draft, which records Pursue and opens Start the draft (P6). Add a note opens an optional note (up to 2,000 characters). |
| Q (next) | New | Description column before the AI reason on every Calls view: the call's description, first 300 characters, up to four lines, in full on hover and on keyboard focus. Text the scanner wrote, not the portal (AFWERX, SpaceWERX, APFIT and the first sentence of NASA Forecast rows), is labelled Scanner summary. A members-only page says Members only. Hidden below 1280px; Table settings can hide it. |
| Q (next) | New | Your decision status in the Decide cell. On a call in the queue that you have not decided, the Decide button has an accent border. In views that mix calls you have and have not decided (Top 10 and All calls), it also shows a needs your decision badge, with due today or due in N days on its own line under it when the call closes within 14 days. Once you decide, that badge becomes You: and your decision, with its time, and the button reads Change. Views that hold only calls waiting for you (Needs review, Due soon, Judges agree, Judges disagree, New this week) show no badge. The row itself is not tinted. |
| Q (next) | New | Clicking a row in Home's Top 10 (outside its links and buttons), or Enter on the focused row, opens Calls, Top 10 with that call scrolled into view, marked with an accent bar and its reasons panel open. Calls, Top 10 lists all ten calls, decided or not. |
| Q (next) | New | Every table's body rows lighten on hover. |
| Q (next) | New | On a pursued call with no pursuit, the Decide cell shows Start the draft (P6); on a call with a pursuit, Open workspace with its current step. |
| Data per call | Changed | Description: up to 1,500 to 4,000 characters depending on the portal (was "Up to 1,500 characters"). |

## Draft and submitted badges (new section)

| ID | Change | Requirement |
| --- | --- | --- |
| DB1 | New | Wherever a call appears (Home's Top 10, every Calls view, every Proposals view), a call with a pursuit shows a badge on its own line under its details: draft started, step N while it is being worked, or draft finished once it reaches the Submit gate. |
| DB2 | New | A submitted call shows submitted and its date instead, wherever it appears. |
| DB3 | New | The badge is a button that opens a menu: View the draft (or the submission) in Google Drive, View in Proposals, and one line saying who owns it and its step, or who submitted it, when, and when the result is expected. |

## Proposals

Replace P1 to P8 with:

| ID | Change | Requirement |
| --- | --- | --- |
| P1 | Changed | Five view cards: Closing in 14 days, To draft, Drafting, Submitted and waiting, Results. The filter bar (portals, tag, open or closed) and a sortable key column work as on Calls. |
| P2 | Changed | To draft: pursued calls that are still open and have no pursuit, nearest deadline first, each with Start the draft. A call that cannot be drafted says why in place of the button: closed, or needs the solicitation first (a members-only page the worker cannot read). |
| P3 | Changed | Drafting: each pursuit with its current step, its state in words (working, ready for the owner, failed), the owner, Open workspace and the Drive folder. |
| P4 | Changed | Submitted and waiting: who submitted it and when, the confirmation number, days waiting and the result expected by date: the date Discovery found in the call for when results are announced, with its source, or 90 days after the deadline when the call does not say. The owner can change it at the Submit gate. Once that date passes the row says result overdue. No news yet moves the date 30 days on. Record result: Won, Lost, Withdrawn or Cancelled by the agency, with an optional debrief note and an optional What to do differently next time, which Results shows and the next alignment check reads; the call moves to Results. |
| P5 | Changed | Results: results recorded here and past submissions from the Proposal Register, with win rate by portal. |
| P6 | Changed | Start the draft opens a dialog: the format read from the call's type (changeable when the call allows more than one), user approval required (every step, or key gates only), the owner (the viewer), the deadline, optional people to work with (PW24), an optional direction, and optional past work to build on. Its Start button is the person's approval to spend, since a draft takes 20 to 60 minutes and costs money. It creates the Drive folder and starts Discovery. A second pursuit of the same call, or a call marked Not relevant, is refused with the reason. |
| P7 | Changed | Two workspace actions record the call's decision, through the same guard as All calls (C8): Mark submitted records Submitted, and No-go records Not relevant with its note. Choosing Submitted in a Decide menu on a call with an open pursuit opens its Submit gate instead. |
| P8 | Unchanged | Starting a draft needs the worker (build-plan, Worker). Until it exists, Start the draft says Drafting is not set up yet. |

## Proposal workspace (new section)

| ID | Change | Requirement |
| --- | --- | --- |
| PW1 | New | The workspace is a page at /proposals/{call id}: a header (logo, title, portal, format, deadline, owner, approval mode, Drive folder link, then Checklist from step 4 and Show history at the far right), and a stage strip: Qualify, Plan, Draft, Review, Finalize, Submit. |
| PW2 | New | A step list on the left with each step's state in words: waiting, working, ready, done, failed. Any done step opens read only. |
| PW3 | New | The steps, in order: 1 Discovery, 2 Opportunity summary, 3 Alignment, 4 Requirements and checklist, the Go or no-go gate, 5 Outline, 6 First draft, 7 Compliance check, 8 Reviews, 9 Final checks, then the Submit gate. |
| PW4 | New | The open step shows what it is for, what Claude prepared (its file in Drive and the key points), the question for the person, and its actions: Approve and continue, Ask for changes (with a note; Claude redoes the step), Add material, and on steps 1 to 4 Stop here, no-go. Button colours follow their function on hover: green to approve, blue to change or add, red to stop. |
| PW5 | New | With key gates only, steps other than Go or no-go, Outline and Submit are approved automatically when Claude finishes them, and the history says so. |
| PW6 | New | Discovery lists its tasks with their state: re-check the call page, download every attachment, find the parent instructions, pull out the key facts (including when results are announced, for P4), compare with past work (starting from Builds on), check for clashes, bring in the dashboard's record, write the Discovery summary. Anything behind a login is listed for the owner to fetch. |
| PW7 | New | Opportunity summary gives the call's full description and key facts, with Continue to Alignment. |
| PW8 | New | Alignment gives a verdict and how the call aligns for Velocity (both judges' reasons, people's notes, the past work), with the owner's direction beside Claude's proposed angle. The owner keeps theirs, takes Claude's or writes a new one; the result carries forward, shows again at the Outline, then locks. |
| PW9 | New | Requirements and checklist lists the volumes, evaluation, eligibility and keywords, and creates the submission checklist in six parts: registrations and eligibility, required documents and volumes, inputs needed from the owner and the team, formatting and packaging, reviews and approvals, submission (fewer for an RFI or white paper). Each item is specific to the call, cites its source, and has an owner and a due date; items already met start ticked. The step also sets an internal submit-by date one business day before the deadline, with the milestones worked back from it, and lists the questions for the government and the source documents. The checklist is tickable from the Checklist button from then on. |
| PW10 | New | Go or no-go shows Claude's decision brief: fit rating (Strong, Moderate, Stretch or Poor fit), win themes, critical gaps with how to address each, effort and timing against the milestones, and a recommendation. The owner chooses Go; Go with conditions, where each condition (one per line, at least one) joins the checklist as an item they own; or No-go, which needs the reason and what would change the answer, saves a decision note, records Not relevant (P7) and moves the call's folder to Submissions/_no-go/. |
| PW11 | New | Outline lists the sections with the criterion each answers and its share of the page limit, and the past work each draws on. Past work can be changed until the Outline is approved; approving locks the direction and the past work. |
| PW25 | New | The two evaluator passes rate each evaluation criterion in words (Outstanding, Good, Acceptable, Marginal or Unacceptable, or the solicitation's own scale), shown on their rows in Reviews. The leadership pass does not rate the criteria. |
| PW12 | New | Reviews: the AI slop check runs on every new draft without asking and fixes what it can (PW20 to PW23). Then three Claude passes (an external evaluator, a second evaluator, Velocity leadership) each propose changes, one per row with the text now, the suggestion and why, and Accept, Reject and Edit at the right. The draft is approved once every change is decided. |
| PW20 | New | AI slop check result, opened from the AI slop check row in Reviews, for the latest scan of the newest draft: (1) the verdict line, for example "Not ready: 1 PERSON WRITES, 2 NEEDS INPUT; band light (provisional)", with the band, its points, its confidence and the word count, the time of the last scan and the draft it ran on; (2) the open placeholders by kind, PERSON WRITES and NEEDS INPUT, each linked to its line; (3) up to five paragraphs to revise first, each linked to its line range; (4) the findings grouped by family, each with its tier, hits, rate per 1,000 words, the family's fix and its findings by line and column, then the tiers with nothing left; (5) the proposal faults in their own list, which do not count toward the band; (6) Check again. A line link opens the scanned text beside the list at that line. |
| PW21 | New | A draft is Ready when no placeholder is open and the band is clean or light. Below 150 words there is no band; below 300 words the band has low confidence. Until the band lines are calibrated on 20 or more Velocity proposals from 2019 to 2022, every band shows provisional. Submit opens only when the newest draft is Ready. |
| PW22 | New | Check again queues a scan of the newest draft in Drive. The page shows working with its start time and keeps the last result until the new one is saved. The scan runs in the worker, never in the browser. |
| PW23 | New | The AI slop check reports writing patterns and their fixes only. No screen, file or message says or implies that a text was or was not written by AI, and none shows a probability of it. |
| PW13 | New | Final checks shows seven checks with their result in words: formatting, the compliance re-check, the placeholder sweep grouped by type with who provides each, the AI slop check's final verdict with the dash-check, the submission package check (format, names, size limits, markings, PDF fonts and page count), the checklist update, and the final version saved. Then the checklist for the owner to tick. While a placeholder is open the AI slop check says Not ready, Approve and continue is unavailable, and Check again runs the checks once more. |
| PW14 | New | The Submit gate links to the call's page (Open the call page, at the end of its row), and takes the confirmation number and the result expected by date. Mark submitted ends the workflow (P7); the call waits in Submitted and waiting. |
| PW15 | New | While Claude works a step, the step says so with its start time and asks nothing; Slack tells the owner when it is ready. A failed step says why, with Retry. |
| PW16 | New | Show history lists each event with its time and who: started, each step saved, approved or redone, the gate decisions, submitted. |
| PW17 | New | Only the owner sees the approve, change and gate actions and decides the reviewers' changes; everyone else sees the step with a line saying it is waiting on the owner. Enforced once Google sign-in is live (PRO-477). |
| PW24 | New | A pursuit has one owner and any number of people working with them, chosen at Start the draft or from People in the workspace header (only the owner changes the list). People working on it can add material and Builds on, tick checklist items, and get the step ready and behind Slack messages; the header lists them after the owner, and Show history records each change. |
| PW19 | New | Each pursuit has a spending cap, $200 by default. When the next step would pass it, the worker stops and the step says budget reached, with Raise the cap for the owner. The header shows what has been spent. |
| PW18 | New | Slack, in the call's thread: a step is ready, a step is behind its target (targets worked back from the internal submit-by date, PW9), and a daily 08:00 digest per owner of steps waiting on them. A call with no Slack card gets one posted when its pursuit starts. |

## Deciding

| ID | Change | Requirement |
| --- | --- | --- |
| V4 | Changed | Deciding with nobody chosen refuses with: Log in (top right) before deciding. |
| V6 | Changed | On the queue, the first decision becomes the call's decision; later ones are added beside it without changing it. A call's decision changes from All calls, and from the workspace's Mark submitted and No-go (P7). |

## Account menu and profile

| ID | Change | Requirement |
| --- | --- | --- |
| U7 | New | Signed out, the dashboard opens its own sign-in page at /login: the Velocity mark and BD Team, Sign in with Google, Reset password (Google's account recovery) and Need access? Ask an admin. There is no Create account: an admin adds people. Messages in words: signed out, timed out, not allowed (a Google account not on the list), cancelled. Log out returns here. Dark only, no theme switch. |
| U2 | Changed | Profile settings is a page at /profile: display name and initials (shown on votes, notes and the account menu) and, after Google sign-in (PRO-477), the account signed in with. |

## Decision log rows to add

| Date | Decision | Ticket |
| --- | --- | --- |
| 27 Oct | View cards replace tabs and page titles in every section; Home becomes five link cards and the Top 10 table | new |
| 27 Oct | The proposal workspace: a step-by-step page per pursued call, Claude doing each step and the owner approving each step or only key gates | new |
| 27 Oct | Draft and submitted badges on a call wherever it appears; a draft can start from any row once the call is pursued | new |
| 27 Oct | Submitted and waiting tracks a result expected by date, with No news yet and Record result (won, lost, withdrawn, cancelled by the agency) | new |
| 27 Oct | A Description column on the Top 10 and Calls tables | new |
| 28 Oct | From the complete skills: a six-part submission checklist with an internal submit-by date; a decision brief with Go with conditions at go or no-go; seven final checks. Submitting stays with the owner on the portal | new |
| 28 Oct | One owner per pursuit, with people working with them; Lisa and Alec added as decision makers; the result expected by date is researched in Discovery, else 90 days after the deadline | new |
