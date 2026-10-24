# DOE SBIR

What the scanner knows about DOE's SBIR and STTR programs (PRO-543). The assistant reads this
file when people ask about the portal.

## What it is

In 2026 DOE moved its SBIR and STTR programs from the Office of Science to the Office of
Technology Commercialization (OTC). The Office of Science page the old Yukon scanner read
(science.osti.gov/sbir/Funding-Opportunities) now says all its opportunities are closed. New
solicitations are posted on DOE's SBIR/STTR Application Hub (https://sbir-sttr.connectwerx.org/),
run for DOE by ConnectWerx with ATI, a partnership intermediary.

On 24 Oct 2026 the hub listed two solicitations, both closed: FY26 Phase I Genesis Mission (four
AI topic areas: biotechnology, quantum computing and networking, materials design, autonomous
laboratories; deadline 10 Sep 2026) and FY25 Phase II, open only to earlier DOE awardees (deadline
2 Oct 2026). OTC says a broader Phase I opportunity follows this fall. Expect a few a year.

## How it is read

- The hub is a WordPress site. Its public REST API lists every solicitation as an Avada portfolio
  item: one request a run (100 items a page). robots.txt allows it. No browser and no login.
- Each item's classes carry its category: Active, Upcoming or Closed Solicitation.
- The deadline is read from the line "Submission Deadline: September 10, 2026 at 2 PM ET", in
  Eastern time, or as a bare date from the excerpt ("Submission Deadline: 09/10/2026").
- If the API stops answering or answers in another shape, the run fails and the pipeline alerts.
- Every listing is an SBIR or STTR solicitation, and its description says so, so the keyword
  filter keeps them all and the judges rate each one. A rejected row is never filtered again, so
  an upcoming listing posted before its topics must not be dropped. A listing first seen as
  Upcoming is judged then; when it opens, its row is refreshed (deadline, text) but not judged or
  posted again.

## Fields

- `id` is `doe-<item id>`; `url` is the solicitation's page on the hub.
- `type` is SBIR/STTR Phase I, SBIR/STTR Phase II or SBIR/STTR solicitation, from the title.
  `department` is DOE Office of Technology Commercialization.
- `posted_date` is the item's publish date. `due_date` is the deadline as ISO 8601 with its
  Eastern offset, for example `2026-09-10T14:00:00-04:00`, or a bare date.
- `description` is a summary line (category and deadline), then the Information section and the
  topics, cut to 4,000 characters; the process, timeline and file table are left out.
- `extra`: `doe_post_id`, `doe_status` (Active, Upcoming or Closed), `doe_modified`,
  `doe_deadline_text` (the words the deadline was read from), `doe_no_deadline` (an upcoming
  listing without a date yet, or TBD) and `doe_closed` (the category is Closed or the deadline
  has passed). A closed solicitation is stored only if an earlier run stored it.

## How to respond

Through the hub: request an account on ATI's Acquisition Management Portal (AMP), then respond to
the open solicitation there before its deadline. A Phase I application starts with a short pitch
(four questions); DOE invites the strongest to apply in full.
