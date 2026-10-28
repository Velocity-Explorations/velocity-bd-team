# Handoff: BD Team dashboard redesign and proposal workspace

28 Oct 2026. For Claude Code, building in `Velocity-Explorations/velocity-bd-team`.

## Start here

1. Read `docs/design/handover-discovery.md` in the repo (commit 65a5fce). It records what exists in the code today. This package says what to build and how.
2. Read `docs/decisions.md`. It covers:
   - every place the design and the code disagree, with the answer to each;
   - every decision David has made, dated 27 and 28 Oct.
3. Merge `docs/spec-updates.md` into `docs/design/dashboard-design-spec.md` as the first pull request. The build prompts and `tests/test_design_brief.py` check requirement IDs against the spec, so the spec must lead.
4. Build in the order of `docs/build-plan.md`, which lists 13 pull requests, each with its tests.
5. Use the files in `design/` as the reference for look and behaviour, and `velocity-theme/` for tokens and component rules.

`CLAUDE_CODE_PROMPT.md` is a ready-made first message for a Claude Code session.

## Overview

BD Team is Velocity's business development dashboard. It finds government calls (SBIR, STTR, BAAs, RFIs and others) across eleven portals. Two AI judges, Claude and Grok, rate each call, and people decide which to pursue. Pursued calls are then taken from first look to a submitted proposal in a step-by-step workspace, where Claude does each step's work and the proposal's owner approves it.

The redesign covers:
- the structure: four sections and view cards in place of tabs;
- every screen in that structure;
- the new proposal workspace;
- Google sign-in;
- the Velocity Theme extended from slides to app components.

## About the design files

The files in `design/` are **design references made in HTML**: prototypes that show the intended look and behaviour, not production code to copy. Recreate them in the dashboard's existing environment (Next.js, server actions over the ledger), using its patterns and libraries.

The `.dc.html` files are Design Components and need `support.js` beside them. To open them, serve the `design/` folder over HTTP, since the prototype fetches `proto-data.js`. For example, `cd design && python -m http.server 8000`, then open `http://localhost:8000/Review%20Queue%20Prototype.dc.html`. All styling is inline in each file, so inspect elements for exact values.

## Fidelity

**High fidelity.** Colours, type, spacing, radii, shadows, hover states and copy are final. Recreate them exactly, using the tokens in `velocity-theme/tokens-app.css` and `velocity-theme/card.css` rather than literals.

The dashboard is **dark only**: there is no light theme and no theme switch.

The data is the snapshot in the public repo's `docs/design/dashboard-snapshot`: 122 calls, 26 runs, the 19 Oct brief. Two changes were made for the example:
- C2 Capability Prototype is marked Submitted by Analyst A;
- DOW STTR 27.TZ Release 1 is pursued.

## The working prototype

`design/Review Queue Prototype.dc.html` is the source of truth for behaviour. It runs every section and keeps its state in this browser (localStorage key `bdq-proto-v1`). What it fakes:
- **The worker:** a workspace step takes 1.8 seconds.
- **Google Drive:** links go to drive.google.com, not a real folder.
- **Google sign-in:** the button signs you back in as the last person.
- **Slack:** nothing is sent.

Each view has its own address, for example `#/calls?view=all&portal=NSTXL&state=open`, and Back works.

| Address in the prototype | Screen |
| --- | --- |
| `BD Team Login.dc.html` | Sign-in page (signed out, every page goes here) |
| `#/` | Home |
| `#/calls` (Needs review), `?view=top10`, `due-soon`, `judges-agree`, `judges-disagree`, `new`, `all` | Calls |
| `#/proposals`, `?view=closing`, `drafting`, `submitted`, `results` | Proposals |
| `#/workspace?id={call id}` | Proposal workspace (the build uses `/proposals/{call id}`) |
| `#/automation`, `?view=decided`, `scans`, `problems`, `judges` | Automation |
| `#/brief` | Past weekly briefs |
| `#/profile` | Profile settings |

`design/Proposal Workspace.dc.html` draws every workspace step in order (9a to 9o) with full example content. `design/BD Dashboard Redesign.dc.html` is the design canvas: earlier explorations, the handoff note, and Turn 8, which shows each view live from the prototype. Artboards marked "superseded" are history only.

## Screens and views

Every page uses the same layout:
- the ground `#1E1E1E`;
- the top bar;
- content padded `0 24px`;
- fluid width;
- the 1280px breakpoint, where noted.

### Top bar (every page)
- **Bar:** 56px high with a `2px solid #333333` bottom rule.
- **Left, the brand:** the Velocity mark (16px high, `assets/velocity-mark-white.png`) then "Velocity BD" in Chakra Petch 13px 600, caps, 0.12em letter-spacing; it links to Home. See Open items: the app's name is BD Team.
- **Section links:** Home, Calls, Proposals and Automation, 28px apart. Each is Inter Tight 14px with a 15px Lucide icon (house, inbox, file-text, workflow).
  - Resting: `#BEBEBE`.
  - Current section: `#F5F5F5`, weight 600, the icon in accent `#FFCB03`, and `aria-current="page"`.
- **Count chips:** accent fill `#FFCB03`, text `#1E1E1E`, Chakra Petch 11px 700, 16px high, 4px side padding, 3px radius. Each has an aria-label saying what it counts (for example "28 waiting for you").
  - Calls: calls waiting for the viewer.
  - Proposals: calls to draft, plus workspace steps ready for the viewer.
  - Automation: requests waiting.
- **Right, the account button:** 38px high, 4px radius, transparent, with a 1px border that is accent while the menu is open. It holds a 28px initials square (`#434343`, Chakra Petch 12px 700), the name (13px 600), and "Deciding" under it (Chakra Petch 11px `#959595`).

### Account menu
- **Panel:** a menu panel (see Menus) 260px wide. The top section is a 36px initials square, the name, and "Decisions are recorded as you".
- **Items:** Profile settings, then Table settings (on Calls), then Switch user (until Google sign-in is live), then Log out.
- **Log out** ends the session and goes to the sign-in page with the notice "You are logged out of BD Team."

### View cards (Calls, Proposals, Automation, Home)
- **Layout:** one row of cards on a grid, `repeat(N, minmax(0,1fr))`, 12px column gap, padding `16px 24px`.
- **Shared rows:** each card spans three grid rows with `grid-template-rows: subgrid`, so the label band, the number and the description line up across the row. The tallest label or description sets that row for every card.
- **The card:** see `velocity-theme/card.css` and `components/card`.
  - Label band: Chakra Petch 11px 600, caps, 0.12em, `#BEBEBE`, padding `10px 14px`, 1px `#333333` rule below.
  - Number: Inter Tight 30px 700, padding `12px 14px 6px`, accent only for the count that needs you.
  - Description: Chakra Petch 12px `#959595`, padding `0 14px 14px`.
- **States:**
  - Selected: lighter gradient, 2px `#F5F5F5` border, band `#383838` with a `#555555` rule, a 3px accent bar along the bottom, and `aria-pressed="true"`.
  - Hover: lift 2px, border `#757575`, deeper shadow, 140ms ease-out.
  - Pressed: returns to rest.
  - Focus: 2px accent outline, offset 2px.
  - Reduced motion: no lift.
- **Switching cards** changes the table below. It keeps the portal, tag and open or closed filters, and resets the column filters and sort to the view's own. A column filter that matches no view leaves no card pressed.
- **Home's cards** are links, marked with an arrow in the band, and open their view.

### Home
- **Five link cards:**
  - Needs review, whose count is in accent;
  - Due soon;
  - Agent update requests;
  - Proposals to draft;
  - Submitted and waiting.
- **The Top 10 table, the only table on Home:**
  - Columns at 1280px and up: rank 32px, Call `minmax(0,1.4fr)`, Deadline 170px, Claude 76px, Grok 76px, Decision now 104px, Description `minmax(0,1.1fr)`, Claude's reason `minmax(0,1.1fr)`.
  - Below 1280px, Description and Claude's reason are hidden.
  - Each row has a 28px right padding holding a 16px arrow in `#757575`.
- **Row click:** clicking a row outside its links and buttons, or pressing Enter on the focused row, opens Calls, Top 10. That call is scrolled to about 140px from the top, given an inset 3px accent bar on the left and a `#2A2A2A` background, takes focus, and has its reasons panel open. Calls, Top 10 lists all ten calls, decided or not. If the bar's filters would hide the call, they are cleared, with the notice "Cleared the portal, tag and open or closed filters so this call shows."
- **The title** links to the portal page in a new tab.
- **Badges and buttons in the row:**
  - A draft or submitted badge, on its own line under the details, opens its menu.
  - "Start the draft" shows on pursued calls with no draft.
- **Under the table:**
  - the status line: requests waiting, the last scan's result and time, and how often the judges agree;
  - a link to this week's brief.

### Calls
- **View cards:** Needs review (the count in accent), Top 10, Due soon, Judges agree, Judges disagree, New this week, All calls.
- **Filter bar:** 30px controls, in this order:
  - the Portals menu;
  - the Tag menu;
  - the All, Open and Closed switch;
  - Clear filters, shown when any filter is set;
  - the count line, right-aligned, Chakra Petch 12px `#959595`;
  - Table settings at the end.
- **All calls also has a title search:** 260px wide, applied on Enter, with the placeholder "Search titles, Enter to apply".
- **Table header:** min 36px high, 1px rule above and 2px below.
  - Labels: Chakra Petch 12px 600 `#BEBEBE`.
  - Each header has a 20px menu button. It holds the column's sort, its filters and keyword search, Hide column, and a link to Table settings.
  - The sorted column is ink, with an accent arrow and `aria-sort`.
- **Body rows:** 1px `#333333` rule, cells padded `12px 10px`. Hover lightens the row to `#262626` over 120ms. While the reasons or notes panel is open, the row is `#232323`.
- **Columns:**
  - **Call:**
    - a 40px white logo tile, 1px `#434343` border, 4px radius;
    - the title, 14px 600, linked to its portal page, with an external-link icon;
    - details, 12.5px `#BEBEBE`, separated by dots. A detail with a source is dotted-underlined, focusable, and shows its source on hover and on keyboard focus;
    - badges on their own line;
    - tags on their own line, 20px high, 3px radius, the type tag first in the info tone.
  - **Filter (All calls only):** kept, rejected or pending; the tier; the reject reason.
  - **Votes:** Claude and Grok, each with its badge and a 20px note button that opens the reason panel. Under a dashed rule, each person's latest vote, with a note button when they left a note. "judges disagree" or "people disagree" shows as a badge, in words.
  - **Description:** the first 300 characters, up to four lines, in full on hover and on focus. Text the scanner wrote is labelled "Scanner summary"; a members-only page says "Members only".
  - **AI reason.**
  - **Due:** the date, the time, and days left.
  - **First seen:** hidden by default.
  - **Decide:** 176px.
  - Below 1280px, the AI reason folds under the call, and the description is hidden.
- **The Decide cell:**
  - **Undecided by you:** on a queue call you have not decided, the Decide button (28px high, full width) has an accent border and chevron.
  - **Mixed views:** Top 10 and All calls mix calls you have and have not decided. There, an undecided call also shows a "needs your decision" badge in the caution tone. When it closes within 14 days, a line under the badge in Chakra Petch 11.5px `#FAB36D` reads "due today" or "due in N days".
  - **Once you decide:** the cell shows "You: {decision}" as a badge with its time, and the button reads "Change". On All calls, the call's own decision shows above, with who decided and when; there the button reads Decide, Change or Add yours.
  - **The Decide menu:** Pursue, Not relevant, Submitted and Dismiss, each with its tone square and word. A call with no pursuit adds "Pursue and start the draft". "Add a note" opens a note of up to 2,000 characters.
  - **Pursued calls:** a pursued call with no draft shows "Start the draft"; one with a draft shows "Open workspace" with its current step.
- **Expanded panels** open under the row on `#1A1A1A` with a 24px close button:
  - **Reasons:** both judges' reasons, and where the details come from.
  - **Notes:** each person's note with its time and source, on the dashboard or a Slack thread reply.
- **Empty state:** an 8px square, a title, one line saying why, and a way out.

### Table settings (dialog)
- **To review's settings:** columns, details under the title, the AI reason box, and the note box.
- **All calls' settings:** its own column list.
- **Footer:** Reset to defaults, Cancel, Save. See Dialogs.

### Proposals
- **View cards:** Closing in 14 days, To draft (in accent), Drafting, Submitted and waiting, Results. The filter bar works as on Calls, and each view's key column can be sorted.
- **To draft:** pursued calls with no pursuit, each with "Start the draft". When a call can't be drafted, the reason shows in place of the button: closed, or needs the solicitation first.
- **Drafting:** each pursuit with its current step and its state in words, the owner, "Open workspace", and "Open Drive folder".
- **Submitted and waiting:**
  - who submitted it and when, and the confirmation number;
  - days waiting;
  - "Result expected by", the date Discovery found or else 90 days after the deadline, with "result overdue" once that date passes;
  - "No news yet", which moves the date 30 days on;
  - "Record result", a group of Won, Lost, Withdrawn and Cancelled by the agency, with an optional "What to do differently next time" box. Results shows it as "Next time".
- **Results:** results recorded here and past submissions from the Register, with win rate by portal.

### Start the draft (dialog, 760px)
- **Title:** the call's title, portal and deadline.
- **Format:** read from the call's type, with a select to change it.
- **User approval required:** radio cards, "Every step" or "Key gates only".
- **Owner and deadline,** shown read only.
- **Working with:** optional checkbox chips of the other decision makers.
- **Direction:** optional.
- **Builds on:** optional chips of past work, suggested past work, "Choose from Drive" and "Upload files".
- **The folder line:** "Creates Submissions/... in Google Drive".
- **Footer:** Cancel, then "Start the draft", which turns green on hover.

### Proposal workspace
- **Header:**
  - the 44px logo tile;
  - the breadcrumb "Proposals > {stage}";
  - the title, 22px 700;
  - a line with the portal, format, deadline, owner, "Working with", the approval mode, and the Drive folder link;
  - at the far right, People, Checklist (from step 4, "N of 20 done") and Show history, which toggle panels under the header.
- **Stage strip:** Qualify, Plan, Draft, Review, Finalize, Submit, in six equal columns, each with a 3px top rule: done `#80DBA2`, current accent, next `#434343`.
- **Step list:** 220px to 280px on the left, with stage headings. Each step has its number, name and state word: waiting, working, ready, done or failed. Done steps open read only.
- **The open step's card:**
  - 2px `#F5F5F5` border;
  - a band (`#383838`) with "Step N of 9 · {name}" and its state;
  - what it is for;
  - a "working" notice while Claude works;
  - the file saved to Drive;
  - the step's content;
  - "Your call", in an accent label on `#1A1A1A`, with the question;
  - the actions.
- **The steps:**
  - 1 Discovery: eight tasks with their state.
  - 2 Opportunity summary: the full description and the key facts.
  - 3 Alignment: a verdict, "How it aligns for Velocity", the owner's direction beside Claude's angle, and a choice of Keep mine, Use Claude's angle or Write a new one.
  - 4 Requirements and checklist: the six-part submission checklist starts here.
  - The Go or no-go gate: the decision brief, with Go, Go with conditions or No-go.
  - 5 Outline: sections, criteria, page shares and the past work each draws on. Approving locks the direction and the past work.
  - 6 First draft.
  - 7 Compliance check.
  - 8 Reviews:
    - the AI slop check runs automatically;
    - two evaluator passes rate each criterion in words;
    - a leadership pass;
    - each pass proposes changes, one per row: section, now (struck through), suggested, and why, with Accept, Reject and Edit at the right.
  - 9 Final checks: seven checks, then the checklist.
  - The Submit gate: "Open the call page" at the end of its row, the confirmation number, the "Result expected by" date, and Mark submitted. The owner submits on the portal themselves.
- **AI slop check result (in Reviews):**
  - the verdict line, for example "Not ready: 1 PERSON WRITES, 2 NEEDS INPUT; band light (provisional)", with the band, points, confidence, word count, and the last scan's time and draft;
  - the open placeholders by kind, each with a line link;
  - up to five paragraphs to revise first;
  - the findings by family, each with its tier, hits, rate per 1,000 words, fix, and findings by line and column;
  - the proposal faults, listed apart;
  - Check again;
  - a line link opens the scanned text beside the list. It never says or implies AI authorship.
- **Button colours by function:** see Tokens.
  - Approve and continue, Go, Mark submitted and Accept fill green on hover.
  - Ask for changes, Add material, Check again and Edit fill blue.
  - Stop here, no-go, No-go and Reject fill red.
  - Neutral buttons lighten.
- **The owner and the people working with them:**
  - Only the owner sees the approve, gate and change actions.
  - People working with the owner see "Waiting on {owner}..." and can add material and tick checklist items.

### Automation
- **View cards:** Agent update requests (in accent), Decided requests, Scans, Scan problems, Judges agree.
- **Requests:** "Approve", or "Reject with a note".
- **Scans:** the most recent run as a card on top, then the runs table with a Portals filter and a sortable Started column.
- **Judges:** scores against the team's decisions, by person, between people, calls where people disagree, and pursued calls a judge said no to.

### Past weekly briefs
A breadcrumb back to Home, then the Top 10 table (as on Home), then one board per portal. Each board is a content card whose label band links to that portal's calls.

### Profile settings
- **Layout:** one row per setting, the label and help in a 300px column and the field up to 560px wide.
- **Settings:**
  - display name and initials;
  - the signed-in account;
  - where the dashboard opens (Home or Calls);
  - the default filters for Calls (portals, tag, open or closed);
  - time zone (America/Denver by default).
- **Footer:** Reset to defaults, Cancel, Save.

### Sign-in page (`BD Team Login.dc.html`, the build's `/login`)
- **Background:** the company slate image, set to cover with an `rgba(0,0,0,0.18)` overlay. Until the image is supplied, a radial gradient fallback from `#3A3A3A` to `#121212`.
- **Card:** up to 530px wide, centred, padding `76px 50px 56px`, 6px radius, the card fill and shadow.
- **Inside the card, in order:**
  - the mark, 44px, and "BD TEAM" in Inter Tight 46px 700, 0.06em, caps;
  - the message, if any;
  - "Sign in" in Chakra Petch 13px 600, 0.14em, caps;
  - "Use your Velocity Google account." in 15px `#BEBEBE`;
  - the "Sign in with Google" button;
  - "Reset password", which goes to Google's account recovery;
  - "Need access? Ask an admin" in `#959595`.
- **The button:** 60px high, 4px radius.
  - Fill: `linear-gradient(90deg,#0066CC,#00468A)`.
  - Text: Chakra Petch 17px 600, 0.12em, caps, white.
  - Hover: brightness 1.15 and `0 6px 16px rgba(0,70,138,0.45)`.
  - While signing in it reads "Signing in".
- **Stripe:** a 30px stripe at the card's foot, `linear-gradient(90deg,#F2C744 0%,#9FCF9A 24%,#3CCFD8 44%,#00C8FF 58%,#0A72D0 80%,#0B3FA8 100%)`.
- **Messages,** each with its word:
  - "Done: You are logged out of BD Team." (status, info tone);
  - "Refused: Your login attempt timed out. Login will start from the beginning.";
  - "Refused: This Google account cannot use BD Team yet. Ask an admin to add it.";
  - "Refused: Google sign-in was cancelled. Sign in again to continue."
- **No Create account:** an admin adds people.

### Notices
- **Bar:** a full-width bar at the top of the content, with the tone's wash, a 1px tone line and a 4px radius.
- **Contents:** a 76px column with a 6px square and the word (Done, Refused or Note), one sentence, and at most one underlined link.
- **Roles:** `role="status"` for done, `role="alert"` for refused.

## Interactions and behaviour

- **Every interactive element has a hover state.**
  - Buttons: the fills above. Secondary buttons go to `#2E2E2E` with a `#757575` border.
  - Text links turn accent.
  - Table rows lighten.
  - Cards lift.
  - Transitions are 120ms ease-out, and 140ms for cards. With reduced motion, the lift and transitions are off.
- **Focus:** every focusable element shows a 2px accent outline, offset 2px.
- **Menus:**
  - Focus moves in on open, arrow keys move between items, and Escape or a click outside closes the menu.
  - Focus returns to the trigger, and only one menu is open at a time.
- **Dialogs:** focus moves in on open, Tab stays inside, and Escape or Cancel closes the dialog and returns focus.
- **Hover-only text:** any `title` text shows as a tooltip on keyboard focus too (`#333333`, 1px `#555555`, 12.5px, up to 360px wide).
- **Decisions on Calls:**
  - On the queue, the first decision becomes the call's decision.
  - On All calls, the newest decision wins.
  - Every vote is kept, and the latest per person shows.
  - An out-of-date form writes nothing and says what the call is now (C8, server-side).
- **Workspace steps:** see the PW rows in `docs/spec-updates.md`. The prototype shows every state: working, ready, done, failed, approved automatically in key gates only mode, waiting on the owner, read only.
- **Signed out:** every page goes to the sign-in page. "Sign in with Google" signs in and returns to Home, with the notice "Signed in with Google as {name}."
- **Times:** shown in the viewer's time zone. A deadline the portal wrote as text stays as written.

## State and data

- **Server state:** the ledger. `docs/build-plan.md` gives migration 008:
  - `pursuits`, `pursuit_steps`, `step_changes`, `pursuit_events`, `drive_items`, `slop_scans`;
  - the new pursuit fields: collaborators, cost and budget ($200 default), target dates, result expected by and its source.
- **Who does what:** the dashboard writes rows through guarded server actions, and the worker does the work.
- **Client state:** the view, filters and sort live in the address, and open panels and menus are local. The time zone and default filters come from Profile settings.

## Design tokens

Full lists are in `velocity-theme/tokens-app.css` and `velocity-theme/card.css`.

| Group | Values |
| --- | --- |
| Ground and surfaces | ground `#1E1E1E`, surface `#262626`, raised `#2E2E2E`, inset field `#1A1A1A`, input `#141414` |
| Lines | subtle `#333333`, line `#434343`, strong `#555555`, hover `#757575` |
| Ink | `#F5F5F5`, `#BEBEBE`, `#959595`, `#757575` |
| Accent | `#FFCB03`: what needs you, the current selection and focus. Never a status colour |
| Good | text `#80DBA2`, line `#3A8357`, wash `#182C1F` |
| Caution | text `#FAB36D`, line `#99642A`, wash `#322314` |
| Conflict | text `#FFA59D`, line `#A45953`, wash `#36201E` |
| Info | text `#7ECCFF`, line `#3977A8`, wash `#172836` |
| Neutral | text `#BEBEBE`, line `#555555` |
| Card, dialog, menu fill | `linear-gradient(135deg,#2C2C2C 0%,#262626 45%,#212121 100%)`; selected `linear-gradient(135deg,#363636 0%,#2E2E2E 45%,#282828 100%)` |
| Shadows | card, dialog, menu `4px 6px 14px rgba(0,0,0,0.45)`; hover `6px 10px 22px rgba(0,0,0,0.55)`; selected `4px 6px 16px rgba(0,0,0,0.55)`. Inset boxes inside a card stay flat |
| Radius | chips and badges 3px; cards, buttons and fields 4px; menus and dialogs 6px |
| Button hover fills | approve: green `#80DBA2`, active `#5FBF84`. Change or add: blue `#7ECCFF`, active `#5CB2EA`. Stop or reject: red `#FFA59D`, active `#E8857C`. Text `#1E1E1E` on all three. Neutral: `#2E2E2E` with a `#757575` border |
| Buttons at rest | primary: ink fill `#F5F5F5`, text `#1E1E1E`, weight 600. Secondary: `#262626` with 1px `#434343`. Destructive: transparent with 1px `#A45953` and text `#FFA59D`. Heights 32px, or 28px in rows and menus |
| Badges | 18px high, 1px tone line, 3px radius, a 6px tone square, Chakra Petch 11px 600; the word is always written |
| Type | page title 24/700, workspace title 22/700, dialog 20/600, section 16/600, body 14/1.5, row title 14/600, small 13, detail 12.5, header 12 Chakra Petch 600, label 11 Chakra Petch 600 caps 0.12em, dates and counts in Chakra Petch 500, card number 30/700 |
| Fonts | Inter Tight 400, 600, 700, and Chakra Petch 400, 500, 600, 700 (`design/fonts/`) |

## Assets

- **Fonts:** `design/fonts/`, woff2.
- **Velocity marks:** `design/assets/velocity-mark-white.png`, `velocity-lockup-white.png` and their ink versions.
- **Portal logos:** `design/assets/logos/`, shown on a white 4px-radius tile:
  - afwerx, diu, nasa, nstxl, sam-gov, spacewerx, ssc, vulcan-sof;
  - the originals are in `logos/src/`.
- **Icons:** Lucide, from `lucide-static@0.460.0`, drawn as CSS masks in `currentColor`. Use the dashboard's Lucide package instead.
- **The sign-in background:** the company slate image is still to be supplied by David. The page shows a placeholder until then.

## Files in this package

| Path | What it is |
| --- | --- |
| `CLAUDE_CODE_PROMPT.md` | The first message for Claude Code |
| `docs/decisions.md` | The design and code disagreements, and David's decisions |
| `docs/spec-updates.md` | The spec changes as requirement rows, ready to paste |
| `docs/build-plan.md` | The architecture, migration, worker, Drive and Word, AI slop check, Slack, sign-in, routes, and 13 pull requests with their tests |
| `prompts/opportunity_assessment.md`, `prompts/proposal_drafting.md` | The two skills adapted to the workspace; commit to `drafting/prompts/` |
| `skills/opportunity-assessment/SKILL.md`, `skills/proposal-drafting/SKILL.md` | The complete skills as written; commit to `.claude/skills/` |
| `velocity-theme/` | `tokens-app.css`, `card.css`, `tokens.json` and a guide per component: account menu, badge, button, card, dialog, field, menu, notice, table, tag, tooltip, top bar, view cards |
| `design/Review Queue Prototype.dc.html` | The working prototype of every page |
| `design/BD Team Login.dc.html` | The sign-in page |
| `design/Proposal Workspace.dc.html` | Every workspace step drawn in order (9a to 9o) |
| `design/BD Dashboard Redesign.dc.html` | The design canvas and handoff note; history included |
| `design/TopBar.dc.html`, `QueueRow.dc.html`, `VoteRow.dc.html`, `Velocity Theme Card.dc.html` | Components the canvas imports, and the card's sample page |
| `design/proto-data.js`, `design/data.js` | The snapshot data the designs read |
| `design/support.js`, `design/image-slot.js` | The runtime for the design files. Not for the build |
| `screenshots/app/`, `screenshots/workspace/` | Pictures of every screen and workspace step |

## Screenshots

`screenshots/` holds pictures of every screen, for a quick look. The HTML files hold the exact values.
- They were taken at the 1440px layout, scaled to fit, so they are about 910px wide.
- Long screens are cut off at the bottom; the workspace steps are shown in one or two parts.

- `screenshots/app/`, from the working prototype:
  - 01 Home;
  - Calls: 02 Needs review, 03 Top 10, 04 All calls, 05 the Decide menu, 06 Table settings;
  - 07 the account menu;
  - Proposals: 08 To draft, 09 Drafting, 10 the proposal workspace, 11 Submitted and waiting, 12 Results;
  - Automation: 13 Requests, 14 Scans, 15 Judges;
  - 16 Past weekly briefs;
  - 17 Profile settings;
  - 18 the sign-in page, without its background image.
- `screenshots/workspace/`: every workspace mockup from 9a Start the draft to 9o Notices, named by artboard.

The counts and states come from one browser's prototype session, so some views show data a person added while trying it out.

## Open items

1. **The app's name.** The sign-in page says BD Team, but the top bar still says "Velocity BD". Ask David which the top bar should say before building it.
2. **Sign-in method.** The sign-in page needs Google sign-in inside the dashboard, limited to the company domain and `DASHBOARD_USERS`. IAP in front of the dashboard would show Google's page first and never this one. Decide this with PRO-477 (`docs/build-plan.md`, Sign-in).
3. **The AI slop check result** is designed from a description of the scanner, not its real output; its family names and counts are examples. Read the scanner's JSON from the private ai-slop-detection repo and match the labels. Nothing from that repo goes into the public repo.
4. **Content in the public repo.** `design/proto-data.js` holds the public snapshot's calls, including 16 mentions of Vulcan SOF. They are already public in `docs/design/dashboard-snapshot`; check that before committing the design files, and never add login-gated text.
5. **House rules:**
   - no en dash or em dash anywhere (write ranges with "to");
   - plain sentence-case labels, with caps only through CSS;
   - status always as a word, never colour alone.
