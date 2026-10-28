# BD Dashboard Build Prompts

25 Oct 2026, David; revised 26 Oct for Home and the four sections

> Superseded on 28 Oct 2026 by Claude Design's handoff package (handoff/README.md) and the build plan in redesign-plan.md. Kept for the record; requirement IDs here follow the spec as it stands.

Seven prompts take the dashboard from today's UI to the Velocity Theme redesign: one for Claude Design, then six for Claude Code, each ending in a merged pull request.

## How to use

Run the prompts in order; each Claude Code run starts from main after the previous pull request merged.

1. Paste prompt 0 into Claude Design on the Velocity account. It reads this folder from GitHub, since the repo is public, and returns a design.
2. Bring the design into the repo. Claude Code runs on David's own login, which cannot open designs on the Velocity account, so export the design from Claude Design (its HTML or handoff bundle, with the handoff note) into `docs/design/redesign/` through a pull request. If a Claude Code session can open the design's link, the link works too.
3. In every Claude Code prompt below, replace `<DESIGN_LINK>` with `docs/design/redesign/` (or the link).
4. Paste prompts 1 to 6 into Claude Code in `C:\Projects\velocity-bd-team`, one session each. Each ends with its pull request merged, its Linear issue done, and a row in Shaun's review doc (BD Automation Review).

Already have a design from the earlier prompt 0, made before 26 Oct for the seven pages? Paste the update prompt at the end of this file into the same Claude Design project instead of prompt 0, export the design as in step 2, then run prompts 1 to 6 as written.

Each Claude Code prompt stands alone (AGENTS.md rule 6) and repeats the rules that matter. Where the design leaves a choice open, Claude Code asks you through the questions prompt rather than guessing.

The inputs every prompt reads are in this folder: the [design spec](dashboard-design-spec.md), the [dashboard snapshot](dashboard-snapshot/README.md) and the [Velocity Theme](velocity-theme/README.md). The snapshot shows the seven pages from before 26 Oct; the spec's Pages section has the four sections that the design and the build follow.

## Prompt 0: Claude Design

Paste into Claude Design. It designs every screen in the Velocity Theme and ends with a handoff note the Claude Code prompts read.

```text
Design the next version of Velocity's BD triage dashboard in the Velocity Theme design system.

Everything you need is in the public GitHub repo Velocity-Explorations/velocity-bd-team, in docs/design:
https://github.com/Velocity-Explorations/velocity-bd-team/tree/main/docs/design
Its README.md says what each part is. To read a file as plain text, use https://raw.githubusercontent.com/Velocity-Explorations/velocity-bd-team/main/ followed by the file's path.

Read these first:
1. The design spec: https://github.com/Velocity-Explorations/velocity-bd-team/blob/main/docs/design/dashboard-design-spec.md
   Every requirement and decision behind the dashboard. Keep all of them; only their look is open. Its Pages section sets the structure: four sections, Home, Calls, Proposals and Automation, replace the seven pages of today's dashboard, and Home is new. Its "Velocity Theme fit" section lists where the theme and the dashboard collide (status colours, dark only, date format, where the yellow accent goes, missing app components). Resolve each one and say how.
2. The design system: https://github.com/Velocity-Explorations/velocity-bd-team/tree/main/docs/design/velocity-theme
   README.md is the brand book; tokens.json and tokens.css hold the tokens; components/ holds each component's guidelines and an example; fonts/ and assets/Logos/ hold the typefaces and the Velocity logo. It was made for slides, so extend it to app components rather than replace it.
3. The snapshot of today's UI: https://github.com/Velocity-Explorations/velocity-bd-team/tree/main/docs/design/dashboard-snapshot
   Its README shows ten screenshots; the seven HTML pages keep the real markup, styling and data. They show the old seven pages, so take content from them and structure from the spec. Use its calls as the content of your artboards.

Artboards, 1440px wide unless noted:
- Home, the landing page: the top bar with the four sections, Ready for review, Top 10, Due in the next 14 days, Submitted and waiting, and the status line.
- Calls, To review, the main working screen: the tabs, the filter bar, and a table with one call in each state: judges agree, judges disagree (yes vs no), a call another person voted on, a member-only call with no deadline, a NASA forecast.
- To review at 1024px.
- One To review row enlarged, with every detail, badge and tag variant.
- Calls, All: a call with two people's disagreeing votes, a rejected call, and the decide control open.
- Menus open: a column header's filter, Portals, Tag.
- The account menu open, the Table settings dialog, and the Profile settings page.
- Proposals: Pursuing (Ready to draft with Draft buttons, and Drafting with a queued, a running, a finished and a failed draft), Submitted and Results.
- Automation: Requests (with the count badge), Scans and Judges.
- A past weekly brief.
- Notices: done, refused, and the vote notice with its link.
- Empty states for each Home block, To review and All.
- Light and dark, unless you decide on dark only; then say why.

Goals: Home answers what needs attention now at a glance; triage on To review is fast; the width is used well. Rows are tall today; make them denser without hiding anything a decision needs. Keep every piece of hover-only information reachable from the keyboard.

Rules: no en dash or em dash anywhere (write ranges with "to"); plain sentence-case labels; status always written as a word, never shown by colour alone; real content from the snapshot, never placeholder text.

End with a handoff note on the canvas for the developers: the tokens you added to the theme (status colours, table, form and menu styles), the type sizes for the web, the components you defined, and any spec requirement you could not meet and why.
```

## Prompt 1: theme foundation

Brings the theme's tokens, fonts and shared components into the dashboard. Pages keep their layout, so later prompts change one part at a time.

```text
Phase 1 of 6 of the dashboard redesign: bring the Velocity Theme into the dashboard as tokens, fonts and shared components, without changing any page's layout or behaviour.

Read first, in this order:
- AGENTS.md, docs/STATUS.md and docs/DASHBOARD.md in this repo.
- The design: <DESIGN_LINK> (from Claude Design; read its handoff note too).
- The spec: docs/design/dashboard-design-spec.md. Requirement IDs such as Q4 or F7 refer to it.
- The design system: docs/design/velocity-theme/. Read its README.md, tokens.json and components/bundle.css. The fonts are its fonts/*.woff2 with their licences in licenses/; the Velocity mark is in assets/Logos/.
- Today's UI: docs/design/dashboard-snapshot/ (README.md with ten screenshots, and the seven pages).
If you cannot open the design, stop and ask David to export it into docs/design/redesign/.

Build:
1. dashboard/app/globals.css: one token layer from the theme (ground, surface, line, ink and its steps, accent) plus the status tones the design adds, replacing today's --bg, --surface, --fg, --muted, --border, --accent and the good, warn, bad, info and grey tones. Components read tokens only; no literal colours outside the token layer.
2. Self-host Inter Tight and Chakra Petch from the theme's woff2 files with next/font/local and real fallbacks; commit the OFL licence texts beside them.
3. Restyle the shared pieces to the design: top bar (Velocity mark, page links, the Requests count, and today's picker and Settings button, which phase 2 folds into the account menu), page head, tabs, metric cards, badges and tags, buttons, text fields and selects, menus (details.menu), the Settings dialog, notices and tables. Keep today's markup and class names where you can, so pages take the look without edits. The top bar keeps today's seven links; phase 2 changes them to the four sections.
4. Light and dark exactly as the design decides; if it is dark only, drop the light values and say so in docs/DASHBOARD.md.
5. Where the design leaves a choice open, ask David with the questions prompt (recommended option first) rather than guess.

Keep: every behaviour the spec lists; server components, URL parameters for every view and server actions for every write; the two cookies (bd_viewer, bd_columns); only the client code there is today (ViewerPicker, SettingsDialog, MenuController); the dashboard reads only the ledger, never another component's files.

Tests first:
- Write failing tests for what you add, for example that the top bar shows the Velocity mark and that every badge carries its status word.
- At the end these pass: cd dashboard; npm test; npm run build. At the repo root: pytest.
- Browser tests against the dev server (cd dashboard; npm run dev serves port 8000; if 8000 is busy, run npx next dev --port 8010 and use that URL):
  $env:DASHBOARD_TEST_URL = "http://localhost:8000"; pytest tests/test_dashboard_layout.py tests/test_dashboard_settings.py tests/test_dashboard_viewer.py tests/test_dashboard_filters.py
  Update a selector only where the markup changed; never weaken what a test checks.
- Look at every page at 1440px and 1024px (Playwright screenshots in your scratchpad, never the repo).

Process:
- A Linear issue first (team Product, project BD Automation), In Progress; its text names people, outcomes and evidence.
- Branch dashboard/theme-foundation; never commit to main.
- Commit: feat(dashboard): Velocity Theme tokens, fonts and shared components PRO-NNN, then a line ref PRO-NNN, nothing else.
- No en dash or em dash in code, comments, docs, commits, PR text or the UI.
- The repo is public: no Vulcan SOF content or anything login-gated in commits, fixtures or screenshots; never print an environment variable's value.
- Update docs/DASHBOARD.md and docs/STATUS.md.
- Open the PR, squash-merge it once verified (no need to ask), switch to main and pull, mark the issue Done with a comment on what changed and the test results, and add a row to the "Since 21 Oct" table in Shaun's review doc, BD Automation Review (its link is in your memory notes; otherwise ask David).

Done when every page shows the Velocity look through the new tokens, nothing moved or broke, all tests pass and the PR is merged.
```

## Prompt 2: the four sections and Home

Replaces the seven top bar links with Home, Calls, Proposals and Automation, moves each page under its section, and builds Home, the account menu and Profile settings.

```text
Phase 2 of 6 of the dashboard redesign: the four sections, Home and the account menu. Phase 1 (theme tokens, fonts and shared components) is merged on main.

Read first: AGENTS.md, docs/STATUS.md and docs/DASHBOARD.md; the design <DESIGN_LINK> (the top bar, the tabs, Home, Proposals, Automation, the account menu and Profile settings); the spec docs/design/dashboard-design-spec.md, sections Pages, Home, Proposals, Deciding, Settings, and Account menu and profile; then every page under dashboard/app/, dashboard/lib/queries.ts and dashboard/lib/brief.ts. If you cannot open the design, ask David to export it into docs/design/redesign/.

Build N1 to N6, H1 to H5, P1 to P8 and U1 to U6, keeping V1 to V9 and S1 to S6:
- Top bar: Home, Calls, Proposals and Automation, with the Requests count as a badge on Automation, and the account menu (U1): the picker becomes Switch user, Clear User Selection becomes Log out, and Settings becomes Table settings, which also stays beside the filter bar.
- Addresses: Home at /; Calls with To review at /review (today's queue, moved from /) and All at /calls; Proposals with Pursuing at /proposals, Submitted at /proposals/submitted and Results at /proposals/results (today's Proposals page); Automation with Requests at /requests, Scans at /runs and Judges at /judges; Profile settings at /profile; past weekly briefs stay at /brief, linked from Home. Every old address keeps working (N4).
- Home, built as designed: the blocks in H1 to H5, read live from the ledger. The Top 10 ranks yes before maybe, then the nearest deadline, then the newest, the order assistant/tools.py (RANKING) uses for the Monday brief; write that order in the dashboard's own query, since the dashboard reads only the ledger (AGENTS.md rule 1).
- Pursuing and Submitted read each call's decision (human_status pursue or submitted, with human_by and human_at), in phase 1's look; phase 5 brings them, Results and Automation to the design.
- Pursuing's two sections (P5 to P8): the Draft button and draft progress need the drafts queue and worker (docs/plans, Draft-Ready Upgrade U1 and Writer Plan W2a). If they are not on main yet, list the calls in both sections, show Draft as not set up yet, and say so in the PR.
- Profile settings (U2 to U6): display name and initials, where the dashboard opens, default filters for Calls and time zone, kept for this browser until sign-in.
- Where the design and the spec disagree, the spec wins on behaviour and the design on look; ask David about anything else with the questions prompt.

Tests first:
- Failing unit tests (dashboard/lib/*.test.ts) for Home's logic: the Top 10 order, the 14-day window (pursued calls first, deadlines that are not dates left out), and days waiting for submitted calls.
- Browser tests (tests/test_dashboard_*.py): the top bar shows the four sections, each tab opens at its own address, old addresses still land on the right view, Home shows its blocks or their empty states, the account menu switches user and logs out, and each Profile setting takes effect (landing page, default filters, time zone). Browser tests only read and set cookies: none may record a decision.
- At the end: npm test, npm run build, pytest, and every tests/test_dashboard_*.py against the dev server with DASHBOARD_TEST_URL set. Point the existing browser tests at /review where they used the queue at /; never weaken what they check.

Process, as in phase 1: a Linear issue first (team Product, project BD Automation); branch dashboard/structure-and-home; commit feat(dashboard): Home, four sections and the account menu PRO-NNN with a ref line and nothing else; no en or em dashes anywhere; nothing login-gated committed; update docs/DASHBOARD.md (its Pages table) and docs/STATUS.md; open the PR, squash-merge once verified, switch to main and pull, mark the issue Done with a comment, and add a row to the "Since 21 Oct" table in Shaun's review doc.

Done when the four sections, Home, the account menu and Profile settings work at their addresses, old links still land, all tests pass and the PR is merged.
```

## Prompt 3: To review

Rebuilds the main working screen to the design, keeping every queue, filter, decision, settings and layout requirement.

```text
Phase 3 of 6 of the dashboard redesign: rebuild Calls, To review (/review, the review queue) to the design. Phases 1 (theme foundation) and 2 (the four sections and Home) are merged on main.

Read first: AGENTS.md, docs/STATUS.md and docs/DASHBOARD.md; the design <DESIGN_LINK> (the To review artboards, the enlarged row, the menus, notices and empty states); the spec docs/design/dashboard-design-spec.md, sections Pages, Calls: To review, Details tags and badges, Filters sorting and links, Deciding, Settings, Layout and responsiveness, Formats and empty states, Accessibility and writing rules; then the To review page under dashboard/app/ and the components and lib files it uses. If you cannot open the design, ask David to export it into docs/design/redesign/.

Build To review as designed while keeping Q1 to Q12, N5 to N6, F1 to F11, V1 to V9, S1 to S6, L1 to L7, T1 to T7, A1 to A5 and W1 to W3. In particular:
- Denser rows that still show everything a decision needs: both judges' verdicts and the disagreement flags, Grok's reason, the title link, the details line, the tags line, the deadline and why one is missing, Claude's reason, first seen, the votes so far, the note and the Decide menu (Q9).
- Information that is hover-only today stays reachable from the keyboard (A4).
- Settings still hides and shows each column and the tags line; hidden columns give their width to the rest.
- No sideways scroll and no hidden columns from 1024px to 2560px.
- A vote still shows the notice with its link to everyone's votes (Q10), and the call still leaves the voter's queue.
- Where the design and the spec disagree, the spec wins on behaviour and the design on look; ask David about anything else with the questions prompt.

Tests first:
- Failing unit tests (dashboard/lib/*.test.ts) for any new display logic, and browser tests (tests/test_dashboard_*.py) for the new behaviour. Browser tests may set cookies but must never record a decision: they can run against a dashboard on the live ledger.
- At the end: npm test, npm run build, pytest, and every tests/test_dashboard_*.py against the dev server with DASHBOARD_TEST_URL set.
- Compare your 1440px and 1024px screenshots (scratchpad only) with the design.

Process, as in phase 1: a Linear issue first (team Product, project BD Automation); branch dashboard/review-redesign; commit feat(dashboard): To review in the Velocity Theme PRO-NNN with a ref line and nothing else; no en or em dashes anywhere; nothing login-gated committed; update docs/DASHBOARD.md and docs/STATUS.md; open the PR, squash-merge once verified, switch to main and pull, mark the issue Done with a comment, and add a row to the "Since 21 Oct" table in Shaun's review doc.

Done when To review matches the design, every listed requirement holds, all tests pass and the PR is merged.
```

## Prompt 4: All calls

Rebuilds Calls, All, reusing what prompt 3 built for rows, details, tags and verdicts.

```text
Phase 4 of 6 of the dashboard redesign: rebuild Calls, All (/calls) to the design. Phases 1 to 3 are merged on main; reuse what phase 3 built for rows, details, tags and verdicts.

Read first: AGENTS.md, docs/STATUS.md and docs/DASHBOARD.md; the design <DESIGN_LINK> (the All artboards, the votes and the decide control); the spec docs/design/dashboard-design-spec.md, sections Calls: All, Details tags and badges, Filters sorting and links, Deciding, Settings, Layout and responsiveness, Formats and empty states, Accessibility and writing rules; then dashboard/app/calls/page.tsx and what it uses. If you cannot open the design, ask David to export it into docs/design/redesign/.

Build All as designed while keeping C1 to C8, N5 to N6, F1 to F11, V1 to V9, S1 to S6, L1 to L7, T1 to T7, A1 to A5 and W1 to W3. In particular:
- The title search; the filter's result, tier and reason for rejected calls; both judges' reasons; each person's decision with its time; the people disagree flag; every note with its author and time.
- The decide control: decide, change or add yours, with the decision, an optional note and Save. A stale form still writes nothing and says what the call is now (C8).
- 200 rows per page with the Showing N of M line; every filter and sort is still a link that can be shared.
- Where the design and the spec disagree, the spec wins on behaviour and the design on look; ask David about anything else with the questions prompt.

Tests first, as in phase 3: failing unit and browser tests for what changes (browser tests never record a decision), then npm test, npm run build, pytest and every tests/test_dashboard_*.py against the dev server; compare screenshots at 1440px and 1024px with the design.

Process, as in phase 1: a Linear issue first (team Product, project BD Automation); branch dashboard/calls-redesign; commit feat(dashboard): All calls in the Velocity Theme PRO-NNN with a ref line and nothing else; no en or em dashes anywhere; nothing login-gated committed; update docs/DASHBOARD.md and docs/STATUS.md; open the PR, squash-merge once verified, switch to main and pull, mark the issue Done with a comment, and add a row to the "Since 21 Oct" table in Shaun's review doc.

Done when All matches the design, every listed requirement holds, all tests pass and the PR is merged.
```

## Prompt 5: Proposals, Automation and past briefs

Brings Proposals' three tabs, Automation's three tabs and the past weekly briefs to the design, keeping what each does.

```text
Phase 5 of 6 of the dashboard redesign: bring Proposals (Pursuing, Submitted, Results), Automation (Requests, Scans, Judges) and the past weekly briefs (/brief) to the design. Phases 1 to 4 are merged on main.

Read first: AGENTS.md, docs/STATUS.md and docs/DASHBOARD.md (its Pages table and The write actions); the design <DESIGN_LINK> (these pages' artboards and the empty states); the spec docs/design/dashboard-design-spec.md, sections Pages, Proposals, Formats and empty states, Accessibility and writing rules, Build constraints; then each of these pages under dashboard/app/. If you cannot open the design, ask David to export it into docs/design/redesign/.

Keep what each does today:
- Pursuing and Submitted: P1, P2, P4 and P5 to P8, each row linked to its call on All.
- Results: past submissions from the Proposal Register with win rate by portal, and its empty state (P3).
- Requests: waiting requests first (who asked, why, the preview, Approve and Reject with a note), then the last 50 decided with their result, and the count on Automation in the top bar (N3). A request decided elsewhere is never overwritten.
- Scans (today's Runs page): the latest run on top with status, start, duration, stage counts, error and log link, then the last 100; a run still running after two hours is flagged.
- Judges: per judge (matched, misses, false alarms, maybes), per person, between people, and the pursued calls a judge said no to. Only verdicts given before anyone decided the call count.
- Past briefs: the week as Monday's Slack post had it; the Top 10 across portals; a board per portal (new calls by verdict, calls waiting, top picks, pursued calls closing within 14 days, the week's decisions, the scraper line); each call's decision as of now; links to earlier weeks.
- Every page's empty state, and its migration notice where one applies.
- Where the design and the spec disagree, the spec wins on behaviour and the design on look; ask David about anything else with the questions prompt.

Tests first, as in phase 3, plus a browser test per page that it renders with the new look. Browser tests only read: none may approve or reject a request or record a decision. Then npm test, npm run build, pytest and every tests/test_dashboard_*.py against the dev server; compare screenshots with the design.

Process, as in phase 1: a Linear issue first (team Product, project BD Automation); branch dashboard/pages-redesign; commit feat(dashboard): Proposals, Automation and past briefs in the Velocity Theme PRO-NNN with a ref line and nothing else; no en or em dashes anywhere; nothing login-gated committed; update docs/DASHBOARD.md and docs/STATUS.md; open the PR, squash-merge once verified, switch to main and pull, mark the issue Done with a comment, and add a row to the "Since 21 Oct" table in Shaun's review doc.

Done when these pages match the design, all tests pass and the PR is merged.
```

## Prompt 6: finishing pass

Checks keyboard, contrast, widths and wording across every page, removes leftovers, and ticks off every requirement in the spec.

```text
Phase 6 of 6 of the dashboard redesign: the finishing pass. Phases 1 to 5 are merged on main.

Read first: AGENTS.md, docs/STATUS.md and docs/DASHBOARD.md; the design <DESIGN_LINK>; and the whole spec docs/design/dashboard-design-spec.md, especially Accessibility and writing rules, Layout and responsiveness, and the Decision log. If you cannot open the design, ask David to export it into docs/design/redesign/.

Check and fix, across every page:
1. Keyboard: tab from the top bar through Home and To review to a decision, open and close each menu, switch tabs, open the account menu and Table settings and leave each with Escape; focus always visible.
2. Contrast: text and badges meet WCAG AA (4.5:1 for text) in every theme the design has.
3. Widths: no sideways scroll and no hidden columns from 1024px to 2560px; below 1024px the page stays usable and only a table scrolls inside itself.
4. Words: no en or em dash anywhere in the UI, code or docs (read the files as UTF-8 when you search, since piping text through the shell on this PC decodes it as cp1252); labels in sentence case; status always written as a word.
5. Leftovers: delete CSS, classes, components and pages nothing uses any more.
6. The spec: walk every requirement ID and tick it off; fix what fails, and list in the PR anything the design changed on purpose.

Then:
- Update docs/DASHBOARD.md to describe the new look, sections and components, and docs/STATUS.md.
- In docs/design/dashboard-design-spec.md, add screenshots of Home, To review and All to its Current UI section (saved in docs/design/screens/; public-portal calls only, never Vulcan SOF), and a row to its Decision log.
- Tests: whatever the fixes need first; then npm test, npm run build, pytest and every tests/test_dashboard_*.py against the dev server.

Process, as in phase 1: a Linear issue first (team Product, project BD Automation); branch dashboard/redesign-finish; commit fix(dashboard): accessibility, widths and cleanup after the redesign PRO-NNN with a ref line and nothing else; no en or em dashes anywhere; nothing login-gated committed; open the PR, squash-merge once verified, switch to main and pull, mark the issue Done with a comment, and add a row to the "Since 21 Oct" table in Shaun's review doc. Then ask David what to work on next with the questions prompt.

Done when every spec requirement is ticked off or explained, all tests pass and the PR is merged.
```

## Update prompt: Claude Design

For a design made from the earlier prompt 0, before 26 Oct, for the seven pages. Paste it into the same Claude Design project: it keeps what is drawn and adds what changed.

```text
Update the BD dashboard design you made earlier. On 26 Oct the structure changed: four sections replace the seven pages, Home is new, and your account menu is now part of the spec. Keep everything already designed (tokens, components, rows, menus, notices, the account menu); move the existing screens into the new structure and design only what is new.

Read first, from the public repo Velocity-Explorations/velocity-bd-team (plain text: https://raw.githubusercontent.com/Velocity-Explorations/velocity-bd-team/main/ followed by the path):
- docs/design/dashboard-design-spec.md: https://github.com/Velocity-Explorations/velocity-bd-team/blob/main/docs/design/dashboard-design-spec.md
  The sections that changed: Pages (N1 to N6), Home (H1 to H5), Proposals (P1 to P8), Account menu and profile (U1 to U6), Deciding (V1 to V4), Q9 under Calls: To review, and the 26 Oct rows of the Decision log. The rest is unchanged since your first design.

The new structure:
- Top bar: Home, Calls, Proposals and Automation, with the Requests count as a badge on Automation, and your account menu at the right.
- Home (/): the new landing page.
- Calls: tabs To review (/review, your Review queue screen) and All (/calls, your All calls screen). Switching tabs keeps the portal, tag and open or closed filters.
- Proposals: tabs Pursuing (/proposals) and Submitted (/proposals/submitted), both new, and Results (/proposals/results, your Proposals screen). Pursuing has two sections: Ready to draft, with a Draft button on each call, and Drafting.
- Automation: tabs Requests, Scans (your Runs screen, renamed) and Judges. Automation opens on Requests.
- Past weekly briefs (/brief): your Monday brief screen, now outside the top bar and linked from Home.
- Account menu: as you drew it (Profile settings, Table settings, Switch user, Log out). Profile settings is a new page.
- Decide: keep your Decide menu; the spec now asks for it (Q9).

Artboards, 1440px wide unless noted:
- Home with every block filled: Ready for review (waiting for you, split yes and maybe, new this week, a link to start reviewing), Top 10 (both verdicts, title, portal, deadline), Due in the next 14 days (pursued calls first, then undecided yes and maybe calls, with days left), Submitted and waiting (portal, who marked it and when, days waiting), the status line (requests waiting, the last scan's result and time, judges agree %), and the link to past briefs.
- Home at 1024px.
- Home with every block empty.
- The tab component, and the top bar with each section selected.
- Proposals, Pursuing: Ready to draft with Draft buttons, plus a members-only call that cannot be drafted and says why; Drafting with a queued, a running (with progress), a finished (with its readiness line and Open) and a failed draft (with Retry).
- Proposals, Submitted.
- Profile settings: display name and initials, the signed-in account (shown once Google sign-in is live), where the dashboard opens (Home or To review), default filters for Calls (portals, tags, open or closed) and time zone, with Save.
- Every existing screen moved into the new top bar and tabs: To review, All, Results, Requests, Scans, Judges and the past brief.

Goals: Home answers what needs attention now at a glance, ideally without scrolling at 1440px. Reuse your existing components (stat tiles, badges, rows) before adding new ones.

Rules, as before: no en dash or em dash anywhere (write ranges with "to"); plain sentence-case labels; status always written as a word, never shown by colour alone; real content from the snapshot (https://github.com/Velocity-Explorations/velocity-bd-team/tree/main/docs/design/dashboard-snapshot), never placeholder text. The snapshot has no submitted calls, so mark one of its yes calls Submitted for the example.

Update the handoff note: list the new and changed artboards, any new components or tokens (the tabs, Home's blocks, Profile settings), and any spec requirement you could not meet and why.
```
