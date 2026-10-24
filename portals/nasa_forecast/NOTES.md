# NASA Forecast

What the scanner knows about NASA's acquisition forecast (PRO-545). The assistant reads this file
when people ask about the portal.

## What it is

NASA publishes the buys it plans as one spreadsheet, viewable at
https://www.hq.nasa.gov/office/procurement/forecast/NAF.html: one row per planned acquisition,
by center (MSFC, GSFC, KSC and so on), with its NAICS code, the quarter NASA expects to release
the solicitation and to award, the estimated value, set-aside, contract type, contacts and a
description. On 24 Oct 2026 it held 136 rows: 95 neither awarded nor withdrawn, 34 of them under
Velocity's NAICS codes (31 under 541715).

A forecast row is a heads-up, often months before the solicitation: the time to reach the
technical contact or the center's small business specialist, and to watch SAM.gov for the
solicitation.

## How it is read

- One download a run of
  https://www.hq.nasa.gov/office/procurement/forecast/AcqForecastNew.xlsx (about 83 KB). NASA's
  server has no robots.txt (it answers 403, which the robots standard reads as no rules). No
  browser and no login.
- The spreadsheet is read with Python's standard library (an .xlsx file is a zip of XML parts),
  by the header row's column names, so a moved column does not break it. The download and each
  part are limited to 20 MB before parsing.
- A download that is not a spreadsheet, or whose header lacks SourceID or TitleOfRequirement,
  fails the run and the pipeline alerts.
- The keyword filter keeps rows under Velocity's five NAICS codes and rows naming software, AI,
  machine learning, autonomy, cyber, data analytics or information technology; the codes are in
  `keywords.yaml`, so they can be changed from the dashboard.

## Fields

- `id` is `nasa-<SourceID>`; `url` is the forecast page (rows have no page of their own).
- `type` is Forecast; `department` is NASA and the buying office, for example "NASA MSFC";
  `naics_code` and `set_aside` are the row's.
- `posted_date` and `due_date` are empty: a forecast has neither.
- `description` is a summary sentence (office, expected solicitation and award quarters, new or
  re-compete, value, contract type, competition, NAICS), then the row's Summary and Description.
- `extra`: `nasa_source_id`, `nasa_status` (AcquisitionStatus: New, Revised, Awarded, Withdrawn),
  `nasa_phase` (AcquisitionPhase), `nasa_solicitation_expected` and `nasa_award_expected` (for
  example "Q3 FY2026", NASA's fiscal years), `nasa_estimated_value`, `nasa_requirement`
  (Services, Research & Development and so on), `nasa_contacts` (the technical contact and small
  business specialist), `nasa_no_deadline` (always true) and `nasa_closed` (awarded, withdrawn or
  cancelled). A closed row is stored only if an earlier run stored it.

## How to respond

Nothing to submit yet. Reach the row's technical contact or the center's small business
specialist, and watch SAM.gov for the solicitation in the quarter NASA expects to release it.
