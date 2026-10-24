# Integration Memory

Session log for velocity-bd-team, read whole by `/continue`. Each entry is a pointer: what
changed, what was decided, what is still open. The evidence lives in the PRs, Linear issues
and docs it links. This repo is public, so nothing here may name a credential or quote
portal content.

<!-- New sessions are added directly below this line, newest first. -->

## Current Session

**Date**: 2026-10-24 (covers 20 to 24 Oct)
**Focus**: Six new portals, two judges and the review queue, the dashboard's hosting container, Proposal Register, drafting gates

### What Was Done
- Portals: SSC Front Door (PR #15), SAM.gov (#22, Yukon prior art #21), NSTXL (#23), DIU (#24), AFWERX (#26), SpaceWERX (#28); IARPA through SAM.gov's office search (#27). AFWERX and SpaceWERX share `portals/shared/funding_list.py`. All but Vulcan SOF first run in Sunday's 25 Oct 22:00 scan.
- Judges and queue: each judge's verdict kept (#11), judges scored against people's decisions (#13), everyone decides every call during training (#14).
- Dashboard: filter panel (#8), Monday brief with a Top 10 (#16), container with Google sign-in through IAP (#20), portal details on call rows (#25). Slack Monday summary (#9); weekly scan on Sunday night (#10).
- Drafting and library: drafting port (#2), a person writes each opening (#17), slop check gate (#18), Proposal Register sync (#19). Flaky assistant test fixed (#29).
- Review doc for Shaun ("BD Automation Review") brought up to date on 24 Oct; its Decisions section lists what waits on him.

### Key Decisions
- DSIP's robots.txt forbids automated reading, so SBIR and STTR cycles are cards linking DSIP's topic search (PRO-536). iarpa.gov refuses automated clients, so IARPA is read through SAM.gov, with no workaround (PRO-537).
- One SAM.gov key with an entity role, not rotated keys (PRO-529). A Front Door repost of a SAM.gov notice is stored once, first copy wins (PRO-525).
- SpaceWERX keeps STRATFI and TACFI notices and AFWERX drops them, until Shaun says whether Velocity holds a Phase II (PRO-538).
- SAM.gov's v2 search ignores `subtier`; offices are searched by `organizationName` (portals/sam_gov/NOTES.md).

### Key Files Modified
| File | Change |
|------|--------|
| `portals/` | sam_gov, nstxl, diu, afwerx and spacewerx adapters; `shared/funding_list.py` |
| `dashboard/`, `review/`, `drafting/`, `library/` | Filters, brief, container and IAP, portal details; judges; drafting gates; Register |
| `docs/` | STATUS, RUNBOOK, LEDGER_SCHEMA and OWNERS for each portal |

### In Progress
- Monday 26 Oct: check Sunday's runs, the cards and the dashboard's portal details.
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
