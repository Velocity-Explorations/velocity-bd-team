# Decisions and where the design and the code disagree

27 Oct 2026. For Claude Code, building in Velocity-Explorations/velocity-bd-team. Read after `docs/design/handover-discovery.md` (commit 65a5fce), which is the record of what exists today; this handover says what to build and how.

## Where the design and the code disagree, and what wins

| Topic | Today | The handover's answer |
| --- | --- | --- |
| Tabs | Spec N2: tabs under a page title | View cards switch each section's table; no page titles or tabs. Old paths keep working (spec-updates, Pages) |
| Workspace tables | `proposals` is the Proposal Register | New tables `pursuits`, `pursuit_steps`, `step_changes`, `pursuit_events` (build-plan, Data) |
| Running steps | Nothing runs on approval; requests wait for 12:07 and 17:07 | An always-on worker on David's PC, the Writer Plan's W2a, with its own lock (build-plan, Worker) |
| Drive and Word | No Google access; drafting writes Markdown locally | A service account on a shared drive, used by the worker only; python-docx for Word files (build-plan, Drive and Word) |
| The dashboard calling Drive or Slack | Not allowed (AGENTS rule 1) | Kept: the dashboard writes ledger rows and reads them back; the worker and `run.py` do the rest. Builds on picks from a Drive index the worker keeps in the ledger |
| Step list | Two skills, the `drafting/` pipeline, and the design | The design's steps are the contract; each maps onto existing `drafting/` phases (build-plan, Steps) |
| Who approves | Anyone on `DASHBOARD_USERS`, self-asserted | The pursuit's owner, with people working with them who can add material and tick the checklist. Shown in the interface now, enforced once Google sign-in (PRO-477) is live. The reviewer and leadership passes are Claude passes, so no roles are needed |
| Submitted | A triage decision anyone can choose | The workspace's Submit gate sets it, through the same guarded `decideCall` (C8). Choosing Submitted on a call with an open pursuit opens its Submit gate instead |
| Result values | Register outcomes: won, lost, no_award, pending, withdrawn, shortlisted | The pursuit keeps its own: won, lost, withdrawn, cancelled_by_agency; cancelled_by_agency becomes no_award when the Register row is written |
| Folder names | Two conventions | The Library convention (`docs/LIBRARY_CONVENTIONS.md`), dated the day the draft starts. A call stopped at go or no-go moves to `Submissions/_no-go/` |

## Decisions from David, 27 Oct

1. **No-go folders** move to a new `Submissions/_no-go/` folder.
2. **Skill text** goes in the public repo under `drafting/prompts/`. `prompts/opportunity_assessment.md` and `prompts/proposal_drafting.md` here are the complete skills adapted to the workspace, ready to commit under `drafting/prompts/`. Its examples (Cobra Gold, Hoverslam, real topic numbers) are cleared to be public.
3. **Login-gated portals are allowed now:** Start the draft works for Vulcan SOF calls and NSTXL member pages. Their text still never goes into the repo, fixtures or logs.
4. **Budget:** a spending cap of $200 per pursuit by default. The worker stops and asks when the next step would pass it.
5. **Refusal wording:** "Log in (top right) before deciding." (spec V4 changes).
6. **Reviewer changes** are decided on the dashboard in v1, and the accepted text goes into the next draft. Word tracked changes come later.
7. **One owner, with people working with them.** The owner stays one person from start to submission and alone approves steps and decides reviewers' changes. Other people can be added to work on the proposal: they add material, tick checklist items and get the Slack messages (PW24).
8. **Decision makers:** add Lisa and Alec to `DASHBOARD_USERS`, so they appear in Switch user, can decide calls, and can own or work on proposals. The prototype shows them as Analyst C and D.
9. **Result expected by** is researched in Discovery: when the call says when results are announced, that date is used, with its source. Otherwise it defaults to 90 days after the deadline (P4).

## Decisions from David, 28 Oct

10. **Sign-in is Google.** BD Team keeps its own sign-in page (`BD Team Login.dc.html`, spec U7): Sign in with Google, Reset password (Google's account recovery), and no Create account, since an admin adds people. Dark only, with no theme switch. For this page to show, sign-in happens inside the dashboard with Google, limited to the company domain and `DASHBOARD_USERS`. IAP in front of the dashboard would show Google's page first and this page never (build-plan, Sign-in).
11. **No house Word template.** Each file follows the format its solicitation sets; the NV022 checklist template is dropped.
12. **Skills ship in the repo by default.** The complete opportunity-assessment and proposal-drafting skills are committed as they are under `.claude/skills/` (from `skills/` here), alongside the workspace prompts in `drafting/prompts/`. The AI slop detection skill is the exception: it stays in its private repo, and the worker calls it from `AI_SLOP_SCAN`.

## House rules

No en dash or em dash anywhere; write ranges with "to". Plain sentence-case labels. Status always written as a word. Nothing login-gated or sensitive (Vulcan SOF content, NSTXL member pages, CUI, credentials) in commits, fixtures, screenshots or logs.
