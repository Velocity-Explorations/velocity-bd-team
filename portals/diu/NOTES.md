# DIU

What the scanner knows about DIU, the Defense Innovation Unit (PRO-534). The assistant reads
this file when people ask about the portal.

## What it is

DIU posts three kinds of solicitation on its open-solicitations page:
- Commercial Solutions Openings (CSOs) under 10 U.S.C. 2371b other transaction authority:
  `type` CSO.
- Prize challenges and commercial acceleration opportunities: `type` Challenge.
- CLASS ACT "bridge" solicitations, open only to entities with a top secret facility
  clearance: `type` Bridge program.

A handful are open at a time (2 on 23 Oct 2026), and each stays open a few weeks.

## How it is read

- One request for https://www.diu.mil/work-with-us/open-solicitations; robots.txt allows it.
  No browser and no login.
- The page draws its list in the browser from a private API, so its HTML has no solicitation
  headings (the old Yukon scanner relied on them). The server writes the same list into the
  page's embedded Nuxt state, `window.__NUXT__`: a JavaScript function whose parameters stand
  for repeated values. `api.nuxt_state()` reads that literal syntax and never runs any of it;
  the list is `state.aois`.
- If the page stops carrying the state or the list, the run fails and the pipeline alerts.

## Fields

- `id` is `diu-<PROJ number>`; `url` is the solicitation's own page on diu.mil, linked for
  people and never fetched (robots.txt asks crawlers to stay off submission pages).
- `due_date` is the close time as ISO 8601 with its Eastern offset, for example
  `2026-10-28T23:59:59-04:00`. DIU gives no posted date.
- `description` is the area of interest (the solicitation text), then "Eligibility:" and the
  eligibility requirements, cut to 4,000 characters.
- `extra`: `diu_number`, `diu_project_type` (DIU's own, for example "2371b OT - CSO"),
  `diu_contracting_shop`, `diu_close` (DIU's wording of the close time) and `diu_closed`.
- A solicitation whose close time has passed is stored only if an earlier run stored it; then
  it is refreshed, so it shows as closed.

## How to respond

Through the solicitation's page on diu.mil before its close time. A CSO response starts with a
short solution brief; DIU invites the strongest to pitch, then to propose.
