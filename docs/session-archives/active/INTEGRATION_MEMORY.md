# Integration Memory

Session log for velocity-bd-team, read whole by `/continue`. Each entry is a pointer: what
changed, what was decided, what is still open. The evidence lives in the PRs, Linear issues
and docs it links. This repo is public, so nothing here may name a credential or quote
portal content.

<!-- New sessions are added directly below this line, newest first. -->

## Current Session

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
