# SpaceWERX

What the scanner knows about SpaceWERX, the U.S. Space Force's innovation arm and a division of
AFWERX (PRO-538). The assistant reads this file when people ask about the portal.

## What it is

SpaceWERX's Get Funded page (https://spacewerx.us/get-funded/) has an "Open Funding
Opportunities" list built on AFWERX's site template: SBIR and STTR cycles, and STRATFI and TACFI
notices for the Space Force. On 23 Oct 2026 it listed one: the PY26.2 TACFI Notice of
Opportunity, open since 5 Jun 2026 and taking submissions on a continuous basis.

STRATFI and TACFI (Strategic and Tactical Funding Increases) add funding to a current or recent
SBIR or STTR Phase II, and not twice for the same technology, so they only matter if Velocity
holds such an award. Each card says so. Space Force topics in DoD SBIR and STTR cycles also show
on AFWERX's list, with an SF badge.

## How it is read

- One request a run for the Get Funded page; robots.txt allows it. No browser and no login.
- portals/shared/funding_list.py reads the list for both SpaceWERX and AFWERX: the labelled
  block the page shows for each listing ("SOLICITATION : ...", "PRE-RELEASE : ...", "OPEN : ...",
  "CLOSE : ..."), and the link on its title. SpaceWERX shows no AF or SF badges.
- A page without the "Open Funding Opportunities" heading, or with dates in the list but no
  labelled block, fails the run and the pipeline alerts. An empty list means no listings.
- The keyword filter keeps a listing whose title says SBIR, STTR, STRATFI or TACFI; the judges
  then rate it like any call.

## Fields

- `id` is `spacewerx-` and the listing's title in lower case with dashes, for example
  `spacewerx-py26-2-tacfi-notice-of-opportunity`. A renamed listing gets a new id.
- `type` is SBIR cycle, STTR cycle, SBIR/STTR cycle, STRATFI, TACFI, STRATFI/TACFI or
  Solicitation, from the title. `department` is U.S. Space Force.
- `posted_date` is the pre-release date (the open date when there is none) and `due_date` the
  close date, both as dates without a time. A listing that takes submissions on a continuous
  basis, or whose close date is TBD or N/A, has no due date and `spacewerx_no_deadline` true.
- `url` is the listing's own link (for the TACFI notice, the resources on SpaceWERX's
  STRATFI/TACFI page); a link to DSIP's sign-in page becomes DSIP's topic search.
- `extra`: `spacewerx_branches`, `spacewerx_pre_release` and `spacewerx_open` (ISO dates, or
  null), `spacewerx_no_deadline` and `spacewerx_closed` (the close date has passed in Eastern
  time). A listing already closed is stored only if an earlier run stored it.

## How to respond

Follow the listing's link. SBIR and STTR cycles take proposals through DSIP while they are open.
STRATFI and TACFI notices say how on SpaceWERX's STRATFI/TACFI page
(https://spacewerx.us/accelerate/stratfi-tacfi/) and need a current or recent Phase II award.
