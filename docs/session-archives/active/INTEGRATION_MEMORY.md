# Integration Memory

Session log for velocity-bd-team, read whole by `/continue`. Each entry is a pointer: what
changed, what was decided, what is still open. The evidence lives in the PRs, Linear issues
and docs it links. This repo is public, so nothing here may name a credential or quote
portal content.

<!-- New sessions are added directly below this line, newest first. -->

## Current Session

**Date**: 2026-10-25
**Focus**: Dashboard redesign brief for Claude Design: spec, snapshot, build prompts and the Velocity Theme, in the repo

### What Was Done
- Redesign brief: a design spec of every dashboard requirement and decision (IDs Q1 to B9, the theme's fit, open questions), a static snapshot of the seven pages on public-portal data with sample votes by Analyst A and Analyst B, and six build prompts (0 for Claude Design, 1 to 5 for Claude Code).
- Claude Design runs on the Velocity login, which cannot open David's personal artifacts, so the brief moved into docs/design with the Velocity Theme (PR #51, PRO-559); `tests/test_design_brief.py` checks that every link resolves and nothing written has a dash. The spec and prompts Claude Docs now point at the repo.

### Key Decisions
- The theme zip's example text came from an internal slide deck; the public copy uses this project's own text and writes ranges with "to". The snapshot went in as captured (David).
- The repo copies are the ones to keep current. A finished design comes back as an export in docs/design/redesign/ by pull request, because Claude Code cannot open designs on the Velocity login.

### Key Files Modified
| File | Change |
|------|--------|
| `docs/design/` | Index, spec, build prompts, snapshot pages and screens, velocity-theme |
| `tests/test_design_brief.py` | Parts exist; markdown, HTML, font and GitHub links resolve; no dashes |
| `AGENTS.md`, `docs/STATUS.md`, `docs/DASHBOARD.md` | Point at docs/design |

### In Progress
- David runs prompt 0 in Claude Design; prompts 1 to 5 then build the design, one PR each.
- Monday: check Sunday's 22:00 run, the first to read SAM.gov and to tag new calls in the review.
- Still open from 24 Oct: SAM.gov role (PRO-529), hosting with Alec (PRO-477), NSTXL member sign-in (PRO-531), shared portal account (PRO-509), Register judgment columns (PRO-480).

### Blockers
- AI vendor clearance (PRO-473) is still open. SAM.gov allows 10 requests a day until the role is approved.

## Session: 2026-10-24

**Date**: 2026-10-24 (covers 20 to 24 Oct)
**Focus**: Ten new portals and the first full scan, two judges and the review queue, the dashboard's hosting container, Proposal Register, drafting gates

### What Was Done
- Portals: SSC Front Door (PR #15), SAM.gov (#22, Yukon prior art #21), NSTXL (#23), DIU (#24), AFWERX (#26), SpaceWERX (#28), DOE SBIR (#32), NASA Forecast (#33), Space Florida (#34), APFIT (#35); IARPA (#27) and TRMC/JMETC (#36) through SAM.gov searches. AFWERX and SpaceWERX share `portals/shared/funding_list.py`. BidNet is built but shelved, unmerged, on `bidnet/adapter` (PRO-544).
- Judges and queue: each judge's verdict kept (#11), judges scored against people's decisions (#13), everyone decides every call during training (#14).
- Dashboard: filter panel (#8), Monday brief with a Top 10 (#16), container with Google sign-in through IAP (#20), portal details on call rows (#25, #31, #37). Slack Monday summary (#9); weekly scan on Sunday night (#10).
- Drafting and library: drafting port (#2), a person writes each opening (#17), slop check gate (#18), Proposal Register sync (#19). Flaky assistant test fixed (#29).
- 24 Oct: a dry run of all eleven portals passed, then David started the first full scan a day early: 32 cards (Claude 2 yes, 30 maybe). NSTXL and Front Door ran past their fetch limit because every ledger query opened a new Supabase connection; one reused connection per thread fixed it (#39, PRO-550, 585 to 183 ms a query). Checking its rows on the dashboard led to clearer NASA contacts, set-asides and empty due cells (#40, PRO-551), and every page now fits the window with 24px each side, checked by `tests/test_dashboard_layout.py` against a running dashboard (#42, PRO-552). Review doc for Shaun ("BD Automation Review") is current; its Decisions section lists what waits on him.
- 24 Oct, later: choosing a name under "Deciding as" applies at once, with a Clear User Selection button (#44, PRO-553); a vote's notice says the call left your queue and links to everyone's votes (#45, PRO-554); a Settings dialog picks each table's columns per browser, Tier hidden by default (#46, PRO-555); tags from `review/tags.yaml` on every call, by rules, Claude and Grok (#47, PRO-556; backfill: 183 calls by rule, 121 by each judge), shown under titles with a Tag filter (#48, PRO-557); the filter panel became a bar above the table, and headers sort and filter (#49, PRO-558). A two-person voting demo ran on a throwaway Docker database and was removed.

### Key Decisions
- No getting around a site's block: DSIP (robots.txt) gets cards linking its topic search (PRO-536); IARPA (403) and TRMC (no public listings) come through SAM.gov office and title searches (PRO-537, PRO-548); BidNet (AWS bot challenge after a few requests) is shelved (PRO-544).
- One SAM.gov key with an entity role, not rotated keys (PRO-529). A Front Door repost of a SAM.gov notice is stored once, first copy wins (PRO-525). SAM.gov's v2 search ignores `subtier`; offices are searched by `organizationName`.
- SpaceWERX keeps STRATFI and TACFI notices and AFWERX drops them, until Shaun says whether Velocity holds a Phase II (PRO-538). DOE SBIR and APFIT keep every listing for the judges, since a rejected row is never filtered again.
- Since 24 Oct David's standing rule: PRs are merged without asking once verified.
- A contact links to its address only when a word of the name is in it: NASA's forecast pairs one person's name with another person's address on some rows (PRO-551).
- Tags: David approved the list (one type, plus work, customer and access tags; the customer catch-all is "Other buyer"). Rules set what a call's data makes certain and both judges tag on a TAGS line of their review answers, so no extra model calls. The pipeline copies the list into the ledger's `tag_list` so the dashboard never reads review files (AGENTS rule 1).

### Key Files Modified
| File | Change |
|------|--------|
| `portals/` | ten adapters, `shared/funding_list.py`, SAM.gov office and title searches |
| `dashboard/`, `review/`, `drafting/`, `library/` | Filters, brief, container and IAP, portal details; judges; drafting gates; Register |
| `ledger/db.py` | One Postgres connection kept per thread across transactions (PRO-550) |
| `review/tags.yaml`, `review/tags.py`, migrations 006 and 007 | Tag list, rules, `call_tags` and `tag_list` (PRO-556, PRO-557) |
| `dashboard/components/` | FilterBar, HeaderCell, MenuController, SettingsDialog, ViewerPicker (PRO-553 to PRO-558) |
| `docs/` | STATUS, RUNBOOK, LEDGER_SCHEMA and OWNERS for each portal |

### In Progress
- Monday: check Sunday's 22:00 run, the first to read SAM.gov (24 Oct's 10 requests went to the dry run) and the first to tag new calls in the review, and its SAM.gov rows on the dashboard.
- SAM.gov role for David's key, waiting on Velocity's entity administrator, then the first full ingest (PRO-529). Hosting with Alec (PRO-477), NSTXL member sign-in (PRO-531), shared portal account (PRO-509), Register judgment columns (PRO-480).

### Blockers
- AI vendor clearance (PRO-473) is still open. SAM.gov allows 10 requests a day until the role is approved.

## Session: 2026-10-19

**Date**: 2026-10-19
**Focus**: Pipeline GitHub token, Proposal Library naming and Drive layout, progress update and Linear project, public repo, quieter schedule

### What Was Done
- Fault reports file with the pipeline's own classic token, `BD_GITHUB_TOKEN` (PRs #3, #4; renewal in RUNBOOK "GitHub token").
- The past-submissions collection is now called the Proposal Library everywhere (PR #5). Drive folder "BD Proposal Library" laid out, with folders for Vigilant Eagle 27 and Northern Edge 27.
- Progress update for Shaun (Claude Doc "Velocity BD Progress Update") and Linear project BD Automation, issues PRO-473 to PRO-483.
- Repo made public after a scan of every commit found no credentials.
- Scheduled tasks run in a hidden console; approved requests run at 12:07 and 17:07 (PR #6, PRO-483).

### Key Decisions
- Classic token: fine-grained tokens would need the org to allow them for members.
- Public repo (David): commits, PRs and issues are world-readable, approved fault reports included (AGENTS.md rule 9).
- The dashboard will be hosted on a Velocity domain (PRO-477), not shared from David's PC.
- Hidden consoles over pythonw or S4U: docs/research/decisions/2026-10-19_hidden-task-windows.md.

### Key Files Modified
| File | Change |
|------|--------|
| `run.py`, `config.py` | Pipeline GitHub token (PR #3) |
| `scripts/install-schedule.ps1` | Hidden consoles, requests twice a day (PR #6) |
| `docs/RUNBOOK.md`, `docs/STATUS.md`, `AGENTS.md` | Token, schedule, public repo |

### In Progress
- Drafting port, PR #2: waits on David's read of the sample draft (PRO-474).
- Proposal Library: dates for JATF-26 and Tactical Edge PNT, files into folders (PRO-480), then phase A (PRO-475).

### Blockers
- Vendor clearance (PRO-473) blocks the Grok assistant (PRO-476) and the knowledge base (PRO-478).
