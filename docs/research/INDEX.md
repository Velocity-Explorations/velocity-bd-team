# Research index

Evidence behind decisions and investigations: one row per document, newest first in each
table. The session log (docs/session-archives/active/INTEGRATION_MEMORY.md) links here
instead of restating it.

## Decisions

| Date | Document | Summary | Tags |
|---|---|---|---|
| 2026-11-16 | [How the scanner reads Vulcan SOF's emailed sign-in code](decisions/2026-11-16_sign-in-code-mailbox.md) | Gmail API through the service account for GKE over an app password or gog; app password meanwhile, pending a super admin's grant | vulcan, otp, gmail, gke, auth |
| 2026-10-19 | [Hidden windows for the scheduled tasks](decisions/2026-10-19_hidden-task-windows.md) | conhost --headless over pythonw, S4U or VBScript; Last Run Result always reads 0 | scheduler, windows, task-scheduler |

## Investigations

| Date | Document | Summary | Tags |
|---|---|---|---|
| 2026-11-04 | [The AI slop scanner misses long placeholders](investigations/2026-11-04_slop-scanner-long-placeholders.md) | Open items over about 210 characters went uncounted, so Ready could read early; fixed 4 Nov by sweeping with the repo's own patterns | drafting, slop-check, placeholders |

## Analysis

| Date | Document | Summary | Tags |
|---|---|---|---|
| 2026-11-18 | [Where the Top 10 comes from, and calls on two portals](analysis/2026-11-18_portal-mix-and-duplicates.md) | SAM.gov holds 439 of 735 calls, hence its share of the Top 10; no call has been on two portals since 24 Oct | portal-mix, top-10, duplicates, sam-gov, front-door |
| 2026-11-06 | [The fit score against the judges' verdicts](analysis/2026-11-06_fit-score-against-judges.md) | The score rates categories: 35 of 44 strong calls had no yes, so the Top 10 ranks verdicts first | fit-score, ranking, judges, top-10 |

## Benchmarks

| Date | Document | Summary | Tags |
|---|---|---|---|

## Explorations

| Date | Document | Summary | Tags |
|---|---|---|---|
| 2026-11-10 | [Putting a call no scanner found through the pursuit flow](explorations/2026-11-10_manual-call-to-pursuit.md) | upsert_call under its own run, kept and reviewed, then Pursue on the dashboard; solicitation files to 00_solicitation, facts as workspace material | pursuits, drafting, dsip, manual-call, worker |
