# AFWERX

What the scanner knows about AFWERX, the Department of the Air Force's innovation arm and its
SBIR/STTR program office (PRO-536). The assistant reads this file when people ask about the portal.

## What it is

AFWERX's Get Funded page (https://afwerx.com/get-funded/) lists, under "Open Funding
Opportunities", each DoD SBIR or STTR solicitation cycle that includes U.S. Air Force or Space
Force topics, with its pre-release, open and close dates. Two were listed on 23 Oct 2026, both
open 28 Oct to 25 Nov 2026: DoW SBIR Specific Topic 27.BZ & 27.BX Release 1 and DoW STTR
Specific Topic 27.TZ Release 1. Expect a few cycles a year.

The topics themselves are on DSIP, the DoD SBIR/STTR Innovation Portal (dodsbirsttr.mil), whose
robots.txt forbids automated access. The scanner does not read DSIP: each cycle becomes one call,
and its link opens DSIP's topic search (https://www.dodsbirsttr.mil/topics-app/) for a person to
read the topics.

## How it is read

- One request a run for the Get Funded page; robots.txt allows it. No browser and no login.
- The page lists each cycle twice: a grid row (badges, title, three unlabelled dates) and a
  labelled block for small screens ("SOLICITATION : ...", "PRE-RELEASE : ...", "OPEN : ...",
  "CLOSE : ..."). The scanner reads the labelled blocks and the badges above each one: AF means
  the cycle includes Air Force topics, SF Space Force topics.
- A page without the "Open Funding Opportunities" heading, or with badges in the list but no
  labelled block, fails the run and the pipeline alerts. An empty list means no cycles.
- The keyword filter keeps a cycle when its title says SBIR or STTR; the judges then rate it like
  any call. A listing of another kind (STRATFI or TACFI, for example) is dropped unless a broad
  keyword is added for it.

## Fields

- `id` is `afwerx-` and the cycle's title in lower case with dashes, for example
  `afwerx-dow-sbir-specific-topic-27-bz-27-bx-release-1`. A renamed cycle gets a new id.
- `type` is SBIR cycle, STTR cycle, SBIR/STTR cycle or Solicitation, from the title.
- `posted_date` is the pre-release date (the open date when there is none) and `due_date` the
  close date, both as dates without a time, since AFWERX gives none. A cycle counts as closed
  from the day after its close date, in Eastern time.
- `description` says what the cycle is, which services' topics it includes, its dates, and that
  the topics are on DSIP.
- `url` is DSIP's topic search, linked for people and never fetched.
- `extra`: `afwerx_branches` (Air Force, Space Force or both), `afwerx_pre_release` and
  `afwerx_open` (ISO dates, or null when AFWERX writes TBD or N/A), `afwerx_no_deadline` (AFWERX
  writes TBD or N/A for the close date) and `afwerx_closed`.
- A cycle whose close date has passed is stored only if an earlier run stored it; then it is
  refreshed, so it shows as closed.

## How to respond

Through DSIP while the cycle is open: find a topic in DSIP's topic search, read the cycle's
instructions (https://www.dodsbirsttr.mil/submissions/solicitation-documents/active-solicitations)
and submit a proposal to that topic. Submitting needs a DSIP account.
