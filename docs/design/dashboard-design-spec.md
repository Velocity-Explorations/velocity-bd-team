# BD Dashboard Design Spec

25 Oct 2026, David

Every requirement and decision behind the Velocity BD triage dashboard as of 25 Oct 2026, written as a brief for redesigning it in the Velocity Theme design system. A redesign keeps every requirement here; how each one looks is open.

## Purpose and users

The dashboard is the one place Velocity's BD team decides which government opportunities to pursue. Slack posts a card per promising call and carries the discussion; it never records a decision.

The loop it serves, every week:

1. Sunday 22:00 the pipeline scans 11 portals (Vulcan SOF, SSC Front Door, SAM.gov, NSTXL, DIU, AFWERX, SpaceWERX, DOE SBIR, NASA Forecast, Space Florida, APFIT).
2. A keyword filter keeps likely fits. Claude (claude-haiku-5-5) rates each kept call yes, maybe or no with a one-sentence reason, and Grok (grok-4.7) gives a second verdict.
3. Rules, Claude and Grok tag every call from a set list.
4. People triage on the dashboard: Pursue, Not relevant, Submitted or Dismiss, with an optional note. Every decision feeds the next review's prompt and scores the judges.

People: David and Shaun decide today, and more can be added. While the judges are being trained, everyone decides every call, so each person has their own queue.

The jobs, most frequent first:

- Triage the week's new calls quickly, seeing why each was flagged.
- Find calls by portal, tag, deadline or verdict, and revisit a decision.
- See how Claude and Grok compare with each person, and read the Monday brief.
- Approve or reject the portal assistant's change requests, and check scan health.

David's design goal, 24 Oct: use the space effectively. Long reasons, tags, details and up to eight columns compete for width.

## Pages

Seven pages share one top bar. The bar carries the brand (Velocity BD), the seven page links with the current one highlighted, a count badge on Requests when requests wait, the Deciding as picker with Clear User Selection, and the Settings button.

| Path | Page | What it is for | What it shows |
| --- | --- | --- | --- |
| / | Review queue | Triage: decide each call rated yes or maybe | Five metric cards (waiting, yes, maybe, new this week, judges agree %), the filter bar, then one row per call with decide buttons |
| /calls | All calls | Find any call, change a decision, read votes and notes | Every call scanned, rejected ones too, up to 200 rows, with a Showing N of M line |
| /brief | Monday brief | The week as the Monday 9:00 job posted it to Slack | A Top 10 across portals, then a bulletin board per portal: new calls by verdict, calls waiting, top picks, pursued calls closing within 14 days, the week's decisions, the scraper line; each call's decision as of now; earlier weeks linked at the top |
| /judges | Judges | How Claude and Grok compare with people | Per judge: matched, misses, false alarms, maybes; per person: calls decided and how often each judge matched them; between people: agreement; pursued calls a judge said no to |
| /requests | Requests | Approve the portal assistant's change requests | Waiting requests first (who asked, why, a preview of the change, Approve and Reject with a note), then the last 50 decided with their result |
| /runs | Runs | Scan health | The latest run on top (status, start, duration, stage counts, error, log link), then the last 100 runs; a run still running after two hours is flagged |
| /proposals | Proposals | Past submissions and win rate | The proposals table with win rate by portal; an empty state until the Proposal Library fills it |

The queue and All calls get the most use and carry most of the requirements below.

## Review queue

The queue lists the calls Claude rated yes or maybe that the keyword filter kept and the viewer has not decided, newest first, up to 500. Its columns, in order: Claude / Grok, Call, Due, Tier (hidden by default), AI reason, First seen, Decided so far, Decide.

| ID | Requirement |
| --- | --- |
| Q1 | Who is waiting: while everyone decides every call (the default), each person's queue holds the calls they have not decided. In shared mode it holds the calls nobody has decided. |
| Q2 | Metric cards above the table: Waiting (Waiting for you in each-person mode), Yes, Maybe, New this week, Judges agree % with the counts on hover. |
| Q3 | Claude / Grok cell: each judge's verdict as a badge (yes green, maybe amber, no red, not reviewed grey). Grok's reason opens from a why toggle; Claude's reason is the AI reason column. |
| Q4 | Disagreement flags in that cell: judges disagree (amber) when the verdicts differ, and judges: yes vs no (red) when one said yes and the other no. |
| Q5 | Call cell: the title links to the portal's page; under it the details line, then the tags line (section Details, tags and badges). |
| Q6 | Due cell: the deadline in the dashboard's time zone; hover says where it came from; a blank deadline says why in a word or two (section Formats). |
| Q7 | AI reason cell: Claude's one-sentence reason, often 40 to 70 words, the longest text in the row. |
| Q8 | Decided so far (each-person mode only): other people's votes as Name: Decision, nobody yet when none, and a people disagree badge when one said yes and another no. |
| Q9 | Decide cell: an optional note (up to 2,000 characters) and four buttons that record at one click: Pursue (green), Not relevant (grey), Submitted (blue), Dismiss (grey). |
| Q10 | After a vote the call leaves the voter's queue. The notice reads, for example, Pursue: PY26.2 TACFI Notice of Opportunity. It has left your queue. See everyone's votes on All calls, with that last part a link to the call on All calls. |
| Q11 | Empty states: No calls match these filters, Nothing waiting for you, or Nothing waiting for a decision, each with a line on when new calls arrive. |
| Q12 | The page's lead line explains the mode: everyone decides every call while the judges are trained, the first decision becomes the call's decision, later ones are kept beside it. |

## All calls

All calls lists every call the scanner has seen, the filter's rejects included, newest first, 200 at a time. Its columns, in order: Call, Filter, Claude / Grok, Decision, Notes, Due, First seen.

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
| F2 | Portals menu: one checkbox per portal that has calls; none ticked shows every portal. It applies when the menu closes if a box changed, and has an Apply button too. |
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

There is no login until the dashboard is hosted behind Google's sign-in (PRO-477); until then a picker says who is deciding, and every person's every decision is kept.

| ID | Requirement |
| --- | --- |
| V1 | Deciding as: a picker in the top bar lists the allowed people (DASHBOARD_USERS). Choosing a name applies at once; there is no Set step (PRO-553). |
| V2 | Clear User Selection beside the picker removes the choice; it is disabled while nobody is chosen. |
| V3 | With one allowed person the bar just says Deciding as that person. Behind Google's sign-in it shows the signed-in person, or that the account cannot decide. |
| V4 | Deciding with nobody chosen refuses with: Choose who you are (top right) before deciding. |
| V5 | Decisions are Pursue, Not relevant, Submitted and Dismiss. Pursue and Submitted count as yes, Not relevant and Dismiss as no, when scoring the judges. |
| V6 | On the queue, the first decision becomes the call's decision; later ones are added beside it without changing it. A call's decision changes only from All calls. |
| V7 | Every decision is kept per person, with its note and time, so the judges page can score each judge against each person. |
| V8 | Notices after an action show at the top of the page: green for done, red for refused, with what happened in one sentence. |
| V9 | Slack informs and never decides: each run posts a card per new yes or maybe call, card threads become notes, and cards are edited to show the decision made here. |

## Settings

A Settings button in the top bar opens a dialog where each person chooses which columns the review queue and All calls show (PRO-555, PRO-557).

| ID | Requirement |
| --- | --- |
| S1 | One list per table, in column order, each column a checkbox. |
| S2 | Call and Decide (Decision on All calls) always show: ticked, disabled, marked always shown. |
| S3 | Tags under the title is a choice on both tables, shown by default. |
| S4 | Defaults: everything shows except Tier. |
| S5 | Save keeps the choice for this browser; Reset to defaults clears it; Cancel closes without saving. |
| S6 | The tables render without the hidden columns, so hidden columns give their width to the rest. |

David's broader idea for Settings, not built: more choices than columns, such as which detail fields show. Choices could follow each person across devices once sign-in identifies them.

## Layout and responsiveness

The pages use the window's full width with fixed 24px side margins, and tables wrap their text rather than hide columns (PRO-552).

| ID | Requirement |
| --- | --- |
| L1 | The top bar and the content keep exactly 24px on each side; there is no maximum width, so on wide screens the content reaches the margins. |
| L2 | No page scrolls sideways at widths from 1024 to 2560px, and no table hides columns behind a sideways scroll there. Below 1024px a table may scroll inside itself. |
| L3 | Text wraps to fit. A date breaks before its time, never inside the date. Long unbroken text (an email, a blocklist pattern) may break anywhere rather than widen its column. |
| L4 | Today's minimum column widths: Call 11rem, AI reason 12rem, Decide 12rem, date cells 7rem. They are tuning, not requirements. |
| L5 | The filter bar wraps onto more lines on a narrow window; header menus open over the table. |
| L6 | Light and dark themes follow the system setting today (prefers-color-scheme). |
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
| A1 | The sorted column carries aria-sort; header filter buttons are labelled (Filter Claude / Grok); the search box, picker and note boxes have labels. |
| A2 | Notices use role=status, errors role=alert. Escape closes an open menu or the Settings dialog. |
| A3 | Every control is a link, button or form field, reachable by keyboard. |
| A4 | Much secondary information lives in hover text today (a deadline's source, a tag's author, a contact's address). A redesign should keep it reachable without a mouse. |
| A5 | Badges never carry meaning by colour alone: the word (yes, members only, judges disagree) is always written. |
| W1 | No en dash or em dash anywhere in the interface. Use a comma, a colon, parentheses, a plain hyphen, or the word to for ranges. |
| W2 | Plain, specific labels in sentence case; decisions are verbs or states (Pursue, Not relevant, Submitted, Dismiss). No emoji as decoration. |
| W3 | Messages say what happened and what to do next in one sentence, for example Choose who you are (top right) before deciding. |

## Build constraints

A design must be buildable in the current stack and architecture; these are fixed unless the team decides otherwise.

| ID | Constraint |
| --- | --- |
| B1 | Next.js 16 (App Router) with React server components. Pages render on the server on every request, reading the ledger (Postgres on Supabase) directly; there is no API layer. |
| B2 | Filters and sort are URL parameters, so every view is a plain link. Writes are server actions: decide, approve or reject a request, choose or clear the viewer, save or reset Settings. |
| B3 | Client-side code stays small: today only the picker, the Settings dialog and the menu behaviour run in the browser. |
| B4 | Two cookies: bd_viewer (who is deciding) and bd_columns (Settings). |
| B5 | The dashboard reads only the ledger, never another component's files (AGENTS rule 1). The tag list, for example, reaches it through the tag_list table. |
| B6 | Hosting: a container for Google Kubernetes Engine behind Google's Identity-Aware Proxy, which signs people in by email (PRO-511 built it; PRO-477, hosting with Alec, is open). |
| B7 | Tests: unit tests (node --test) for the display logic, and Playwright browser tests for layout widths, Settings, the picker, and the filter bar and headers, run against a dashboard. A redesign keeps the behaviour those tests check; their selectors can follow the new markup. |
| B8 | The repository is public: no login-gated portal content, CUI or credentials in code, fixtures or screenshots. |
| B9 | The Velocity Theme design system supplies the look: colours, type, spacing and components. The tone meanings in Details, tags and badges need a mapping onto its palette. |

## Velocity Theme fit

The [Velocity Theme](velocity-theme/README.md) design system was built on 7 Oct from a Velocity slide deck, so it is a dark slide system; the dashboard needs it extended to app components.

What it gives: near-black ground (#1E1E1E) with surface #262626, ink #F5F5F5 down to muted #757575, one yellow accent (#FFCB03), Inter Tight for reading and Chakra Petch for labels, counts and codes, square corners (2px cards, 1px chips), 2px line borders, no shadows, and components StatTile, Tag, Card and the slide layouts. Sizes are set for a 1920x1080 slide; on the web they halve.

| Theme rule | What the dashboard does today | To decide |
| --- | --- | --- |
| No table, form field, button, menu, dialog, top bar or notice components | Uses all of them on every page | Design them in the theme's language |
| The palette has no status colours; say status in words | Colours verdicts, disagreement and caution (green, amber, red, blue, grey), always with the word written | Add status tones for the app, or rely on words, weight and the accent |
| Dark ground only | Follows the system's light or dark setting | Dark only, or a light variant too |
| One accent, filling at most one block per slide | Highlights the active page, the sort, set filters and the type tag | Where the yellow goes on a working screen |
| Dates as 21 July 2026 | 2026-10-24 05:54 MDT; deadlines as each portal wrote them | A date format for tables, where width is tight |
| Titles in Title Case | Labels and titles in sentence case | Which case for page titles and column headers |
| Ranges with an en dash (in the original theme) | David's rule: no en or em dash anywhere | Decided: write ranges with to; the copy in velocity-theme/ already does |
| No icon set | Uses arrows for sort and a small triangle for menus | Whether the arrows the theme allows are enough |

## Data per call

Each call is one row in the ledger's calls table, with its judgments, decisions, notes and tags beside it; a design can show any of these.

| Field | What it holds | Shown today |
| --- | --- | --- |
| title, url | The call's name and its page on the portal | Call (linked title) |
| portal | One of the 11 portals | Details line |
| type, department | The portal's own type and the issuing office | Details line |
| naics_code, set_aside | Where the portal gives them (SAM.gov, NASA) | Details line |
| due_date, posted_date | The deadline as the portal wrote it; the posting date | Due; posting date not shown |
| description | Up to 1,500 characters of the call's text | Not shown |
| first_seen_at | When the scan first saw the call | First seen |
| filter_result, filter_reason, match_tier, matched_keywords | The keyword filter's outcome, its reason, tight or broad, and the keywords that matched | Filter column, Tier; keywords not shown |
| ai_verdict, ai_reasoning | Claude's verdict and reason, which decide what Slack posts | Claude / Grok, AI reason |
| judgments | Each judge's newest verdict and reason (claude, grok) | Claude / Grok |
| human_status, human_by, human_at, human_notes | The call's decision, who made it, when, and every note | Decision, Notes |
| decisions | Every person's decision with its note and time | Decided so far, Decision |
| call_tags | Each tag with who set it (rule, claude, grok) | Tags line |
| extra | Portal fields: closed flag, contacts, attachments, documents, services, open and pre-release dates, deadline sentences, members-only flag | Details line, badges, due hover |

The other tables behind the other pages: briefs (Monday brief), change_requests (Requests), runs (Runs), proposals (Proposals), tag_list (the Tag filter).

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

Open questions for the design:

- [ ] How dense should a row be, and what can fold away (the AI reason, the tags, the details) without slowing triage?
- [ ] How should hover-only information reach keyboard and touch users?
- [ ] Should the decide controls stay in every row, or move to a side panel or a row action?
- [ ] How should the Monday brief, Judges, Requests, Runs and Proposals pages look in the design system? They follow the queue's look today.
- [ ] Final column list: Shaun's decision (Decisions, BD Automation Review).

## Current UI

The [BD Dashboard Snapshot](dashboard-snapshot/README.md) is a working copy of all seven pages as of 25 Oct, with their real markup and styling, plus ten screenshots. The code is in [dashboard/](../../dashboard/) in this repo.

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
