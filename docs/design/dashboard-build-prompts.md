# BD Dashboard Build Prompts

25 Oct 2026, David

Six prompts take the dashboard from today's UI to the Velocity Theme redesign: one for Claude Design, then five for Claude Code, each ending in a merged pull request.

## How to use

Run the prompts in order; each Claude Code run starts from main after the previous pull request merged.

1. Paste prompt 0 into Claude Design on the Velocity account. It reads this folder from GitHub, since the repo is public, and returns a design.
2. Bring the design into the repo. Claude Code runs on David's own login, which cannot open designs on the Velocity account, so export the design from Claude Design (its HTML or handoff bundle, with the handoff note) into `docs/design/redesign/` through a pull request. If a Claude Code session can open the design's link, the link works too.
3. In every Claude Code prompt below, replace `<DESIGN_LINK>` with `docs/design/redesign/` (or the link).
4. Paste prompts 1 to 5 into Claude Code in `C:\Projects\velocity-bd-team`, one session each. Each ends with its pull request merged, its Linear issue done, and a row in Shaun's review doc (BD Automation Review).

Each Claude Code prompt stands alone (AGENTS.md rule 6) and repeats the rules that matter. Where the design leaves a choice open, Claude Code asks you through the questions prompt rather than guessing.

The inputs every prompt reads are in this folder: the [design spec](dashboard-design-spec.md), the [dashboard snapshot](dashboard-snapshot/README.md) and the [Velocity Theme](velocity-theme/README.md).

## Prompt 0: Claude Design

Paste into Claude Design. It designs every screen in the Velocity Theme and ends with a handoff note the Claude Code prompts read.

```text
Design the next version of Velocity's BD triage dashboard in the Velocity Theme design system.

Everything you need is in the public GitHub repo Velocity-Explorations/velocity-bd-team, in docs/design:
https://github.com/Velocity-Explorations/velocity-bd-team/tree/main/docs/design
Its README.md says what each part is. To read a file as plain text, use https://raw.githubusercontent.com/Velocity-Explorations/velocity-bd-team/main/ followed by the file's path.

Read these first:
1. The design spec: https://github.com/Velocity-Explorations/velocity-bd-team/blob/main/docs/design/dashboard-design-spec.md
   Every requirement and decision behind the dashboard. Keep all of them; only their look is open. Its "Velocity Theme fit" section lists where the theme and the dashboard collide (status colours, dark only, date format, where the yellow accent goes, missing app components). Resolve each one and say how.
2. The design system: https://github.com/Velocity-Explorations/velocity-bd-team/tree/main/docs/design/velocity-theme
   README.md is the brand book; tokens.json and tokens.css hold the tokens; components/ holds each component's guidelines and an example; fonts/ and assets/Logos/ hold the typefaces and the Velocity logo. It was made for slides, so extend it to app components rather than replace it.
3. The snapshot of today's UI: https://github.com/Velocity-Explorations/velocity-bd-team/tree/main/docs/design/dashboard-snapshot
   Its README shows ten screenshots; the seven HTML pages keep the real markup, styling and data. Use its calls as the content of your artboards.

Artboards, 1440px wide unless noted:
- Review queue, the main screen: top bar, metric cards, filter bar, and a table with one call in each state: judges agree, judges disagree (yes vs no), a call another person voted on, a member-only call with no deadline, a NASA forecast.
- Review queue at 1024px.
- One queue row enlarged, with every detail, badge and tag variant.
- All calls: a call with two people's disagreeing votes, a rejected call, and the decide control open.
- Menus open: a column header's filter, Portals, Tag.
- The Settings dialog.
- Monday brief, Judges, Requests, Runs and Proposals.
- Notices: done, refused, and the vote notice with its link.
- Empty states for the review queue and All calls.
- Light and dark, unless you decide on dark only; then say why.

Goals: triage at a glance, and use the width well. Rows are tall today; make them denser without hiding anything a decision needs. Keep every piece of hover-only information reachable from the keyboard.

Rules: no en dash or em dash anywhere (write ranges with "to"); plain sentence-case labels; status always written as a word, never shown by colour alone; real content from the snapshot, never placeholder text.

End with a handoff note on the canvas for the developers: the tokens you added to the theme (status colours, table, form and menu styles), the type sizes for the web, the components you defined, and any spec requirement you could not meet and why.
```

## Prompt 1: theme foundation

Brings the theme's tokens, fonts and shared components into the dashboard. Pages keep their layout, so later prompts change one page at a time.

```text
Phase 1 of 5 of the dashboard redesign: bring the Velocity Theme into the dashboard as tokens, fonts and shared components, without changing any page's layout or behaviour.

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
3. Restyle the shared pieces to the design: top bar (Velocity mark, page links, the Requests count, Deciding as picker, Clear User Selection, Settings), page head, metric cards, badges and tags, buttons, text fields and selects, menus (details.menu), the Settings dialog, notices and tables. Keep today's markup and class names where you can, so pages take the look without edits.
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

## Prompt 2: review queue

Rebuilds the main screen to the design, keeping every queue, filter, decision, settings and layout requirement.

```text
Phase 2 of 5 of the dashboard redesign: rebuild the review queue (the / page) to the design. Phase 1 (theme tokens, fonts and shared components) is merged on main.

Read first: AGENTS.md, docs/STATUS.md and docs/DASHBOARD.md; the design <DESIGN_LINK> (the queue artboards, the enlarged row, the menus, notices and empty states); the spec docs/design/dashboard-design-spec.md, sections Review queue, Details tags and badges, Filters sorting and links, Deciding, Settings, Layout and responsiveness, Formats and empty states, Accessibility and writing rules; then dashboard/app/page.tsx and the components and lib files it uses. If you cannot open the design, ask David to export it into docs/design/redesign/.

Build the queue as designed while keeping Q1 to Q12, F1 to F11, V1 to V9, S1 to S6, L1 to L7, T1 to T7, A1 to A5 and W1 to W3. In particular:
- Denser rows that still show everything a decision needs: both judges' verdicts and the disagreement flags, Grok's reason, the title link, the details line, the tags line, the deadline and why one is missing, Claude's reason, first seen, the votes so far, the note and the four decisions.
- Information that is hover-only today stays reachable from the keyboard (A4).
- Settings still hides and shows each column and the tags line; hidden columns give their width to the rest.
- No sideways scroll and no hidden columns from 1024px to 2560px.
- A vote still shows the notice with its link to everyone's votes (Q10), and the call still leaves the voter's queue.
- Where the design and the spec disagree, the spec wins on behaviour and the design on look; ask David about anything else with the questions prompt.

Tests first:
- Failing unit tests (dashboard/lib/*.test.ts) for any new display logic, and browser tests (tests/test_dashboard_*.py) for the queue's new behaviour. Browser tests may set cookies but must never record a decision: they can run against a dashboard on the live ledger.
- At the end: npm test, npm run build, pytest, and every tests/test_dashboard_*.py against the dev server with DASHBOARD_TEST_URL set.
- Compare your 1440px and 1024px screenshots (scratchpad only) with the design.

Process, as in phase 1: a Linear issue first (team Product, project BD Automation); branch dashboard/queue-redesign; commit feat(dashboard): the review queue in the Velocity Theme PRO-NNN with a ref line and nothing else; no en or em dashes anywhere; nothing login-gated committed; update docs/DASHBOARD.md and docs/STATUS.md; open the PR, squash-merge once verified, switch to main and pull, mark the issue Done with a comment, and add a row to the "Since 21 Oct" table in Shaun's review doc.

Done when the queue matches the design, every listed requirement holds, all tests pass and the PR is merged.
```

## Prompt 3: All calls

Rebuilds All calls, reusing what prompt 2 built for rows, details, tags and verdicts.

```text
Phase 3 of 5 of the dashboard redesign: rebuild All calls (the /calls page) to the design. Phases 1 (theme foundation) and 2 (review queue) are merged on main; reuse what phase 2 built for rows, details, tags and verdicts.

Read first: AGENTS.md, docs/STATUS.md and docs/DASHBOARD.md; the design <DESIGN_LINK> (the All calls artboards, the votes and the decide control); the spec docs/design/dashboard-design-spec.md, sections All calls, Details tags and badges, Filters sorting and links, Deciding, Settings, Layout and responsiveness, Formats and empty states, Accessibility and writing rules; then dashboard/app/calls/page.tsx and what it uses. If you cannot open the design, ask David to export it into docs/design/redesign/.

Build All calls as designed while keeping C1 to C8, F1 to F11, V1 to V9, S1 to S6, L1 to L7, T1 to T7, A1 to A5 and W1 to W3. In particular:
- The title search; the filter's result, tier and reason for rejected calls; both judges' reasons; each person's decision with its time; the people disagree flag; every note with its author and time.
- The decide control: decide, change or add yours, with the decision, an optional note and Save. A stale form still writes nothing and says what the call is now (C8).
- 200 rows per page with the Showing N of M line; every filter and sort is still a link that can be shared.
- Where the design and the spec disagree, the spec wins on behaviour and the design on look; ask David about anything else with the questions prompt.

Tests first, as in phase 2: failing unit and browser tests for what changes (browser tests never record a decision), then npm test, npm run build, pytest and every tests/test_dashboard_*.py against the dev server; compare screenshots at 1440px and 1024px with the design.

Process, as in phase 1: a Linear issue first (team Product, project BD Automation); branch dashboard/calls-redesign; commit feat(dashboard): All calls in the Velocity Theme PRO-NNN with a ref line and nothing else; no en or em dashes anywhere; nothing login-gated committed; update docs/DASHBOARD.md and docs/STATUS.md; open the PR, squash-merge once verified, switch to main and pull, mark the issue Done with a comment, and add a row to the "Since 21 Oct" table in Shaun's review doc.

Done when All calls matches the design, every listed requirement holds, all tests pass and the PR is merged.
```

## Prompt 4: the other pages

Brings the Monday brief, Judges, Requests, Runs and Proposals to the design, keeping what each page does.

```text
Phase 4 of 5 of the dashboard redesign: bring the Monday brief (/brief), Judges (/judges), Requests (/requests), Runs (/runs) and Proposals (/proposals) to the design. Phases 1 to 3 are merged on main.

Read first: AGENTS.md, docs/STATUS.md and docs/DASHBOARD.md (its Pages table and The write actions); the design <DESIGN_LINK> (these five pages' artboards and the empty states); the spec docs/design/dashboard-design-spec.md, sections Pages, Formats and empty states, Accessibility and writing rules, Build constraints; then each page under dashboard/app/. If you cannot open the design, ask David to export it into docs/design/redesign/.

Keep what each page does today:
- Monday brief: the week as Monday's Slack post had it; the Top 10 across portals; a board per portal (new calls by verdict, calls waiting, top picks, pursued calls closing within 14 days, the week's decisions, the scraper line); each call's decision as of now; links to earlier weeks.
- Judges: per judge (matched, misses, false alarms, maybes), per person, between people, and the pursued calls a judge said no to. Only verdicts given before anyone decided the call count.
- Requests: waiting requests first (who asked, why, the preview, Approve and Reject with a note), then the last 50 decided with their result, and the count in the top bar. A request decided elsewhere is never overwritten.
- Runs: the latest run on top with status, start, duration, stage counts, error and log link, then the last 100; a run still running after two hours is flagged.
- Proposals: past submissions with win rate by portal, and its empty state.
- Every page's empty state, and its migration notice where one applies.
- Where the design and the spec disagree, the spec wins on behaviour and the design on look; ask David about anything else with the questions prompt.

Tests first, as in phase 2, plus a browser test per page that it renders with the new look. Browser tests only read: none may approve or reject a request or record a decision. Then npm test, npm run build, pytest and every tests/test_dashboard_*.py against the dev server; compare screenshots with the design.

Process, as in phase 1: a Linear issue first (team Product, project BD Automation); branch dashboard/pages-redesign; commit feat(dashboard): the brief, judges, requests, runs and proposals pages in the Velocity Theme PRO-NNN with a ref line and nothing else; no en or em dashes anywhere; nothing login-gated committed; update docs/DASHBOARD.md and docs/STATUS.md; open the PR, squash-merge once verified, switch to main and pull, mark the issue Done with a comment, and add a row to the "Since 21 Oct" table in Shaun's review doc.

Done when all five pages match the design, all tests pass and the PR is merged.
```

## Prompt 5: finishing pass

Checks keyboard, contrast, widths and wording across every page, removes leftovers, and ticks off every requirement in the spec.

```text
Phase 5 of 5 of the dashboard redesign: the finishing pass. Phases 1 to 4 are merged on main.

Read first: AGENTS.md, docs/STATUS.md and docs/DASHBOARD.md; the design <DESIGN_LINK>; and the whole spec docs/design/dashboard-design-spec.md, especially Accessibility and writing rules, Layout and responsiveness, and the Decision log. If you cannot open the design, ask David to export it into docs/design/redesign/.

Check and fix, across every page:
1. Keyboard: tab from the top bar through the queue to a decision, open and close each menu, open Settings and leave it with Escape; focus always visible.
2. Contrast: text and badges meet WCAG AA (4.5:1 for text) in every theme the design has.
3. Widths: no sideways scroll and no hidden columns from 1024px to 2560px; below 1024px the page stays usable and only a table scrolls inside itself.
4. Words: no en or em dash anywhere in the UI, code or docs (read the files as UTF-8 when you search, since piping text through the shell on this PC decodes it as cp1252); labels in sentence case; status always written as a word.
5. Leftovers: delete CSS, classes and components nothing uses any more.
6. The spec: walk every requirement ID and tick it off; fix what fails, and list in the PR anything the design changed on purpose.

Then:
- Update docs/DASHBOARD.md to describe the new look and components, and docs/STATUS.md.
- In docs/design/dashboard-design-spec.md, add screenshots of the queue and All calls to its Current UI section (saved in docs/design/screens/; public-portal calls only, never Vulcan SOF), and a row to its Decision log.
- Tests: whatever the fixes need first; then npm test, npm run build, pytest and every tests/test_dashboard_*.py against the dev server.

Process, as in phase 1: a Linear issue first (team Product, project BD Automation); branch dashboard/redesign-finish; commit fix(dashboard): accessibility, widths and cleanup after the redesign PRO-NNN with a ref line and nothing else; no en or em dashes anywhere; nothing login-gated committed; open the PR, squash-merge once verified, switch to main and pull, mark the issue Done with a comment, and add a row to the "Since 21 Oct" table in Shaun's review doc. Then ask David what to work on next with the questions prompt.

Done when every spec requirement is ticked off or explained, all tests pass and the PR is merged.
```
