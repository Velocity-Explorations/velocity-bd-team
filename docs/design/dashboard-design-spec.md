# BD Dashboard Design Spec

25 Oct 2026, David; revised 26 Oct for Home and the four sections, and 28 Oct for the handoff

Every requirement and decision behind the Velocity BD triage dashboard as of 26 Oct 2026, written as a brief for redesigning it in the Velocity Theme design system. A redesign keeps every requirement here; how each one looks is open. On 26 Oct the seven pages became four sections, Home, Calls, Proposals and Automation (section Pages); on 27 and 28 Oct Claude Design's handoff replaced tabs with view cards and added the proposal workspace (section Proposal workspace). The snapshot still shows the seven pages they come from.

## Purpose and users

The dashboard is the one place Velocity's BD team decides which government opportunities to pursue. Slack posts a card per promising call and carries the discussion; it never records a decision.

The loop it serves, every week:

1. Sunday 22:00 the pipeline scans 11 portals (Vulcan SOF, SSC Front Door, SAM.gov, NSTXL, DIU, AFWERX, SpaceWERX, DOE SBIR, NASA Forecast, Space Florida, APFIT).
2. A keyword filter keeps likely fits. Claude (claude-haiku-5-5) rates each kept call yes, maybe or no with a one-sentence reason, and Grok (grok-4.7) gives a second verdict.
3. Rules, Claude and Grok tag every call from a set list.
4. People triage on the dashboard: Pursue, Not relevant, Submitted or Dismiss, with an optional note. Every decision feeds the next review's prompt and scores the judges.

People: David and Shaun decide today, and more can be added. While the judges are being trained, everyone decides every call, so each person has their own queue.

The jobs, most frequent first:

- See what needs attention at a glance: calls waiting, the best open calls, deadlines coming up and submissions waiting on a response.
- Triage the week's new calls quickly, seeing why each was flagged.
- Find calls by portal, tag, deadline or verdict, and revisit a decision.
- Follow pursued calls to submission, and see what is still waiting on a response.
- See how Claude and Grok compare with each person.
- Approve or reject the portal assistant's change requests, and check scan health.

David's design goal, 24 Oct: use the space effectively. Long reasons, tags, details and up to eight columns compete for width.

## Pages

Four sections share one top bar: Home, Calls, Proposals and Automation. Pages have no title and no tabs: each section opens on a row of view cards (VC1), and the selected card says which view is open. The bar carries the brand (the Velocity mark and BD Team, David, 28 Oct), the four section links with the current one highlighted, count badges (N3) and the account menu.

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

Past weekly briefs keep a page at /brief, outside the top bar and linked from Home (H4), because Monday's Slack post links there. It shows the week as the Monday 9:00 job posted it: the Top 10 table as on Home, then one board per portal, each a content card whose label band links to that portal's calls, with earlier weeks linked at the top.

| ID | Requirement |
| --- | --- |
| N1 | The top bar shows four sections: Home, Calls, Proposals and Automation. The current section is highlighted whichever view is open, including the proposal workspace under Proposals. Automation opens on Agent update requests. |
| N2 | Each section opens on a row of view cards in place of tabs (VC1). Each view has its own address, so a link opens the right view (table above). |
| N3 | Count badges on the section links: Calls, calls waiting for the viewer; Proposals, pursued calls with no draft plus workspace steps ready for the viewer; Automation, requests waiting. Each badge has a label saying what it counts. |
| N4 | Old addresses keep working: /review, /calls with its filters, /brief, /judges, /requests, /runs, /proposals, /proposals/submitted and /proposals/results each open their view. |
| N5 | The account menu sits at the right of the top bar on every page (U1). |
| N6 | Switching view cards within a section keeps the portal, tag and open or closed filters, and resets the column filters and sort to the view's own. |

The rest of this spec calls Needs review the queue and All calls the All calls page. They get the most use and carry most of the requirements below.

## View cards

Every section but the proposal workspace opens on a row of view cards in place of a title and tabs (27 Oct).

| ID | Requirement |
| --- | --- |
| VC1 | A view card shows a label band, a count and one line of description, aligned across the row (the theme's card, `velocity-theme/components/view-cards`). Choosing one changes the table below; the chosen card is marked pressed. |
| VC2 | Counts follow the filter bar: a portal or tag filter narrows every card's count as well as the table. |
| VC3 | Home's cards are links that open their view: Needs review, Due soon, Agent update requests, Proposals to draft, and Submitted and waiting. |
| VC4 | A column filter that matches no card's view leaves no card pressed. |

## Home

Home is the landing page: five link cards, the Top 10 table and a status line (27 Oct). Each reads the ledger live.

| ID | Requirement |
| --- | --- |
| H1 | Five link cards (VC3), each with its count and one line, in this order: Needs review, Due soon, Agent update requests, Proposals to draft, Submitted and waiting. |
| H2 | Top 10 is the only table: this week's Top 10 from the Monday brief (the `briefs` table), with each call's decision as of now; before the first brief exists, the live ranking (yes before maybe, then the nearest deadline, then the newest). Each row: rank, logo, the title linked to its portal page, the portal, the deadline and days left, both verdicts, the decision now, the description and Claude's reason (up to six lines each). Below 1280px the description and the reason are hidden. |
| H3 | A status line under the table: requests waiting, the last scan's result in words and when it ran, and how often Claude and Grok agree, each linked to its view. |
| H4 | A link to this week's brief and the past weekly briefs (/brief). |
| H5 | Home records nothing. Was H7. |

## Calls: To review

Needs review (/review) is the queue. It lists the calls Claude rated yes or maybe that the keyword filter kept and the viewer has not decided, newest first, up to 500; Top 10, Due soon, Judges agree, Judges disagree and New this week are views of the same calls (Pages). Its columns, in order: Call, Votes (each judge's verdict and each person's latest vote: Q3, Q4 and Q8), Description (Q13), AI reason, Due, First seen (hidden by default), Decide. The Tier column is gone; All calls' Filter cell still shows the tier.

| ID | Requirement |
| --- | --- |
| Q1 | Who is waiting: while everyone decides every call (the default), each person's queue holds the calls they have not decided. In shared mode it holds the calls nobody has decided. |
| Q2 | The view cards' counts replace the metric cards (VC1); Home's Needs review card carries the waiting count with yes and maybe (H1). |
| Q3 | Claude / Grok cell: each judge's verdict as a badge (yes green, maybe amber, no red, not reviewed grey). Grok's reason opens from a why toggle; Claude's reason is the AI reason column. |
| Q4 | Disagreement flags in that cell: judges disagree (amber) when the verdicts differ, and judges: yes vs no (red) when one said yes and the other no. |
| Q5 | Call cell: the title links to the portal's page; under it the details line, then the tags line (section Details, tags and badges). |
| Q6 | Due cell: the deadline in the dashboard's time zone; hover says where it came from; a blank deadline says why in a word or two (section Formats). |
| Q7 | AI reason cell: Claude's one-sentence reason, often 40 to 70 words, the longest text in the row. |
| Q8 | Decided so far (each-person mode only): other people's votes as Name: Decision, nobody yet when none, and a people disagree badge when one said yes and another no. |
| Q9 | Decide cell: a Decide menu listing Pursue, Not relevant, Submitted and Dismiss, each with its word; choosing one records it. When the call has no pursuit, the menu adds Pursue and start the draft, which records Pursue and opens Start the draft (P6). Add a note opens an optional note (up to 2,000 characters). |
| Q10 | After a vote the call leaves the voter's queue. The notice reads, for example, Pursue: PY26.2 TACFI Notice of Opportunity. It has left your queue. See everyone's votes on All calls, with that last part a link to the call on All calls. |
| Q11 | Empty states: No calls match these filters, Nothing waiting for you, or Nothing waiting for a decision, each with a line on when new calls arrive. |
| Q12 | Pages have no lead line (N2): the Needs review card's description says whose calls it holds, and V6 says how several people's decisions combine. |
| Q13 | Description column before the AI reason on every Calls view: the call's description, first 300 characters, up to four lines, in full on hover and on keyboard focus. Text the scanner wrote, not the portal (AFWERX, SpaceWERX, APFIT and the first sentence of NASA Forecast rows), is labelled Scanner summary. A members-only page says Members only. Hidden below 1280px; Table settings can hide it. |
| Q14 | Your decision status in the Decide cell. On a call in the queue that you have not decided, the Decide button has an accent border. In views that mix calls you have and have not decided (Top 10 and All calls), it also shows a needs your decision badge, with due today or due in N days on its own line under it when the call closes within 14 days. Once you decide, that badge becomes You: and your decision, with its time, and the button reads Change. Views that hold only calls waiting for you (Needs review, Due soon, Judges agree, Judges disagree, New this week) show no badge. The row itself is not tinted. |
| Q15 | Clicking a row in Home's Top 10 (outside its links and buttons), or Enter on the focused row, opens Calls, Top 10 with that call scrolled into view, marked with an accent bar and its reasons panel open. Calls, Top 10 lists all ten calls, decided or not. |
| Q16 | Every table's body rows lighten on hover. |
| Q17 | On a pursued call with no pursuit, the Decide cell shows Start the draft (P6); on a call with a pursuit, Open workspace with its current step. |

## Calls: All

All calls (/calls) lists every call the scanner has seen, the filter's rejects included, newest first, 200 at a time. Its columns, in order: Call, Filter, Votes, Description, AI reason, Due, First seen (hidden by default), Decide.

| ID | Requirement |
| --- | --- |
| C1 | A lead line: Showing N of M, Narrow the filters to see the rest when there are more, and how often Claude and Grok agree. |
| C2 | Filter cell: kept, rejected or pending as a badge, the tier (broad tier, tight tier), and for a rejected call the reason (no keyword match, or the blocklist pattern that matched). |
| C3 | Claude / Grok cell: both verdicts with both reasons behind why toggles, and the same disagreement flags as the queue. |
| C4 | Decision cell: the call's decision as a badge, or undecided. With one decision, who made it and when; with several, each person's decision and time, flagged people disagree when one said yes and another no. |
| C5 | Decision control in the same cell, labelled decide (undecided), change (your own decision) or add yours (someone else's): a decision select, an optional note, and Save. |
| C6 | Notes cell: every note on the call with its author and time. Notes come from the dashboard and from Slack thread replies. |
| C7 | Changing a decision here changes the call's decision; the newest change wins on the call, and every person's decision is kept. Add yours keeps both. |
| C8 | A form that is out of date writes nothing: if someone decided or changed the call after the page loaded, the page says what the call is now. |

## Draft and submitted badges

A call being worked or submitted says so wherever it appears (27 Oct).

| ID | Requirement |
| --- | --- |
| DB1 | Wherever a call appears (Home's Top 10, every Calls view, every Proposals view), a call with a pursuit shows a badge on its own line under its details: draft started, step N while it is being worked, or draft finished once it reaches the Submit gate. |
| DB2 | A submitted call shows submitted and its date instead, wherever it appears. |
| DB3 | The badge is a button that opens a menu: View the draft (or the submission) in Google Drive, View in Proposals, and one line saying who owns it and its step, or who submitted it, when, and when the result is expected. |

## Proposals

Proposals follows a call from Pursue to its result: five view cards (P1), the Start the draft dialog (P6) and the proposal workspace (section Proposal workspace).

| ID | Requirement |
| --- | --- |
| P1 | Five view cards: Closing in 14 days, To draft, Drafting, Submitted and waiting, Results. The filter bar (portals, tag, open or closed) and a sortable key column work as on Calls. |
| P2 | To draft: pursued calls that are still open and have no pursuit, nearest deadline first, each with Start the draft. A call that cannot be drafted says why in place of the button: closed, or needs the solicitation first (a members-only page the worker cannot read). |
| P3 | Drafting: each pursuit with its current step, its state in words (working, ready for the owner, failed), the owner, Open workspace and the Drive folder. |
| P4 | Submitted and waiting: who submitted it and when, the confirmation number, days waiting and the result expected by date: the date Discovery found in the call for when results are announced, with its source, or 90 days after the deadline when the call does not say. The owner can change it at the Submit gate. Once that date passes the row says result overdue. No news yet moves the date 30 days on. Record result: Won, Lost, Withdrawn or Cancelled by the agency, with an optional debrief note and an optional What to do differently next time, which Results shows and the next alignment check reads; the call moves to Results. |
| P5 | Results: results recorded here and past submissions from the Proposal Register, with win rate by portal. |
| P6 | Start the draft opens a dialog: the format read from the call's type (changeable when the call allows more than one), user approval required (every step, or key gates only), the owner (the viewer), the deadline, optional people to work with (PW24), an optional direction, and optional past work to build on. Its Start button is the person's approval to spend, since a draft takes 20 to 60 minutes and costs money. It creates the Drive folder and starts Discovery. A second pursuit of the same call, or a call marked Not relevant, is refused with the reason. |
| P7 | Two workspace actions record the call's decision, through the same guard as All calls (C8): Mark submitted records Submitted, and No-go records Not relevant with its note. Choosing Submitted in a Decide menu on a call with an open pursuit opens its Submit gate instead. |
| P8 | Starting a draft needs the worker (build-plan, Worker). Until it exists, Start the draft says Drafting is not set up yet. |

## Proposal workspace

One page per pursued call, where Claude does each step's work and the owner approves it (27 and 28 Oct). The step names and order are the contract; the worker builds each step from the `drafting/` phases (handoff/docs/build-plan.md, Steps).

| ID | Requirement |
| --- | --- |
| PW1 | The workspace is a page at /proposals/{call id}: a header (logo, title, portal, format, deadline, owner, approval mode, Drive folder link, then Checklist from step 4 and Show history at the far right), and a stage strip: Qualify, Plan, Draft, Review, Finalize, Submit. |
| PW2 | A step list on the left with each step's state in words: waiting, working, ready, done, failed. Any done step opens read only. |
| PW3 | The steps, in order: 1 Discovery, 2 Opportunity summary, 3 Alignment, 4 Requirements and checklist, the Go or no-go gate, 5 Outline, 6 First draft, 7 Compliance check, 8 Reviews, 9 Final checks, then the Submit gate. |
| PW4 | The open step shows what it is for, what Claude prepared (its file in Drive and the key points), the question for the person, and its actions: Approve and continue, Ask for changes (with a note; Claude redoes the step), Add material, and on steps 1 to 4 Stop here, no-go. Button colours follow their function on hover: green to approve, blue to change or add, red to stop. |
| PW5 | With key gates only, steps other than Go or no-go, Outline and Submit are approved automatically when Claude finishes them, and the history says so. |
| PW6 | Discovery lists its tasks with their state: re-check the call page, download every attachment, find the parent instructions, pull out the key facts (including when results are announced, for P4), compare with past work (starting from Builds on), check for clashes, bring in the dashboard's record, write the Discovery summary. Anything behind a login is listed for the owner to fetch. |
| PW7 | Opportunity summary gives the call's full description and key facts, with Continue to Alignment. |
| PW8 | Alignment gives a verdict and how the call aligns for Velocity (both judges' reasons, people's notes, the past work), with the owner's direction beside Claude's proposed angle. The owner keeps theirs, takes Claude's or writes a new one; the result carries forward, shows again at the Outline, then locks. |
| PW9 | Requirements and checklist lists the volumes, evaluation, eligibility and keywords, and creates the submission checklist in six parts: registrations and eligibility, required documents and volumes, inputs needed from the owner and the team, formatting and packaging, reviews and approvals, submission (fewer for an RFI or white paper). Each item is specific to the call, cites its source, and has an owner and a due date; items already met start ticked. The step also sets an internal submit-by date one business day before the deadline, with the milestones worked back from it, and lists the questions for the government and the source documents. The checklist is tickable from the Checklist button from then on. |
| PW10 | Go or no-go shows Claude's decision brief: fit rating (Strong, Moderate, Stretch or Poor fit), win themes, critical gaps with how to address each, effort and timing against the milestones, and a recommendation. The owner chooses Go; Go with conditions, where each condition (one per line, at least one) joins the checklist as an item they own; or No-go, which needs the reason and what would change the answer, saves a decision note, records Not relevant (P7) and moves the call's folder to Submissions/_no-go/. |
| PW11 | Outline lists the sections with the criterion each answers and its share of the page limit, and the past work each draws on. Past work can be changed until the Outline is approved; approving locks the direction and the past work. |
| PW25 | The two evaluator passes rate each evaluation criterion in words (Outstanding, Good, Acceptable, Marginal or Unacceptable, or the solicitation's own scale), shown on their rows in Reviews. The leadership pass does not rate the criteria. |
| PW12 | Reviews: the AI slop check runs on every new draft without asking and fixes what it can (PW20 to PW23). Then three Claude passes (an external evaluator, a second evaluator, Velocity leadership) each propose changes, one per row with the text now, the suggestion and why, and Accept, Reject and Edit at the right. The draft is approved once every change is decided. |
| PW20 | AI slop check result, opened from the AI slop check row in Reviews, for the latest scan of the newest draft: (1) the verdict line, for example "Not ready: 1 PERSON WRITES, 2 NEEDS INPUT; band light (provisional)", with the band, its points, its confidence and the word count, the time of the last scan and the draft it ran on; (2) the open placeholders by kind, PERSON WRITES and NEEDS INPUT, each linked to its line; (3) up to five paragraphs to revise first, each linked to its line range; (4) the findings grouped by family, each with its tier, hits, rate per 1,000 words, the family's fix and its findings by line and column, then the tiers with nothing left; (5) the proposal faults in their own list, which do not count toward the band; (6) Check again. A line link opens the scanned text beside the list at that line. |
| PW21 | A draft is Ready when no placeholder is open and the band is clean or light. Below 150 words there is no band; below 300 words the band has low confidence. Until the band lines are calibrated on 20 or more Velocity proposals from 2019 to 2022, every band shows provisional. Submit opens only when the newest draft is Ready. |
| PW22 | Check again queues a scan of the newest draft in Drive. The page shows working with its start time and keeps the last result until the new one is saved. The scan runs in the worker, never in the browser. |
| PW23 | The AI slop check reports writing patterns and their fixes only. No screen, file or message says or implies that a text was or was not written by AI, and none shows a probability of it. |
| PW13 | Final checks shows seven checks with their result in words: formatting, the compliance re-check, the placeholder sweep grouped by type with who provides each, the AI slop check's final verdict with the dash-check, the submission package check (format, names, size limits, markings, PDF fonts and page count), the checklist update, and the final version saved. Then the checklist for the owner to tick. While a placeholder is open the AI slop check says Not ready, Approve and continue is unavailable, and Check again runs the checks once more. |
| PW14 | The Submit gate links to the call's page (Open the call page, at the end of its row), and takes the confirmation number and the result expected by date. Mark submitted ends the workflow (P7); the call waits in Submitted and waiting. |
| PW15 | While Claude works a step, the step says so with its start time and asks nothing; Slack tells the owner when it is ready. A failed step says why, with Retry. |
| PW16 | Show history lists each event with its time and who: started, each step saved, approved or redone, the gate decisions, submitted. |
| PW17 | Only the owner sees the approve, change and gate actions and decides the reviewers' changes; everyone else sees the step with a line saying it is waiting on the owner. Enforced once Google sign-in is live (PRO-477). |
| PW24 | A pursuit has one owner and any number of people working with them, chosen at Start the draft or from People in the workspace header (only the owner changes the list). People working on it can add material and Builds on, tick checklist items, and get the step ready and behind Slack messages; the header lists them after the owner, and Show history records each change. |
| PW19 | Each pursuit has a spending cap, $200 by default. When the next step would pass it, the worker stops and the step says budget reached, with Raise the cap for the owner. The header shows what has been spent. |
| PW18 | Slack, in the call's thread: a step is ready, a step is behind its target (targets worked back from the internal submit-by date, PW9), and a daily 08:00 digest per owner of steps waiting on them. A call with no Slack card gets one posted when its pursuit starts. |

## Details, tags and badges

Under each title sit two lines: the details line (the portal, then facts the portal gives) and the tags line. Both must stay scannable at a glance; triage depends on them.

| Portal | Details shown | Badges and links |
| --- | --- | --- |
| Every portal | The type, unless the portal name already ends with it (no NASA Forecast Forecast); the office | closed (grey) when the portal flags the call closed |
| SAM.gov | The agency path shortened to its sub-tier (DEPT OF THE ARMY), the whole path on hover; set-aside; NAICS; solicitation number; first contact; attachment count | Contact name linked to its email |
| NASA Forecast | Expected solicitation quarter (award quarter on hover); estimated value; first contact | A contact whose address names someone else shows the name and the address apart, so a click never emails the wrong person |
| NSTXL | Consortium (SpEC, S2MARTS) | members only (amber), dropped when the Members only tag shows |
| SSC Front Door | Event location | also on SAM.gov, linked, when it reposts a notice |
| AFWERX, SpaceWERX |  | One badge per service whose topics the cycle includes (blue); opens 28 Oct (amber) until submissions open, the pre-release date on hover |
| DOE SBIR |  | upcoming (amber) |
| Space Florida | Document count, linked to the first document, every name on hover | intent to award (amber) |

Set-aside wording: NASA's To Be Determined reads set-aside to be determined. A detail that repeats a shown tag is left out.

Tags (PRO-556, PRO-557):

- Four groups: Type (exactly one per call), Work, Customer and Access (any that apply).
- Type: White paper, Proposal, RFI, OTA, SBIR or STTR, Prize challenge, Demo or exercise, Event, Forecast, Other.
- Work: Software, Hardware, AI and ML, Autonomy, C2, Space, ISR, Cyber, Communications, Data and analytics, Training and simulation, Test and evaluation, Services.
- Customer: USSF, USAF, Army, Navy, USMC, SOCOM, DIU, OSD, Intelligence community, NASA, DOE, Other buyer.
- Access: Members only, Small business set-aside, Phase II holders only, Sponsor needed.
- Display: the type first in blue, then the rest in the list's order in grey; a tag no longer on the list goes last.
- The type shown is the one the call's own data sets, else Claude's, else Grok's.
- Hover says who set each tag (the call's data, Claude, Grok); on the type it also names any other type a judge picked.
- Calls in the queue carry 3 to 15 distinct tags, 6.5 on average (all calls: 2 to 15, 4.8 on average), so the tags line often wraps to two or three lines.

Tone meanings, used across badges: green = good or yes or pursue, amber = caution or maybe or not open yet, red = conflict or no, blue = information (the type, a service, submitted), grey = neutral or closed.

## Filters, sorting and links

Filters that span the whole table sit in a bar between the metric cards and the table; a column's own filter and its sort live in its header, so no control appears twice (PRO-558).

| ID | Requirement |
| --- | --- |
| F1 | The bar holds title search (All calls only, applied on Enter), a Portals menu, a Tag menu, an All / Open / Closed switch, and Clear filters when any filter or a non-default sort is set. |
| F2 | Portals menu: one checkbox per portal that has completed a scan, with its number of stored calls; a portal with none is greyed and shows 0 (PRO-563). None ticked shows every portal. It applies when the menu closes if a box changed, and has an Apply button too. |
| F3 | Tag menu: Any, then the tags grouped as Type, Work, Customer, Access. |
| F4 | Clicking a column's name sorts by it; a second click reverses it. An arrow marks the sorted column, which also carries aria-sort. |
| F5 | Each column starts in its natural direction: First seen newest first, Due closing soonest (upcoming first, then undated, then past), Call A to Z, Claude / Grok yes first, Tier tight first, Decision pursue first, Filter kept first. The default is newest first. |
| F6 | Sortable: Claude / Grok, Call, Due, Tier, First seen on the queue; Call, Filter, Claude / Grok, Decision, Due, First seen on All calls. Free-text columns do not sort: AI reason, Notes, Decided so far, Decide. |
| F7 | Header filters open from a small button beside the name, highlighted while set: Claude / Grok (Claude's verdict, and whether the judges agree or disagree), Tier (queue), Filter (All calls), Decision (All calls, including undecided). |
| F8 | Under judges disagree, calls where one said yes and the other no come first, whatever the sort. |
| F9 | Every choice applies at once. One menu is open at a time; a click outside or Escape closes it. |
| F10 | Every view is a link that can be shared: portal, state, tag, judges, verdict, tier, filter_result, status, q, sort and dir are URL parameters, defaults left out. Old links (?sort=newest, ?sort=due, ?open=1) still work. |
| F11 | Deciding returns to the same view, filters and sort included. |

## Deciding

There is no login until the dashboard is hosted behind Google's sign-in (PRO-477); until then the account menu says who is deciding, and every person's every decision is kept.

| ID | Requirement |
| --- | --- |
| V1 | Deciding as: the account menu shows who is deciding. Until Google sign-in is live, its Switch user list holds the other allowed people (DASHBOARD_USERS), with a line saying why; choosing one applies at once, with no Set step (PRO-553). |
| V2 | Log out in the account menu clears the choice, as Clear User Selection does today; behind Google's sign-in it signs the person out. |
| V3 | With one allowed person the menu has no Switch user list. Behind Google's sign-in it shows the signed-in person, or that the account cannot decide. |
| V4 | Deciding with nobody chosen refuses with: Log in (top right) before deciding. |
| V5 | Decisions are Pursue, Not relevant, Submitted and Dismiss. Pursue and Submitted count as yes, Not relevant and Dismiss as no, when scoring the judges. |
| V6 | On the queue, the first decision becomes the call's decision; later ones are added beside it without changing it. A call's decision changes from All calls, and from the workspace's Mark submitted and No-go (P7). |
| V7 | Every decision is kept per person, with its note and time, so the judges page can score each judge against each person. |
| V8 | Notices after an action show at the top of the page: green for done, red for refused, with what happened in one sentence. |
| V9 | Slack informs and never decides: each run posts a card per new yes or maybe call, card threads become notes, and cards are edited to show the decision made here. |

## Settings

Table settings, in the account menu and beside the filter bar, opens a dialog where each person chooses which columns the review queue and All calls show (PRO-555, PRO-557).

| ID | Requirement |
| --- | --- |
| S1 | One list per table, in column order, each column a checkbox. Needs review's list also sets the details under the title, the AI reason box and the note box; All calls has its own list. |
| S2 | Call and Decide (Decision on All calls) always show: ticked, disabled, marked always shown. |
| S3 | Tags under the title is a choice on both tables, shown by default. |
| S4 | Defaults: everything shows except Tier. |
| S5 | Save keeps the choice for this browser; Reset to defaults clears it; Cancel closes without saving. |
| S6 | The tables render without the hidden columns, so hidden columns give their width to the rest. |

David's broader idea for Table settings, not built: more choices than columns, such as which detail fields show. Profile settings are a separate page (section Account menu and profile).

## Account menu and profile

The account menu at the right of the top bar is each person's own corner: who is deciding, their settings, and signing out (26 Oct).

| ID | Requirement |
| --- | --- |
| U1 | The menu opens from the person's initials and name, with Deciding under the name. It holds the name with Decisions are recorded as you, Profile settings, Table settings, Switch user (until Google sign-in, V1) and Log out (V2). |
| U2 | Profile settings is a page at /profile: display name and initials (shown on votes, notes and the account menu) and, after Google sign-in (PRO-477), the account signed in with. |
| U3 | Where the dashboard opens: Home (the default) or Calls (Needs review). Opening / takes the person there. |
| U4 | Default filters for Calls: portals, tags and open or closed, applied when Calls opens with no filters in its address; a shared link's own filters still win (F10). |
| U5 | Time zone: every time and converted deadline (T1, T2) shows in the person's zone in place of the dashboard's America/Denver. |
| U6 | Profile settings are kept in the ledger, one row per person (a `profiles` table), so display names and initials show to everyone on votes and notes and settings follow the person across devices (David, 28 Oct). |
| U7 | Signed out, the dashboard opens its own sign-in page at /login: the Velocity mark and BD Team, Sign in with Google, Reset password (Google's account recovery) and Need access? Ask an admin. There is no Create account: an admin adds people. Messages in words: signed out, timed out, not allowed (a Google account not on the list), cancelled. Log out returns here. Dark only, no theme switch. |

## Layout and responsiveness

The pages use the window's full width with fixed 24px side margins, and tables wrap their text rather than hide columns (PRO-552).

| ID | Requirement |
| --- | --- |
| L1 | The top bar and the content keep exactly 24px on each side; there is no maximum width, so on wide screens the content reaches the margins. |
| L2 | No page scrolls sideways at widths from 1024 to 2560px, and no table hides columns behind a sideways scroll there. Below 1024px a table may scroll inside itself. |
| L3 | Text wraps to fit. A date breaks before its time, never inside the date. Long unbroken text (an email, a blocklist pattern) may break anywhere rather than widen its column. |
| L4 | Today's minimum column widths: Call 11rem, AI reason 12rem, Decide 12rem, date cells 7rem. They are tuning, not requirements. |
| L5 | The filter bar wraps onto more lines on a narrow window; header menus open over the table. |
| L6 | Dark only: there is no light theme and no theme switch (28 Oct). |
| L7 | Desktop first. Tested widths are 1024 to 2560px; phones are not a target yet. |

Rows are tall today: a queue row stacks two judge badges, a three-line title, a details line, two tag lines, a five-line reason and a note box with four buttons. Making rows denser without losing what triage needs is the main open design question.

## Formats and empty states

Every time shows in the dashboard's zone, America/Denver by default, while deadlines a portal wrote as text stay as written.

| ID | Requirement |
| --- | --- |
| T1 | Times: 2026-10-24 05:54 MDT (date, 24-hour time, zone). |
| T2 | Deadlines written as ISO timestamps (SAM.gov, DIU) convert to the dashboard's zone. Deadlines a portal wrote as text (30 OCT 2026 : 21:59 MDT) and bare dates (2026-11-25) show as written. |
| T3 | Hovering a deadline says where it came from when the portal says: NSTXL's or DOE's sentence (From the page: ...), DIU's own wording. |
| T4 | An empty deadline says why in a word or two, the whole reason on hover: forecast (NASA, with its expected quarter), members only (NSTXL, sign in to see it), see documents (NSTXL, deadline only in the documents), no close date (AFWERX, SpaceWERX, DOE: TBD or continuous), set by sponsor (APFIT). |
| T5 | NASA quarters read Q3 FY2026, or FY2026 alone while NASA has not set the quarter. |
| T6 | Values as the portal gives them: $1.1M - $2M, NAICS 541715, 2 attachments, 1 document. |
| T7 | Every page has an empty state that says what is missing and why, for example the ledger has no calls yet, or a migration is not applied yet. |

## Accessibility and writing rules

Today's accessibility basics stay, and the dashboard's words follow David's writing rules.

| ID | Requirement |
| --- | --- |
| A1 | The sorted column carries aria-sort; header filter buttons are labelled (Filter Claude / Grok); the search box, the account menu and note boxes have labels. |
| A2 | Notices use role=status, errors role=alert. Escape closes an open menu or the Settings dialog. |
| A3 | Every control is a link, button or form field, reachable by keyboard. |
| A4 | Much secondary information lives in hover text today (a deadline's source, a tag's author, a contact's address). A redesign should keep it reachable without a mouse. |
| A5 | Badges never carry meaning by colour alone: the word (yes, members only, judges disagree) is always written. |
| W1 | No en dash or em dash anywhere in the interface. Use a comma, a colon, parentheses, a plain hyphen, or the word to for ranges. |
| W2 | Plain, specific labels in sentence case; decisions are verbs or states (Pursue, Not relevant, Submitted, Dismiss). No emoji as decoration. |
| W3 | Messages say what happened and what to do next in one sentence, for example Log in (top right) before deciding. |

## Build constraints

A design must be buildable in the current stack and architecture; these are fixed unless the team decides otherwise.

| ID | Constraint |
| --- | --- |
| B1 | Next.js 16 (App Router) with React server components. Pages render on the server on every request, reading the ledger (Postgres on Supabase) directly; there is no API layer. |
| B2 | Filters and sort are URL parameters, so every view is a plain link. Writes are server actions: decide, approve or reject a request, choose or clear the viewer, save or reset Table settings, save Profile settings, and, once the drafts queue exists, request, cancel or retry a draft. |
| B3 | Client-side code stays small: today only the picker (to become the account menu), the Settings dialog and the menu behaviour run in the browser. |
| B4 | Cookies: bd_viewer (who is deciding, until Google sign-in) and bd_columns (Table settings). Profile settings live in the ledger (U6). |
| B5 | The dashboard reads only the ledger, never another component's files (AGENTS rule 1). The tag list, for example, reaches it through the tag_list table. |
| B6 | Sign-in is Google, inside the dashboard: its own /login page (U7), limited to the company domain and DASHBOARD_USERS (David, 28 Oct). IAP is no longer planned; the hosting itself is PRO-477, and the container from PRO-511 still applies. |
| B7 | Tests: unit tests (node --test) for the display logic, and Playwright browser tests for layout widths, Settings, the picker, and the filter bar and headers, run against a dashboard. A redesign keeps the behaviour those tests check; their selectors can follow the new markup. |
| B8 | The repository is public: no login-gated portal content, CUI or credentials in code, fixtures or screenshots. |
| B9 | The look comes from the app theme in handoff/velocity-theme (tokens-app.css, card.css and a guide per component), extended from the slide theme. Tone meanings map onto its good, caution, conflict, info and neutral tones. |

## Velocity Theme fit

The [Velocity Theme](velocity-theme/README.md) design system was built on 7 Oct from a Velocity slide deck, so it is a dark slide system; the dashboard needs it extended to app components.

What it gives: near-black ground (#1E1E1E) with surface #262626, ink #F5F5F5 down to muted #757575, one yellow accent (#FFCB03), Inter Tight for reading and Chakra Petch for labels, counts and codes, square corners (2px cards, 1px chips), 2px line borders, no shadows, and components StatTile, Tag, Card and the slide layouts. Sizes are set for a 1920x1080 slide; on the web they halve.

| Theme rule | What the dashboard did before the redesign | Decided (27 and 28 Oct) |
| --- | --- | --- |
| No table, form field, button, menu, dialog, top bar or notice components | Uses all of them on every page | The app theme defines them (handoff/velocity-theme/components) |
| The palette has no status colours; say status in words | Colours verdicts, disagreement and caution (green, amber, red, blue, grey), always with the word written | Five tones (good, caution, conflict, info, neutral), each always with its word |
| Dark ground only | Follows the system's light or dark setting | Dark only (L6) |
| One accent, filling at most one block per slide | Highlights the active page, the sort, set filters and the type tag | The accent marks what needs you, the current selection and focus; never a status |
| Dates as 21 July 2026 | 2026-10-24 05:54 MDT; deadlines as each portal wrote them | A date format for tables, where width is tight |
| Titles in Title Case | Labels and titles in sentence case | Sentence case everywhere; caps only through CSS |
| Ranges with an en dash (in the original theme) | David's rule: no en or em dash anywhere | Decided: write ranges with to; the copy in velocity-theme/ already does |
| No icon set | Uses arrows for sort and a small triangle for menus | Lucide icons in the top bar and on buttons |

## Data per call

Each call is one row in the ledger's calls table, with its judgments, decisions, notes and tags beside it; a design can show any of these.

| Field | What it holds | Shown today |
| --- | --- | --- |
| title, url | The call's name and its page on the portal | Call (linked title) |
| portal | One of the 11 portals | Details line |
| type, department | The portal's own type and the issuing office | Details line |
| naics_code, set_aside | Where the portal gives them (SAM.gov, NASA) | Details line |
| due_date, posted_date | The deadline as the portal wrote it; the posting date | Due; posting date not shown |
| description | The call's text, up to 1,500 to 4,000 characters depending on the portal (handover-discovery, question 12) | Description column (Q13) |
| first_seen_at | When the scan first saw the call | First seen |
| filter_result, filter_reason, match_tier, matched_keywords | The keyword filter's outcome, its reason, tight or broad, and the keywords that matched | Filter column, Tier; keywords not shown |
| ai_verdict, ai_reasoning | Claude's verdict and reason, which decide what Slack posts | Claude / Grok, AI reason |
| judgments | Each judge's newest verdict and reason (claude, grok) | Claude / Grok |
| human_status, human_by, human_at, human_notes | The call's decision, who made it, when, and every note | Decision, Notes |
| decisions | Every person's decision with its note and time | Decided so far, Decision |
| call_tags | Each tag with who set it (rule, claude, grok) | Tags line |
| extra | Portal fields: closed flag, contacts, attachments, documents, services, open and pre-release dates, deadline sentences, members-only flag | Details line, badges, due hover |

The other tables behind the other pages: briefs (past weekly briefs), change_requests (Automation, Requests, and Home's status line), runs (Automation, Scans, and Home's status line), proposals (Proposals, Results), tag_list (the Tag filter).

## Not built yet and open questions

Shaun's column list (BD Automation Review, Columns) asks for fields the dashboard does not show yet; a redesign should leave room for them.

| Item | Status |
| --- | --- |
| Fit score, 0 to 100 with its parts | Formula proposed and trialled on 20 Oct; weights wait on Shaun |
| Effort: small, medium or large | For a bandwidth planner; not started |
| Matched keywords on the queue | Stored (matched_keywords), not shown |
| A Drive folder link for attachments, filled when a call is marked Pursue | Not started |
| Parsed dates for sorting across portals | Partly done: Due sorts across the portals' two date formats |
| Standard opportunity type, category tags, open or closed | Done: the Type tag, the tags, the closed badge and filter |
| Recording won or lost for a submitted call | Not started; Results reads the Proposal Register until then |
| Linking Proposal Register rows to calls | Not started: the Register has no call id |
| Profile settings that follow a person across devices | Needs Google sign-in (PRO-477) and a ledger table (U6) |
| The Draft button and draft progress on Pursuing | Needs the drafts queue and worker (Draft-Ready Upgrade U1, Writer Plan W2a), a schema change (P8) |

Open questions for the design:

- [x] How dense should a row be, and what can fold away (the AI reason, the tags, the details) without slowing triage? One Votes column, a four-line description, and panels for reasons and notes (handoff).
- [x] How should hover-only information reach keyboard and touch users? Tooltips show on keyboard focus too (handoff).
- [x] What fits on Home at 1440px without scrolling, and in what order? Five link cards, the Top 10, a status line (H1 to H5).
- [x] How should Proposals, Automation and the past weekly briefs look in the design system? Designed in the handoff.
- [ ] Final column list: Shaun's decision (Decisions, BD Automation Review).

## Current UI

The redesign is in the [handoff package](handoff/README.md) of 28 Oct, with screenshots of every screen in handoff/screenshots; the build follows [redesign-plan.md](redesign-plan.md). The snapshot below is the dashboard before it.

The [BD Dashboard Snapshot](dashboard-snapshot/README.md) is a working copy of all seven pages as of 25 Oct, with their real markup and styling, plus ten screenshots. It shows the pages from before the 26 Oct restructure: Home has no page there, and the Monday brief is the closest to it. The code is in [dashboard/](../../dashboard/) in this repo.

- Data: the 122 calls from public portals. Vulcan SOF is left out because its pages sit behind a login.
- Samples: decisions by Analyst A and Analyst B, two proposals and two change requests, to show decided and waiting states.
- Static: links between pages work, menus open and Settings opens; nothing saves.
- The live dashboard is not on the web: it reads the live ledger, records decisions, and has no sign-in until hosting (PRO-477).

![Review queue at 1440px: metric cards, the filter bar, then rows with both judges' verdicts, details, tags, Claude's reason and the decide buttons](dashboard-snapshot/screens/queue-1440.png)

![All calls with the Claude / Grok header menu open: Claude's verdict and whether the judges agree; Due sorted closing soonest](dashboard-snapshot/screens/calls-header-menu.png)

## Decision log

Every decision that shaped the dashboard, newest first.

| Date | Decision | Ticket |
| --- | --- | --- |
| 28 Oct | The app is BD Team; sign-in is Google inside the dashboard, with IAP dropped; Profile settings are kept in the ledger per person; the handoff package is committed to docs/design/handoff | PRO-566 |
| 28 Oct | From the complete skills: a six-part submission checklist with an internal submit-by date; a decision brief with Go with conditions at go or no-go; seven final checks. Submitting stays with the owner on the portal | PRO-566 |
| 28 Oct | One owner per pursuit, with people working with them; Lisa and Alec added as decision makers; the result expected by date is researched in Discovery, else 90 days after the deadline | PRO-566 |
| 27 Oct | View cards replace tabs and page titles in every section; Home becomes five link cards and the Top 10 table | PRO-566 |
| 27 Oct | The proposal workspace: a step-by-step page per pursued call, Claude doing each step and the owner approving each step or only key gates | PRO-566 |
| 27 Oct | Draft and submitted badges on a call wherever it appears; a draft can start from any row once the call is pursued | PRO-566 |
| 27 Oct | Submitted and waiting tracks a result expected by date, with No news yet and Record result (won, lost, withdrawn, cancelled by the agency) | PRO-566 |
| 27 Oct | A Description column on the Top 10 and Calls tables | PRO-566 |
| 26 Oct | The Portals menu lists every portal that has scanned, with its call count, so a portal with nothing open no longer looks missing | PRO-563 |
| 26 Oct | Pursuing splits into Ready to draft, with a Draft button per call, and Drafting, with progress and finished drafts; a call is ready when it is pursued, still open, without a draft and with readable solicitation text | PRO-562 |
| 26 Oct | The fourth section is Automation, not Admin, with tabs Requests, Scans (today's Runs) and Judges; an account menu replaces the Deciding as picker and the Settings button, with Profile settings (name, where the dashboard opens, default filters, time zone); deciding on To review uses a Decide menu in place of four buttons | PRO-561 |
| 26 Oct | Seven pages become four sections: Home (a new landing page in place of the Monday brief page, whose weeks stay at /brief), Calls (To review and All), Proposals (Pursuing, Submitted, Results) and Admin (Requests, Runs, Judges); submissions waiting on a response come from calls marked Submitted | PRO-560 |
| 24 Oct | The left filter panel became a bar above the table; column headers sort and filter; choices apply at once, the Portals menu on close | PRO-558 |
| 24 Oct | Tags show under each title, type first in blue; a Tag filter; Settings can hide them | PRO-557 |
| 24 Oct | A tag list in four groups, one type per call; rules, Claude and Grok tag; the customer catch-all is Other buyer | PRO-556 |
| 24 Oct | A Settings dialog chooses each table's columns per browser; Tier hidden by default; Call and Decide always show | PRO-555 |
| 24 Oct | After a vote, the notice says the call left your queue and links to everyone's votes | PRO-554 |
| 24 Oct | Choosing a name applies at once; Set became Clear User Selection | PRO-553 |
| 24 Oct | Pages fill the window with fixed 24px margins; no sideways scroll or hidden columns from 1024 to 2560px | PRO-552 |
| 24 Oct | A contact naming someone else shows name and address apart; set-aside to be determined; empty deadlines say why; no repeated type | PRO-551 |
| 24 Oct | Details for the DOE, NASA, Space Florida and APFIT rows | PRO-549 |
| 24 Oct | A cycle's open date and its services on AFWERX and SpaceWERX rows | PRO-542 |
| 23 Oct | Each portal's details on the call rows; ISO deadlines in the dashboard's zone | PRO-535 |
| 21 Oct | A container for hosting, with Google sign-in through IAP | PRO-511 |
| 21 Oct | The Monday brief on the dashboard, with a Top 10 across portals | PRO-492 |
| 20 Oct | Everyone decides every call in the queue while the judges are trained | PRO-508 |
| 20 Oct | Claude and Grok scored against each person's decisions | PRO-501 |
| 20 Oct | Each judge's verdict kept and shown side by side | PRO-500 |
| 20 Oct | A filter panel with portals, open or closed and closing soonest (replaced by PRO-558) | PRO-488 |
| 17 Oct | Decisions move to the dashboard; Slack cards show them and reactions are no longer read |  |
| 17 Oct | An approval queue for the portal assistant's change requests |  |
| 17 Oct | The Next.js triage dashboard over the ledger |  |
