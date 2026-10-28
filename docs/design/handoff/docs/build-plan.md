# Build plan

How to build the redesign on the codebase as it is at 65a5fce. Facts about today come from `docs/design/handover-discovery.md` (cited as discovery Qn). Requirement IDs are from spec-updates.md.

## Architecture

The rule that components talk only through the ledger (AGENTS rule 1) stays.

- **Dashboard (Next.js):** reads the ledger and writes rows through server actions with guarded updates. It never calls Anthropic, Drive or Slack.
- **Worker (new, Python, on David's PC):** always on. Claims queued workspace steps, runs them with the Anthropic client in `drafting/llm.py`, writes Word files to Drive, reports state back to the ledger.
- **`run.py` jobs:** Slack posts (step ready, behind, digest), the Drive index refresh, and the Register write on submit.

Every workspace button writes a row; the page shows that row's state. That is what makes "working", "ready" and "failed" visible.

## Data: migration 008

Take discovery Q1's sketch of `pursuits`, `pursuit_steps` and `step_changes` as written (portable SQL, `@@AUTOINCREMENT@@`, JSON as TEXT, ISO-8601 UTC text). Add:

- `pursuits.cost_usd REAL NOT NULL DEFAULT 0` and `pursuits.budget_usd REAL`: default 200. The worker stops and marks the step failed with "budget reached" when the next step would pass it (PW19).
- `pursuits.target_dates TEXT`: JSON of step to target date, worked back from the deadline, for the behind message (PW18).
- `pursuits.collaborators TEXT` (JSON list of names from `DASHBOARD_USERS`), `pursuits.result_expected_by TEXT` and `pursuits.result_expected_source TEXT` (the call's words and where they were found, or `default, 90 days after the deadline`), set by Discovery (P4, PW24).
- `pursuit_steps.cost_usd REAL` and `pursuit_steps.task_states TEXT` (JSON, Discovery's eight tasks, PW6).
- `pursuit_events` for Show history (PW16): id, pursuit_id, at, who (a person or worker), kind, text. Written by the dashboard's actions and by the worker.
- `drive_items` for the Builds on picker: id (Drive file id), name, mime, path, parent_id, modified_at, indexed_at. Filled by the worker from the shared drive; the dashboard searches it.
- Later and separate: `proposals.source_call_id TEXT`, the Proposal Library plan's link from a Register row to its call (discovery Q6).

`step` stays free text, validated in code against this list: `discovery`, `summary`, `alignment`, `requirements`, `go_no_go`, `outline`, `draft`, `compliance`, `reviews`, `final`, `submit`.

The same PR updates `docs/LEDGER_SCHEMA.md`, `ledger/schema.sql` and `tests/test_migrate.py`. Coordinator only, additive only.

## Steps: how each design step is built

The design's steps are the contract the dashboard shows; the work reuses `drafting/` phases (discovery Q10) wherever one exists.

| Step | Built from | Output saved to Drive | Person |
| --- | --- | --- | --- |
| Discovery | Phases Listing, Attachments, Past experience, plus the clash check and the dashboard record | Discovery summary, the call page as PDF, attachments into `00_solicitation/` | Approves, or adds material |
| Opportunity summary | New prompt from the opportunity-assessment skill | Opportunity summary | Continues |
| Alignment | Phase Alignment, extended with the judges' reasons, notes, Builds on and the owner's direction | Alignment, the direction carried forward | Picks the direction |
| Requirements and checklist | Phases Requirements and Checklist | Requirements and Submission Checklist | Approves; checklist items become rows in `pursuits.checklist` |
| Go or no-go | Gate | none | Go, or No-go with a note |
| Outline | Phase Outline | Outline | Approves; locks the direction and Builds on |
| First draft | Phase Draft | Draft v1 | Approves |
| Compliance check | Phase Compliance | Compliance report, Draft v2 | Approves |
| Reviews | Slop check (phase 7.7, `drafting/slop_gate.py`) automatically on each new draft, then the review passes as three personas | Each pass's review and next draft; proposed changes as `step_changes` rows | Accepts, rejects or edits each change |
| Final checks | Phases Polish and Opening | Final files | Ticks the checklist |
| Submit | Gate | Moves submitted files to `01_submitted/` | Confirmation number, expected by date, Mark submitted |

Prompts come from the two skills and live as text files in `drafting/prompts/` in the public repo. By default every skill the workflow uses is also committed as it is under `.claude/skills/<name>/SKILL.md` (from `handover/skills/`), so Claude Code and David's Claude read the same text. The AI slop detection skill stays in its private repo. `handover/prompts/opportunity_assessment.md` and `handover/prompts/proposal_drafting.md` are the two skills adapted to the workspace, from the complete skills, ready to commit as is. The skills' check-ins become the dashboard's approvals.

## AI slop check

The scanner comes from the private repo Velocity-Explorations/ai-slop-detection. None of its code, word lists or guidance text goes into this public repo; the worker calls it from its install path, set in `.env` as `AI_SLOP_SCAN`, as `drafting/slop_gate.py` does today (phase 7.7).

- **When:** on every new draft (v1 onward), and when the owner chooses Check again (a queued `slop_scan` step attempt).
- **How:** `slop_scan.py --profile proposal --json --solicitation <solicitation text> <draft>`, on the draft's Markdown. The worker first applies the fixes it can make on its own (house rules, tool residue, tracking parameters, and rewrites per the skill's revision guidance), saves the next draft, then scans again and stores that result.
- **Stored:** a new table `slop_scans`, with these columns:
  - id, pursuit_id, step_id, draft_file_id, scanned_at;
  - words, band, confidence, points, provisional;
  - verdict (the one-line text from `slop_gate.py`);
  - fixed_count;
  - result_json (the scanner's JSON as returned);
  - text_lines (the scanned text, so the page can show a line without opening Word).
- **Shown:** the page reads the newest row for the pursuit's newest draft, and never runs the scanner. The gate rule (Ready, provisional, no band under 150 words, low confidence under 300) is computed in `slop_gate.py` and stored, so the page and Slack say the same thing.
- **Words:** labels and messages report patterns and fixes only; never AI authorship or a probability of it (PW23). Add a test that fails if any template or message string contains "written by AI", "AI-generated", "probability" or "likely AI".

## Worker

- **What it is:** the Writer Plan's W2a worker (`docs/plans/writer-plan.html:121`, `:257`). One process on David's PC, started at logon by Task Scheduler with restart on failure, registered in `scripts/install-schedule.ps1` with a test in `tests/test_schedule_script.py`.
- **Its own lock:** `data/worker.lock`, never `data/pipeline.lock`, so Sunday's scan is not held up.
- **Claiming:** polls every 20 seconds and claims one queued step at a time with a guarded update (the `claim_request` pattern, `ledger/queries.py:436`). It sets `working` and `started_at`, then `ready`, or `failed` with the error.
- **Running a step:** runs it from saved state (`drafting/cli.py` `--from-phase` and `--to-phase`). Records its cost on the step and the pursuit, and writes a `pursuit_events` row.
- **Key gates only:** the worker approves non-gate steps itself, as decided_by `worker (key gates only)`, and queues the next one (PW5).
- **Ask for changes:** the dashboard sets the step `changes_asked` with the note. The worker re-runs it as attempt n+1 with the note in the prompt.
- **Cancel:** when the dashboard sets the pursuit to closed, the worker stops at the next phase boundary.

## Drive and Word

- **Access:** a Google Cloud project with the Drive API, and a service account added to a shared drive holding the Proposal Library. Its key file sits on the PC, outside the repo, named in `.env` as `GOOGLE_SERVICE_ACCOUNT_FILE`.
- **Folders:** the Library convention (`docs/LIBRARY_CONVENTIONS.md:5-16`). On Start the draft the worker creates `Submissions/<YYYY-MM-DD_portal_short-title>/` dated that day, with `00_solicitation/`, `01_submitted/`, `02_working/` and `03_outcome/`, and stores `drive_folder_id`. Drafts go to `02_working/`; submitted files move to `01_submitted/`; debriefs go to `03_outcome/`. No-go moves the folder to `Submissions/_no-go/`.
- **Word:** python-docx, added to `requirements.txt`. There is no house template: each file follows the format its solicitation sets (font, margins, spacing and page limits from the requirements document), with plain defaults where the solicitation says nothing. Markdown stays the working format inside the worker; each saved step is converted and uploaded, and the Drive file id and link go into `pursuit_steps.files`.
- **Tracked changes:** for v1, changes are decided on the dashboard and the accepted text goes into the next draft (David, 27 Oct).
- **Choose from Drive:** the dashboard searches `drive_items`, which the worker refreshes every 15 minutes and on demand (a `drive_refresh` row).
- **Upload files:** in v1 the person puts files in the pursuit's `Builds on/` folder in Drive and chooses Refresh; the worker indexes them. A direct upload needs either an exception to AGENTS rule 1 or a ledger blob table; neither is proposed.

## Slack

- Add `thread_ts` to `slack/sink.py`'s post (no new scope).
- When a pursuit starts on a call with no card, `run.py` posts its card first.
- New `run.py` jobs: step ready (every 5 minutes, posts once per step, mentioning the owner and the people working with them), behind target (daily 08:00), and the digest (daily 08:00: steps waiting on each owner, and checklist items each person can tick). Each reads the ledger only.

## Sign-in

- **Google, inside the dashboard,** for example Auth.js with the Google provider, limited to the company Google Workspace domain and to `DASHBOARD_USERS`. A Google account not on the list sees "not allowed" on the sign-in page.
- **The sign-in page** is /login (spec U7, `BD Team Login.dc.html`). Signed out, every page sends you there; Log out ends the session and returns there with "You are logged out of BD Team."
- **Why not IAP alone:** IAP shows Google's own page before the dashboard loads, so /login would never show. If IAP stays for other reasons, drop /login and the Log out page instead. Decide this with PRO-477.
- **The viewer** becomes the signed-in Google account's name from `DASHBOARD_USERS`, replacing the self-asserted viewer cookie; Switch user goes away once sign-in is live.

## Sign-in and ownership

- **Owner:** the viewer who started the pursuit, `pursuits.owner`. Server actions refuse approvals from anyone else with "Only the owner, {name}, can approve this step." Until IAP is live this is a courtesy check, since the viewer cookie is self-asserted (discovery Q3).
- **People working with the owner:** names in `pursuits.collaborators`. Server actions let them add material, add Builds on and tick checklist items; approvals, gate decisions and change decisions stay owner only (PW17, PW24).
- **Decision makers:** add Lisa and Alec to `DASHBOARD_USERS` (configuration, not code).
- **Roles:** none needed beyond owner and working with. The leadership pass is a Claude persona, not a person.
- **Later:** after PRO-477, take the viewer from IAP's verified email and match it to `DASHBOARD_USERS`.

## Concurrency

- **Step forms:** carry the step's `state` and `updated_at`. Actions update `WHERE id = ? AND state = 'ready' AND updated_at = ?`; with no match, they say what the step is now (C8's pattern, discovery Q9).
- **Change rows:** `step_changes` decisions are guarded on `state = 'proposed'`.
- **Mark submitted and No-go:** call `decideCall` with the expected decision.

## Routes

- **Proposal workspace:** `/proposals/[callId]`.
- **Views:** a `view` search parameter on /review, /calls, /proposals, /requests and /runs, read with the helpers in `dashboard/lib/filters.ts`.
- **Old paths:** keep /proposals/submitted and /proposals/results as routes that render their views (N4).

## Pull requests, in order

Each PR gets its own Linear ticket and its own branch, starts from failing tests, keeps the docs updated, and is squash-merged with the ticket id in its subject.

| # | Pull request | Covers | Tests |
| --- | --- | --- | --- |
| 1 | Spec updates (docs only) | spec-updates.md | `test_design_brief.py` passes with the new IDs |
| 2 | Migration 008 | Data | `test_migrate.py` lists the new tables; a round trip on SQLite |
| 3 | Theme tokens and components | `velocity-theme/` into `dashboard/` styles | `node --test` for any class helpers |
| 4 | View cards and routes on Calls, Proposals and Automation; Home with link cards and the Top 10 | N1 to N6, VC1 to VC4, H1 to H5 | Display logic unit tests; read-only browser tests for each address |
| 5 | Description column | Calls Q (next), H2, Data per call | Query test that selects 300 characters; scanner summary label |
| 6 | Proposals views; Start the draft writes a queued pursuit; badges everywhere; Start the draft from any row | P1 to P6, DB1 to DB3, Q9 | Server action tests for the refusals in P2 and P6 |
| 7 | Worker: claiming, steps from `drafting/`, cost and budget, key gates only | P8, PW5, PW15, PW19 | pytest with a fake LLM client; lock separation |
| 8 | Drive and Word in the worker; `drive_items` index | Drive and Word | pytest against a fake Drive client; no live calls in tests |
| 9 | Workspace page: steps, cards, approvals, Ask for changes, checklist, history, ownership | PW1 to PW11, PW13, PW16, PW17 | Guarded update tests; browser tests read only |
| 10 | Reviews change by change; the AI slop check result | PW12, PW20 to PW23 | `step_changes` decisions and the approve-when-all-decided rule; `slop_scans` rows from fixture JSON; the gate and wording tests |
| 11 | Submit gate, Submitted and waiting, Record result, Register write | PW14, P4, P5, P7, V6 | Mapping cancelled_by_agency to no_award; result overdue and No news yet |
| 12 | Slack threads, ready, behind and digest jobs | PW18 | `test_schedule_script.py`; sink tests with a fake client |
| 13 | Ownership enforced from IAP | PW17 after PRO-477 | IAP header tests in `dashboard/lib/iap.ts` |

PRs 4 and 5 need no backend changes. PR 6 works before the worker exists: P8 says drafting is not set up yet.

## Risks

- **The PC must be on** for steps to move.
- **Login-gated solicitations** (Vulcan SOF, NSTXL member pages) may be drafted now, by David's decision. Their text, generated files and logs stay in Drive and on the PC, never in the repo.
- **Deadlines are portal text.** Reuse the parsing the 08:00 reminder already does for target dates and expected by; a deadline that is not a date gets no target dates and no behind message.
- **AGENTS.md is out of date:** it still says the ledger is SQLite. Fix it in PR 2.
