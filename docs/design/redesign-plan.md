# Redesign: delta and phased build plan

28 Oct 2026 (PRO-565). Compares main at `889e50e` with the Claude Design handoff package of 28 Oct ("Velocity BD Dashboard Redesign.zip"). The package holds:
- the README, which covers every screen;
- the decisions, the spec updates and a 13-PR build plan;
- the working prototype and screenshots;
- the app theme;
- the two proposal skills, as written and adapted to the workspace.

Facts about today come from the code and `docs/design/handover-discovery.md`.

## Summary

- **The package is complete and fits the codebase's rules.** Components still talk only through the ledger, writes are guarded, nothing claims or rates AI authorship, and the slop scanner stays private.
- **This plan keeps the package's build order,** with three changes:
  - it adds a phase 0 for the repo and for setup outside it;
  - it splits the package's two largest PRs;
  - it makes sign-in depend on one open decision.
- **The size of the change:**
  - every dashboard page is rebuilt or new;
  - six ledger tables are added;
  - three backend pieces are new: an always-on worker, Google Drive with Word files, and Slack thread jobs;
  - sign-in is replaced.
- **David's answers, 28 Oct:**
  - the app is called BD Team, in the top bar as on the sign-in page;
  - sign-in is Google inside the dashboard (Auth.js), and IAP is dropped from the PRO-477 plan;
  - Profile settings live in the ledger, one row per person;
  - the whole package goes into the public repo at `docs/design/handoff/`;
  - David sets up Google Cloud, following a step-by-step guide in `docs/RUNBOOK.md`.

## 1. Gaps and inconsistencies inside the package

| # | What | Where | What this plan does |
| --- | --- | --- | --- |
| 1 | The sign-in page says BD Team; the top bar says Velocity BD | README, open item 1 | BD Team everywhere (David, 28 Oct) |
| 2 | Decision 10 and the build plan's Sign-in section put Google sign-in inside the dashboard. The build plan's PR 13, its "Later" note and PW17 still say IAP | decisions.md, build-plan.md | Google sign-in inside the dashboard (Auth.js); IAP dropped (David, 28 Oct). PR 13 becomes phase 11 below |
| 3 | New requirement IDs use two letters (VC, PW, DB), but `tests/test_design_brief.py` reads one-letter IDs | spec-updates.md | Keep the package's IDs and extend the test to one or two letters, so the package's documents stay valid |
| 4 | The new Calls rows are marked "Q (next)" with no number | spec-updates.md, Calls | Number them Q13 to Q17 on merge |
| 5 | H2 says "the best open calls, ranked as the Monday brief ranks them". The prototype reads "From the Monday brief, week of 19 Oct", and Calls, Top 10 "lists all ten calls, decided or not" | spec-updates.md, README, screenshot 01 | Use this week's stored brief list with each call's decision as of now. Rank live only before the first brief exists |
| 6 | U2 shows display names on votes and notes, which other people see, but U6 keeps profile settings in each browser | spec-updates.md, spec U6 | A `profiles` table in the ledger, one row per person (David, 28 Oct); U6 changes on merge |
| 7 | Where the dashboard opens: "Home or Calls" in the README, "Home or To review" in spec U3 | README, spec | "Home or Calls (Needs review)" |
| 8 | "Judges agree" names both a Calls view (waiting calls where the judges agree) and an Automation card (the Judges page) | Pages table | Build as designed; suggest "Judge scores" for the Automation card later |
| 9 | To review has a Tier column (hidden by default); the design's column list does not | README, Calls | Drop the column; All calls' Filter cell still shows the tier |
| 10 | Eight portal logos are supplied; DOE SBIR, Space Florida and APFIT have none | `design/assets/logos/` | An initials tile until logos are supplied |
| 11 | The prompts go in `drafting/prompts/`, but `drafting/prompts.py` already exists. A folder beside it works in Python but reads confusingly | build-plan.md | `drafting/prompt_texts/` |
| 12 | The sign-in page's slate background image is not supplied | README, Assets | The gradient fallback until it is |
| 13 | The AI slop check result was designed from a description; its family names and counts are examples | README, open item 3 | In phase 8, match the labels to the real scanner JSON, run locally; nothing from the scanner is committed |
| 14 | Writing the Register row on submit needs Google Sheets write access as well as Drive | build-plan.md, run.py jobs | Add the Sheets API to the Google setup (section 4) |
| 15 | Log out goes to the sign-in page, which needs Google sign-in | README, Account menu | Until phase 11, Log out clears the chosen name and returns to Home with its notice |
| 16 | `design/proto-data.js` holds the public snapshot's data. Vulcan SOF appears only in run rows and brief boards, never as call text; the NASA contacts are already public. The two runtime files hold 91 dashes, which are not text we write and sit outside the brief's dash test | design/ | Commit all of it (David, 28 Oct) |

## 2. The delta, area by area

"Today" is main at `889e50e`. IDs refer to the spec after the package's updates.

### 2.1 Structure and navigation

| Item | Today | In the package | IDs |
| --- | --- | --- | --- |
| Top bar links | Seven pages: Review queue, Monday brief, All calls, Judges, Requests, Runs, Proposals | Four sections (Home, Calls, Proposals, Automation), each with a Lucide icon; the current one highlighted, with `aria-current` | N1 |
| Counts in the bar | Requests only | Count chips: Calls (waiting for you), Proposals (to draft, plus steps ready for you), Automation (requests waiting), each labelled | N3 |
| Brand | The text "Velocity BD" | The Velocity mark, then "BD Team" in Chakra Petch caps | N1 |
| Who is deciding | The Deciding as picker, Clear User Selection and a Settings button | An account button (initials, name, "Deciding") opening the account menu | N5, U1 |
| Page heads | An h1 and a lead line on each page; five metric cards on the queue | No titles and no tabs: each section opens on a row of view cards, and the pressed card names the view | N2, VC1 |
| Addresses | `/` (queue), `/calls`, `/brief`, `/judges`, `/requests`, `/runs`, `/runs/[id]` (log), `/proposals` | `/` Home; `/review` with views; `/calls`; `/proposals` with views, plus `/proposals/submitted`, `/proposals/results` and `/proposals/[callId]`; `/requests`, `/runs` and `/judges` with views; `/brief`; `/profile`; `/login` | Pages, N4 |
| Old addresses | | Every old path opens its view. `/` changes from the queue to Home | N4 |
| Switching views | One page each | Keeps the portal, tag and open or closed filters; resets column filters and sort to the view's own. A column filter that matches no view leaves no card pressed | N6, VC4 |

### 2.2 Look and components

| Item | Today | In the package | IDs |
| --- | --- | --- | --- |
| Theme | Light and dark, following the system; a blue accent | Dark only. Ground `#1E1E1E`; accent `#FFCB03` marks what needs you, the selection and focus, never a status. Tones good, caution, conflict, info and neutral, each with text, line and wash colours | Tokens |
| Fonts | System UI, plus a monospace for codes | Inter Tight (400, 600, 700) and Chakra Petch (400 to 700), self-hosted | Tokens |
| Icons | None (text arrows) | Lucide: a new dependency (`lucide-react`) | Assets |
| Cards | Plain metric boxes | View cards: a gradient fill; label band, number and description on a shared subgrid; hover lift, pressed bar, focus outline, reduced motion | VC1 |
| Buttons | One style, plus tone colours for decisions | Primary, secondary and destructive. Hover fills by function: green to approve, blue to change or add, red to stop or reject. 32px high, 28px in rows and menus | Tokens |
| Badges and tags | Tone-coloured pills | Badges 18px with a 6px tone square and the word. Tags 20px with a 3px radius, the type first in the info tone | Tokens |
| Menus | `details` menus, one open at a time; an outside click or Escape closes them | Also: focus moves in, arrow keys move between items, and focus returns to the trigger | Interactions |
| Dialogs | The native Settings dialog | A dialog component that keeps focus inside; Escape or Cancel returns focus | Interactions |
| Notices | One line at the top | A bar in the tone's wash, with a word column (Done, Refused, Note), one sentence and at most one link | Notices |
| Tooltips | Native `title` text, mouse only | A tooltip on hover and on keyboard focus | Interactions |
| Hover and focus | Partial | A hover state on every interactive element; 120ms and 140ms transitions; a 2px accent focus outline everywhere | Interactions |
| Breakpoint | Tables wrap from 1024px | At 1280px, Description and Claude's reason hide on Home. On Calls the AI reason folds under the call and Description hides | H2, Q13 |
| Empty states | One sentence | An 8px square, a title, one line saying why, and a way out | Calls |

### 2.3 Home (new)

| Item | Today | In the package | IDs |
| --- | --- | --- | --- |
| The page | `/` is the review queue | Five link cards (Needs review, Due soon, Agent update requests, Proposals to draft, Submitted and waiting), the Top 10 table, a status line and a link to this week's brief | H1 to H5 |
| Top 10 | Only on `/brief` | Rank, logo, title, portal, deadline and days left, Claude, Grok, decision now, description and Claude's reason. Clicking a row opens Calls, Top 10 focused on that call | H2, Q15 |
| Row badges | | Draft or submitted badges with their menus; "Start the draft" on pursued calls with no draft | DB1 to DB3 |

### 2.4 Calls

| Item | Today | In the package | IDs |
| --- | --- | --- | --- |
| Views | Two pages: the queue and All calls | Seven view cards: Needs review, Top 10, Due soon, Judges agree, Judges disagree, New this week, All calls. Their counts follow the filter bar | Pages, VC2 |
| Metric cards | Waiting, Yes, Maybe, New this week, Judges agree % | Replaced by the view cards | VC1 |
| Filter bar | Search (All calls), Portals with counts, Tag, All/Open/Closed, Clear filters | The same, plus a right-aligned count line and Table settings at the end. The search box is 260px: "Search titles, Enter to apply" | Calls |
| To review's columns | Claude / Grok, Call, Due, Tier (hidden), AI reason, First seen, Decided so far, Decide | Call, Votes, Description, AI reason, Due, First seen (hidden), Decide | Calls |
| All calls' columns | Call, Filter, Claude / Grok, Decision, Notes, Due, First seen | Call, Filter, Votes, Description, AI reason, Due, First seen (hidden), Decide | Calls |
| Call cell | Title link, details line, tags line | Adds a 40px logo tile and an external-link icon. Details with a source are focusable and show it in a tooltip. Adds a badges line (draft, submitted, "Top 10, #N") | Calls, DB1 |
| Votes | Claude and Grok badges, Grok's reason behind "why", others' votes in a separate column | One cell: Claude and Grok with note buttons, then each person's latest vote under a dashed rule. "Judges disagree" and "people disagree" show as badges | Calls |
| Description | Stored, never shown | The first 300 characters, up to four lines, in full on hover and focus. "Scanner summary" marks text the adapters wrote; "Members only" marks NSTXL member pages | Q13 |
| Due | The date in the dashboard's time zone | Date, time and days left | Calls |
| Panels | Grok's reason behind a toggle | A Reasons panel (both judges, and where details came from) and a Notes panel (each note with its time and source: the dashboard or Slack) under the row | Calls |
| Deciding on the queue | A note box and four one-click buttons | A Decide menu (Pursue, Not relevant, Submitted, Dismiss, and "Pursue and start the draft") plus Add a note. The button has an accent border until you decide | Q9 |
| Deciding on All calls | A decision select, a note and Save, labelled decide, change or add yours | The same menu, with the call's own decision above it (who and when) and the button reading Decide, Change or Add yours | Q9, C4, C5 |
| Your status | Not shown | In Top 10 and All calls: "needs your decision", with "due today" or "due in N days" inside 14 days. Once you decide: "You: {decision}" with its time, and the button reads Change | Q14 |
| Pursued calls | Nothing extra | "Start the draft", or "Open workspace" with the current step | Q17, P6 |
| Header menus | Sort; filters on Claude / Grok, Tier, Filter and Decision | On every column: sort, its filters, a keyword search, Hide column, and a link to Table settings | Calls |
| Rows | No hover | Rows lighten on hover; a row with an open panel stays tinted | Q16 |
| Table settings | Settings: columns per table and the tags line | Also: details under the title, the AI reason box and the note box (To review); All calls keeps its own list. Reset to defaults, Cancel, Save | S1 to S6 |
| Top 10 focus | | Arriving from Home: the call is scrolled into view, marked with an accent bar, focused and its reasons opened. Filters that would hide it are cleared, with a notice | Q15 |

### 2.5 Proposals

| Item | Today | In the package | IDs |
| --- | --- | --- | --- |
| The page | `/proposals`: the Register's past submissions, with win rate by portal | Five view cards: Closing in 14 days, To draft, Drafting, Submitted and waiting, Results. A filter bar and a sortable key column | P1 |
| To draft | | Pursued, open calls with no pursuit, each with "Start the draft" or the reason it can't start | P2 |
| Drafting | | The current step and its state in words, the owner, Open workspace, Open Drive folder | P3 |
| Submitted and waiting | | Covers:<br>- who submitted it and when, and the confirmation number;<br>- days waiting;<br>- "result expected by": the date Discovery found, or 90 days after the deadline;<br>- "result overdue" once that date passes;<br>- No news yet, which moves the date 30 days on;<br>- Record result (won, lost, withdrawn, cancelled by the agency), with an optional debrief and an optional "next time" | P4 |
| Results | The Register and its win rate | Adds results recorded here, with "Next time" | P5 |
| Start the draft | | A 760px dialog: format, approval mode, owner and deadline, working with, direction, builds on (past work, Drive picks, uploads) and the folder line. Start is the person's approval to spend | P6, PW24 |
| Decisions from the workspace | | Mark submitted and No-go record the call's decision through `decideCall`, so the stale-form guard (C8) applies. Choosing Submitted on a call with an open pursuit opens its Submit gate instead | P7, V6 |
| Before the worker exists | | Start the draft says "Drafting is not set up yet" | P8 |

### 2.6 Proposal workspace (all new)

| Piece | In the package | IDs |
| --- | --- | --- |
| Page and header | `/proposals/[callId]`: logo, breadcrumb, title, portal, format, deadline, owner, working with, approval mode, Drive link, then People, Checklist and Show history | PW1, PW24, PW16 |
| Stage strip and step list | Six stages (Qualify, Plan, Draft, Review, Finalize, Submit). Each step shows its state in words: waiting, working, ready, done or failed. Done steps open read only | PW1 to PW3 |
| The step card | What the step is for, the file saved to Drive, its content, "Your call", and the actions: Approve and continue, Ask for changes, Add material, and "Stop here, no-go" on steps 1 to 4 | PW4 |
| Key gates only | Steps other than Go or no-go, Outline and Submit approve themselves when Claude finishes, and the history says so | PW5 |
| Steps 1 to 4 | 1 Discovery: eight tasks and the result-expected date. 2 Opportunity summary. 3 Alignment: the owner's direction beside Claude's angle; keep, take or rewrite. 4 Requirements and a six-part checklist, with an internal submit-by date | PW6 to PW9 |
| Go or no-go | A decision brief. Go; Go with conditions (each condition joins the checklist); or No-go, with the reason and what would change it, which records Not relevant and moves the folder to `_no-go` | PW10 |
| Steps 5 to 7 | 5 Outline: approving it locks the direction and the past work. 6 First draft. 7 Compliance check | PW11 |
| Step 8, Reviews | The AI slop check runs on every new draft. Then three Claude passes (two evaluators that rate each criterion in words, then leadership) propose changes row by row, each with Accept, Reject and Edit. The step is approved once every change is decided | PW12, PW25 |
| AI slop check result | Verdict line, placeholders, paragraphs to revise first, findings by family, proposal faults and Check again. It never says or implies AI authorship | PW20 to PW23 |
| Step 9, Final checks | Seven checks, then the checklist. While a placeholder is open the check says Not ready | PW13 |
| Submit gate | Open the call page, the confirmation number, the "result expected by" date, Mark submitted. The owner submits on the portal | PW14 |
| States and limits | Working with a start time; failed with its reason and Retry; only the owner sees the actions; a $200 budget with Raise the cap | PW15, PW17, PW19 |
| Slack | Step ready, behind target, and a daily digest, in the call's thread | PW18 |

### 2.7 Automation

| Item | Today | In the package | IDs |
| --- | --- | --- | --- |
| Requests | `/requests`: waiting requests first, then the last 50 decided | Two views: Agent update requests (Approve, or Reject with a note) and Decided requests | Pages |
| Runs | `/runs`: the latest run on top, then the last 100; `/runs/[id]` for a log | Scans: the latest run as a card, then the runs table with a Portals filter and a sortable Started column. Scan problems: failed or timed-out runs | Pages |
| Judges | `/judges`: per judge, per person, between people, calls where people disagree, and pursued calls a judge said no to | The same content, restyled, under Automation | Pages |

### 2.8 Briefs, profile and sign-in

| Item | Today | In the package | IDs |
| --- | --- | --- | --- |
| Past weekly briefs | `/brief` in the bar: the Top 10, then a board per portal; earlier weeks linked | No link in the bar; a breadcrumb to Home. The Top 10 table as on Home, and boards as content cards whose band links to that portal's calls | H4 |
| Profile settings | None (column choices sit in a cookie) | `/profile`: display name and initials, the signed-in account, where the dashboard opens, default filters for Calls, and time zone | U2 to U6 |
| Sign-in | None: the picker, or IAP when configured | `/login`, the BD Team page: Sign in with Google (the company domain and `DASHBOARD_USERS` only), Reset password, "Need access?". Messages for signed out, timed out, not allowed and cancelled. Signed out, every page redirects here | U7 |
| Refusal wording | "Choose who you are (top right) before deciding." | "Log in (top right) before deciding." | V4 |

### 2.9 Data

| Table or column | Today | In the package |
| --- | --- | --- |
| `pursuits` | None; `proposals` is the Register | Call, owner, collaborators, format, approval mode, direction, builds on, Drive folder, current step, state, checklist, target dates, cost and budget ($200), submitted at, confirmation number, result expected by and its source, result |
| `pursuit_steps` | None | Step, attempt, state, files, summary, error, decision and timings, cost, Discovery's task states |
| `step_changes` | None | Reviewers' proposed changes: accepted, rejected or edited |
| `pursuit_events` | None | Show history |
| `drive_items` | None | The Drive index for Builds on |
| `slop_scans` | None; phase 7.7 writes `slop_scan.json` beside the draft | Each scan's verdict, band, points, the full JSON and the scanned lines |
| `profiles` | None; column choices sit in a cookie | One row per person: display name, initials, where the dashboard opens, default filters for Calls, time zone |
| `proposals.source_call_id` | None | Later: links a Register row to its call |
| `AGENTS.md` | Says the ledger is SQLite | Fixed |

### 2.10 Backend

| Item | Today | In the package |
| --- | --- | --- |
| Running steps | Nothing runs on approval. Requests apply at 12:07 and 17:07; draft requests wait for a Writer that does not exist | An always-on worker on David's PC:<br>- its own lock;<br>- polls every 20 seconds and claims one step at a time;<br>- records cost;<br>- approves steps itself in key gates mode;<br>- redoes a step on Ask for changes;<br>- stops on cancel.<br>Task Scheduler starts it at logon and restarts it on failure |
| The steps' work | `drafting/` phases 1 to 8: fully automatic, Markdown in a local folder | The design's nine steps and two gates, mapped onto those phases plus new prompts: Discovery tasks, Opportunity summary, the Go or no-go brief, evaluator ratings, the leadership pass, change rows and the seven final checks |
| Spending | Token usage logged per call | Cost per step and per pursuit; a $200 cap; stop and ask |
| Drive | None; Claude reads the Register through David's connectors | A service account on a shared drive:<br>- Library folders created on Start;<br>- drafts to `02_working/`, submitted files to `01_submitted/`, debriefs to `03_outcome/`, no-go to `Submissions/_no-go/`;<br>- `drive_items` refreshed every 15 minutes |
| Word | None | `python-docx`. Markdown stays the working format; each saved step is converted and uploaded |
| AI slop check | Phase 7.7 scans the final draft into a local file | Every new draft: fix what can be fixed automatically, then scan. Results stored in `slop_scans`; Check again queues a scan; a test checks the wording |
| Register | Read-only sync from files Claude writes | A Register row written on submit, which needs Sheets write access |
| Slack | Cards for new yes and maybe calls; replies read into notes once a day; no thread posts | Posts in the call's thread (`thread_ts`), and a card posted when a pursuit starts on a call without one. Step ready every 5 minutes; behind target and a digest at 08:00 |

### 2.11 People and configuration

| Item | Today | In the package |
| --- | --- | --- |
| Decision makers | `DASHBOARD_USERS`: David and Shaun | Adds Lisa and Alec (Analyst C and D in the prototype), with their emails and Slack ids |
| Google | `gog` not installed; no Cloud project | One project with an OAuth client for sign-in, the Drive and Sheets APIs, and a service account on a shared drive holding the Proposal Library. The key file lives on the PC, outside the repo |
| Sign-in secrets | None | The Auth.js secret and the Google client id and secret, wherever the dashboard runs |
| AI slop scanner | `AI_SLOP_SCAN`, used by drafting | Also used by the worker |

### 2.12 Repo, docs and tests

| Item | Today | In the package |
| --- | --- | --- |
| Spec | The 26 Oct version | `spec-updates.md` merged: Pages, VC1 to VC4, H1 to H5, Q9 and Q13 to Q17, DB1 to DB3, P1 to P8, PW1 to PW25, V4, V6, U2, U7, Data per call, and the decision log rows |
| Build prompts | `dashboard-build-prompts.md`: six phases | Superseded by this plan and the package's build plan |
| Design files | `dashboard-snapshot/` and the slide theme in `velocity-theme/` | `docs/design/handoff/`: the prototype, canvas, screenshots and app theme (`tokens-app.css`, `card.css`, components) |
| Skills | Synced claude.ai copies on David's PC; one is cut off | Complete skills under `.claude/skills/`, and workspace prompts under `drafting/` (path per section 1) |
| Tests | One-letter IDs in the brief's test; browser tests match today's markup | Two-letter IDs. Browser tests rewritten section by section. New pytest for the worker, Drive and Slack (with fakes) and the slop wording |

## 3. Phased plan

Each PR gets its own Linear ticket and branch, starts from failing tests, updates the docs (`DASHBOARD.md`, `STATUS.md`, `LEDGER_SCHEMA.md` and `RUNBOOK.md` where they apply), and is squash-merged with the ticket id in its subject. Sizes are relative: S, M, L.

| Phase | What | Package PR | Depends on | Size |
| --- | --- | --- | --- | --- |
| 0 | This plan; the package and spec merged into the repo; the Google setup guide | 1 | None | S |
| 1 | Ledger: migration 008 and its helpers | 2 | 0 | M |
| 2 | The look and the shell | 3, part of 4 | 0 | L |
| 3 | Sections and views: Home, Calls, Automation, briefs, profile | 4, 5 | 2 | L |
| 4 | Proposals views, Start the draft, badges everywhere | 6 | 1, 3 | M |
| 5 | The worker | 7 | 1 | L |
| 6 | Drive and Word | 8 | 5, Google setup | M |
| 7 | The workspace page | 9 | 4, 5 | L |
| 8 | Reviews and the AI slop check | 10 | 7 | M |
| 9 | Final checks, Submit and results | 11 | 7, 6 | M |
| 9c | An executive summary for each call, in place of the portal's own words | None (added 28 Oct) | None | S |
| 10 | Slack threads and jobs | 12 | 5 | S to M |
| 11 | Sign-in and ownership | 13, revised | OAuth client, hosting (PRO-477) | M |

Phases 2 and 3 change only `dashboard/`, and phase 5 changes only the worker and `drafting/`. Once phase 1 is in, they can run side by side. If Google setup is late, phase 7 starts on local files.

### Phase 0: the repo and outside setup (S)
- **PR 0.1 (PRO-565):** this plan.
- **PR 0.2 (package PR 1):**
  - commit the whole package to `docs/design/handoff/`;
  - merge `spec-updates.md` into the spec, with the defaults in section 1;
  - extend `tests/test_design_brief.py` to two-letter IDs;
  - mark `dashboard-build-prompts.md` superseded;
  - fix the SQLite line in `AGENTS.md`;
  - commit the complete skills to `.claude/skills/`.
- **PR 0.3:** the Google setup guide in `docs/RUNBOOK.md`, step by step, so David can start it at once:
  - the Cloud project with the Drive and Sheets APIs;
  - the shared drive and moving the Proposal Library into it;
  - the service account and its key file;
  - the OAuth client for sign-in.
- **Started outside the repo now, because later phases wait on it:** the Google setup (section 4), Lisa's and Alec's emails and Slack ids, and where the dashboard is hosted (PRO-477).

### Phase 1: the ledger (M)
- **Migration 008:**
  - `pursuits`, with collaborators, `cost_usd`, `budget_usd` (default 200), target dates, and "result expected by" with its source;
  - `pursuit_steps`, with cost and Discovery's task states;
  - `step_changes`, `pursuit_events`, `drive_items` and `slop_scans`;
  - `profiles`, one row per person.
- **`ledger/queries.py` helpers:**
  - create a pursuit with its first step;
  - claim and finish a step, guarded like `claim_request`;
  - guarded state changes;
  - events.
- **Docs:** `LEDGER_SCHEMA.md`, `ledger/schema.sql` and `tests/test_migrate.py` in the same commit, then `python -m ledger.migrate` on Supabase.
- **Tests:** a round trip on SQLite; guarded updates refuse a stale state.

### Phase 2: the look and the shell (L)
- **2a Theme:**
  - the app tokens (`tokens-app.css`, `card.css`) become the dashboard's token layer, dark only;
  - the fonts are self-hosted;
  - `lucide-react` is added;
  - components: button, badge, tag, card and view cards, menu (focus and arrow keys), dialog, notice, tooltip, table, field.
- **2b Shell** (ships in one PR with 3a, since the bar's Home has nothing to open before Home exists):
  - the top bar with four sections, icons and count chips;
  - the account menu: Profile settings, Table settings, Switch user (today's picker), and Log out (clears the name until phase 11);
  - the new notices;
  - hover, focus and reduced motion everywhere.
- **Existing pages** take the new look without changing behaviour; browser tests are updated only where the markup changed.
- **Tests:** unit tests for the count helpers; browser tests for the bar, the menu's keyboard behaviour, and dark only.

### Phase 3: sections and views (L, three PRs)
- **3a Home and addresses:**
  - the queue moves to `/review`;
  - Home at `/`: five link cards, the Top 10 from this week's brief, the status line and the brief link;
  - old addresses keep working (N4);
  - the view-switching rules (N6, VC2, VC4).
- **3b Calls:**
  - the seven views;
  - the new columns: Votes, Description, Due with days left, logos, detail sources, the badges line;
  - header menus with keyword search and Hide column;
  - the Reasons and Notes panels;
  - the Decide menu ("Pursue and start the draft" says "not set up yet" until phase 4);
  - your-status badges;
  - the Top 10 focus from Home;
  - the Table settings additions;
  - folding at 1280px;
  - the new empty states.
- **3c The rest:**
  - Automation: Requests and Decided requests; Scans and Scan problems, with a Portals filter and a sortable Started column; Judges;
  - Past weekly briefs;
  - Profile settings, saved to `profiles`.
- **Tests:**
  - unit tests for the view filters and counts, the description excerpt and its labels, and the status badges;
  - read-only browser tests for every address, the Top 10 focus and the 1280px fold.

### Phase 4: Proposals views and Start the draft (M)
- **The five Proposals views,** built from calls and pursuits.
- **Start the draft:** the dialog writes a queued pursuit and its first step, with the P2 and P6 refusals.
- **Badges** and their menus on every call (DB1 to DB3).
- **Choosing Submitted** on a call with a pursuit routes to its Submit gate (a stub until phase 9).
- **P8 applies** until the worker runs.
- **Tests:** the refusals (a second pursuit, Not relevant, closed, needs the solicitation); read-only browser tests.

### Phase 5: the worker (L)
- **The process:** its own lock, registered in Task Scheduler at logon with restart (`scripts/install-schedule.ps1` and its test).
- **The loop:** claim a step, then run it over the `drafting/` phases with the new step prompts from the adapted skills.
- **Its rules:** cost and the $200 cap, key gates approval, Ask for changes, cancel, and an event for each.
- **Files** go to a local working folder until phase 6.
- **Tests:** a fake LLM client; the lock kept apart from `pipeline.lock`; the budget stop; key gates approval.

### Phase 6: Drive and Word (M; needs the Google setup)
- **Drive:**
  - the service account client;
  - Library folders on Start;
  - uploads, with file ids saved in `pursuit_steps.files`;
  - `drive_items` refreshed every 15 minutes and on demand;
  - the Builds on folder;
  - the `_no-go` move.
- **Word:** `python-docx` conversion that follows the format the requirements document sets.
- **Tests:** a fake Drive client; no live calls in tests.

### Phase 7: the workspace page (L)
- **The page:** `/proposals/[callId]`, with the People, Checklist and Show history panels, the stage strip, the step list and the step card.
- **The screens:** steps 1 to 7 and both gates.
- **The actions:** Approve and continue, Ask for changes, Add material, Stop here no-go, Go, Go with conditions; ticking the checklist.
- **Permissions:** owner and working-with permissions, a courtesy check until sign-in.
- **The states:** working, failed and Retry, and "budget reached" with Raise the cap.
- **Tests:**
  - guarded update tests;
  - browser tests against a throwaway Postgres seeded with pursuits, as the snapshot was built, because browser tests must never write to the live ledger.

### Phase 8: Reviews and the AI slop check (M)
- **The worker:** fixes each new draft, then scans it and stores a `slop_scans` row; Check again queues a scan.
- **The reviews:** three Claude passes with ratings and change rows; Accept, Reject and Edit; the step is approved once every change is decided.
- **The result page** (PW20), with labels matched to the real scanner JSON.
- **Tests:** fixture JSON to `slop_scans`; the gate rules; the wording test; guarded change decisions.

### Phase 9: Final checks, Submit and results (M)
- **The workspace end:**
  - Final checks: seven checks and the placeholder sweep;
  - the Submit gate;
  - Mark submitted and No-go through `decideCall`.
- **Submitted and waiting:** overdue, No news yet and Record result.
- **Results:** recorded results combined with the Register.
- **On submit:** a Register row is written (Sheets), files move to `01_submitted/`, and the debrief goes to `03_outcome/`.
- **Tests:** cancelled by the agency maps to `no_award`; the overdue and No news yet dates; the stale-form guard (C8) on Mark submitted.

### Phase 9c: an executive summary for each call (S)
Added on 28 Oct at David's request; built right after phase 9.
- **Why:** the Description column shows the portal's own words, cut at 300 characters, so understanding a call takes a full read of it.
- **The review:** the per-call review (claude-haiku-5-5) already reads each call. Its prompt asks for one more line, `SUMMARY:`, two plain sentences for an executive: what the agency wants, what kind of award and how much, and the date that matters. New calls need no extra model call.
- **The ledger:** migration 009 adds `calls.ai_summary` (additive), written by the review. LEDGER_SCHEMA.md changes in the same PR.
- **Backfill:** `run.py --backfill-summaries` writes a summary for each open call that has none, with a summary-only prompt. A dry run counts the calls and estimates the cost first; at Haiku's prices it is well under a dollar per thousand calls.
- **The dashboard:** the Description cell shows the summary, labelled Summary, with the portal's own description in full on hover and focus. A call without a summary shows its description as today.
- **Tests:**
  - the review reads `SUMMARY:` and still works when the line is missing;
  - the backfill picks only open calls without a summary;
  - the cell prefers the summary and keeps the original on hover.

### Phase 10: Slack (S to M)
- **Threads:** `thread_ts`, and a card posted when a pursuit starts on a call without one.
- **Jobs:** step ready every 5 minutes, posting once per step; behind target and the digest at 08:00.
- **Mentions:** Slack ids from `DASHBOARD_USERS`.
- **Tests:** sink tests with a fake client; the schedule script test.

### Phase 11: sign-in and ownership (M)
- **Sign-in:**
  - the `/login` page;
  - Google sign-in inside the dashboard (Auth.js), limited to the domain and `DASHBOARD_USERS`, with sessions and Log out;
  - signed out, every page redirects there.
- **Identity:** the viewer comes from the session, and Switch user goes away.
- **Ownership:** owner-only actions are enforced.
- **With PRO-477:** the dashboard needs an HTTPS address for Google's redirect.
- **Tests:** the session and allowlist logic; the signed-out redirect.

## 4. What is needed from people

- **David:**
  - Lisa's and Alec's Google emails and Slack member ids, and Shaun's Slack id if it is missing;
  - the sign-in background image;
  - logos for DOE SBIR, Space Florida and APFIT, or approval of initials tiles.
- **Google setup** (David, with the guide from PR 0.3):
  - a Cloud project with the Drive and Sheets APIs;
  - a service account added to a shared drive that holds the Proposal Library, with its key file saved on the PC outside the repo;
  - an OAuth client for sign-in;
  - moving the Library into the shared drive if it sits in someone's My Drive.
- **Alec (PRO-477):** where the dashboard is hosted, which gives sign-in its HTTPS address.

## 5. Risks

- **The PC must be on** for steps to move; the worker and the Sunday scan both run there.
- **Login-gated solicitations** (Vulcan SOF, NSTXL member pages) go to the Anthropic API and into Drive, by David's decision of 27 Oct. They never go into the repo, fixtures or logs. AI vendor clearance (PRO-473) is still open.
- **Drafts cost money.** The $200 cap per pursuit needs current model prices to turn tokens into dollars.
- **Workspace browser tests need seeded data,** which means a throwaway Postgres; the live ledger stays read only for tests.
- **Deadlines are portal text,** so target dates and "result expected by" need a parsed date, and a deadline that is not a date gets neither.
- **The repo is public.** The package's data is the public snapshot's; nothing login-gated may be added. The portal logos are third-party marks, used only to identify each portal.
