# Velocity's company knowledge and BD history

Where they live and how to use them when drafting, refining or assessing a proposal. The Writer's worker applies
the same rules in code (drafting/facts.py; docs/RUNBOOK.md, Company facts). This page is for any session doing
the work by hand.

## Sources of truth

Everything is on the Google shared drive "Velocity Business Development", in the BD Proposal Library folder
(`1aOlJdDaPR0GuClaw2o0Ft1se-BzJKZ2_`). Read each file live by its id, every time. Never rely on a cached copy:
not `data\drafting\facts\` (the worker's stand-in for when Drive is down), not an export saved earlier, not what
a past session remembered.

| File | Ids inside | Drive file id |
|---|---|---|
| 00 Company Facts (Doc) | F-01 to F-52 | `1f0ivJ89UuiykGbCXJ29GF6-koY2WwRP6iAitNZZx1lY` |
| 01 Past Performance Register (Sheet) | PP-xx | `1N-Bm6U17uDvuoRHVCpDgF-Fk6OeRzcILDKpZTn6u3Dc` |
| 02 Products & Capabilities (Sheet) | PR-xx | `1eNmOkacZ_yUADYJ5vbSggVNfXldSKwXGAdgFqgiv4mQ` |
| 03 People (Sheet) | PE-xx | `1Z7VXVxcKuPZaLtM3mMvKDenFM_HeZsVMZSx4jZa3VLc` |
| 05 Conflicts & Open Questions (Sheet) | CF-xx | `1kCJndsjKU_8okfwgJjL48unsatlRVJh6JbnPBnEzZns` |
| Brand Guide (Doc, in 04 Brand) | | `14ddy8Hf98v-ksyqGfGMbi-R8abzl61NkNkzAtCnTnH8` |
| 00 Proposal Register (Sheet, BD history) | submission_id | `1lKzb-4ytrit9QbYcIay-zNb84Q1vbGwyolSM4_0ijE0` |

BD history is the 00 Proposal Register: one row per proposal, white paper, RFI, pitch, exercise or commercial job,
with its dates, values and outcome (every column is in docs/LIBRARY_CONVENTIONS.md). Each row's submission_id,
`YYYY-MM-DD_portal_short-title` (or `nodate_portal_short-title` when the date is not known), names its folder in
`Submissions/`, which holds 00_solicitation, 01_submitted, 02_working and 03_outcome.

## Using them in a draft

- **Only these files:** company facts, past performance, products and people come only from them. If a fact is
  not there, write `[NEEDS FACT: what is missing]`. Never invent one.
- **Conflicts first:** before using a fact, check 05 Conflicts. A fact tied to a CF item that is not resolved is
  flagged in the draft rather than stated as settled: `[NEEDS FACT: settle CF-nn, ...]`. An item "confirmed by
  David, evidence pending" may be used, and is listed for review.
- **Related past bids:** search the Register for the same agency, topic or product. Read their 01_submitted and
  03_outcome files to reuse the language that won and to avoid repeating the weaknesses that cost a loss. The
  Writer's Outline and First draft do this themselves for the three nearest bids that have files
  (docs/RUNBOOK.md, Past bids in drafts).
- **Active projects:** the PP rows whose period of performance is still running, plus Register rows marked won,
  or submitted and still waiting (outcome pending or shortlisted; the Register has no separate status column).
- **People:** only current staff. Leave out anyone 03 People marks FORMER EMPLOYEE, in bios and key personnel. A
  partner is named as a partner.
- **Entity:** Velocity Explorations, Inc. by default (UEI and CAGE in F-02 and F-03). Use the sister company
  Hoverslam Designs LLC only when told to, and confirm its SAM renewal first.
- **SENSITIVE items:** never use one outside its own proposal. Inside it, use one only when the solicitation
  requires it, and flag it for review.
- **Style:** names, spelling and voice follow the Brand Guide.
- **Facts used:** end every draft with a "Facts used" list citing the F, PP, PR and PE ids it rests on. The
  Writer's worker saves the same list beside each draft instead (facts_used_v1.md and so on), so the draft itself
  stays ready to submit.

## Access

Sessions read these files through the claude.ai Google Drive, Docs and Sheets connectors. They belong to the
Claude account rather than this repo (`claude mcp list` shows them; the repo has no `.mcp.json`). If a
connector's session has expired, reconnect it with `/mcp` or in claude.ai's connector settings, and say what is
needed rather than reading the files another way. The Writer's worker reads them through its service account
(docs/RUNBOOK.md, Google Drive and Sheets).
