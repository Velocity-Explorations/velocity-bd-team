# BD Proposal Library: conventions

The Proposal Library holds every proposal, white paper, RFI response and pitch Velocity Explorations has submitted, with its outcome. The BD tools will learn from it: drafting will quote strong past submissions, the dashboard will show win rates, and the slop check will be tuned on proposals people wrote before AI drafting tools. The same text is kept in two places: this folder's `00 README` on Drive and docs/LIBRARY_CONVENTIONS.md in the velocity-bd-team repo.

## Layout

- `00 README`: this document.
- `00 Proposal Register`: one row per submission (below).
- `01 Company Reference/`: what every proposal draws on: capabilities, past performance, bios, boilerplate, win themes.
- `Submissions/<submission_id>/`: one folder per submission, named `YYYY-MM-DD_portal_short-title`, for example `2026-03-17_vulcan-sof_vigilant-eagle-27`. The date is the day it was submitted. When that date is not known, the name starts with `nodate` instead: `nodate_portal_short-title`, for example `nodate_sofwerx_field-sensor`. Each holds four folders:
  - `00_solicitation/`: what we responded to: the call, RFP, BAA or topic, and its attachments.
  - `01_submitted/`: exactly what went in.
  - `02_working/`: drafts and working files. The drafting pipeline writes here.
  - `03_outcome/`: the award letter or rejection, the debrief, evaluator comments.

Portal slugs: vulcan-sof, ssc-front-door, sam-gov, nstxl, diu, afwerx, iarpa, space-force, doe-sbir, bidnet-co, bidnet-fl, dsip, apfit, xtech, antx, tencap, sofwerx, sparx, nasa-sbir, dhs-sbir, piee, tacfi, other.

## Naming files in 01_submitted/

Name each file for the volume it is, not its version: `technical-volume.pdf`, `cost-volume.xlsx`, `cover-letter.pdf`, `quad-chart.pptx`, `white-paper.pdf`. The folder already says which submission it is, and only the final version belongs here.

## The Register

One row per submission folder. Each row starts with submission_id, submitted_date, portal and drive_link filled in from the folder; people fill in the rest. Dropdowns hold the allowed values. Leave the header row as it is: the sync finds each column by its name and stops if one is missing.

| Column | What it holds |
|---|---|
| submission_id | The folder name. Never change it once synced. |
| title | The submission's title. |
| portal | Where it was submitted (portal slugs above). |
| agency | The customer: agency, command or office. |
| solicitation_id | The government's number for the call, RFP, BAA or topic. |
| type | sbir_1, sbir_2, sbir_3, sttr, rfi, white_paper, baa, pitch, rfp, ota, exercise, commercial or other. |
| role | prime, sub or team member; prime (Hoverslam) when Velocity's sister company Hoverslam was the submitting prime. |
| partners | Teaming partners, comma separated. |
| submitted_date | When it went in (YYYY-MM-DD). Blank when not known (a `nodate_` submission). |
| due_date | The deadline it answered (YYYY-MM-DD). |
| requested_value | What we asked for, in dollars. |
| outcome | won, lost, no_award, pending, withdrawn, shortlisted or not_submitted (prepared but never sent in). |
| outcome_date | When we heard (YYYY-MM-DD). |
| award_value | What was awarded, in dollars. |
| strength_rating | 1 to 5: how strong the submission was, whatever the outcome. |
| strength_reason | One line on why that rating. |
| why_won_or_lost | What the debrief or our best judgment says. |
| use_as_exemplar | yes when drafting may quote it. |
| themes | Topics, comma separated, for example C2, edge AI, legacy modernization. |
| drive_link | The submission's folder. |

## The three columns that matter most

- **outcome**: no record of wins and losses existed before this Register. Without it, nothing can learn what wins.
- **strength_rating**: a loss can be a strong proposal and a win a weak one. The rating says how good the work was, apart from the result.
- **use_as_exemplar**: drafting will quote only rows marked yes. Mark a submission yes only if you would be glad to see its passages reused.

## Keeping the database in step

After filling in or changing rows, or adding a Submissions folder, ask Claude to "sync the register". It adds a starter row for any new folder, checks every row, writes the valid ones to the database, and reports any row it skipped and why (usually a typo in a dropdown value), and any row whose folder is missing. In the repo the sync is `python -m library.register sync` (library/register.py).
