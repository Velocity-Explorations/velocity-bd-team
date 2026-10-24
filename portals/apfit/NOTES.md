# APFIT

What the scanner knows about APFIT, Accelerate the Procurement and Fielding of Innovative
Technologies (PRO-547). The assistant reads this file when people ask about the portal.

## What it is

The Office of the Under Secretary of War for Research and Engineering, OUSW(R&E), awards $10M to
$50M to projects with small business or nontraditional performers to speed initial production,
through a competitive down-select each year. There are two cycles a year. Proposals must come
from government sponsors through an approved service APFIT representative, and each
participating organization sets its own deadlines: a company takes part through a program office
that champions its technology, not by applying itself.

The APFIT page (https://ac.cto.mil/apfit/) posts one status per cycle. On 24 Oct 2026: FY27-1 "is
in final selection" (posted 20 Oct 2026) and FY26-2 "Awards have been announced", so no cycle was
open and nothing was stored.

## How it is read

- One request a run for the APFIT page; robots.txt allows it. The site's WordPress REST API
  answers 401 to the public, so the page's post grid is read instead. No browser and no login.
- Each post in the grid gives its number, schema.org publish and modify dates, a title linking to
  the post and a one-line status.
- A page without the post grid fails the run and the pipeline alerts. An empty grid means no
  cycle posts.
- Every post names APFIT, so the keyword filter keeps them all and the judges rate each.

## Fields

- `id` is `apfit-` and the cycle, for example `apfit-fy27-2`; a post without a cycle in its title
  is `apfit-post-<number>`. `url` is the post. `title` is "APFIT FY27-2 cycle".
- `type` is APFIT cycle; `department` is OUSW(R&E). `posted_date` is the post's publish date;
  `due_date` is empty, since each organization sets its own deadline.
- `description` explains APFIT and how a company takes part, then the cycle's status as of the
  post's last change.
- `extra`: `apfit_cycle` (FY27-2), `apfit_post_id`, `apfit_status` (the post's words),
  `apfit_no_deadline` (always true) and `apfit_closed` (the status says final selection,
  evaluation, closed or awarded). A closed cycle is stored only if an earlier run stored it.

## How to respond

Through a government sponsor: find a program office that will champion the technology for
production, and it submits through its service's APFIT representative by its own deadline.
