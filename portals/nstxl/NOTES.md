# NSTXL

What the scanner knows about NSTXL (PRO-530). The assistant reads this file when people ask
about the portal.

## What it is

NSTXL runs OTA consortia: S2MARTS (with NSWC Crane), SpEC (Space Enterprise Consortium, with
Space Systems Command), JDEC (Joint Directed Energy Consortium), Microelectronics Commons and
TReX. Their opportunities are DoD prototype projects. Members submit through each opportunity's
page; Velocity is a member.

## How it is read

- The site's public WordPress REST API (`/wp-json/wp/v2`): the `opp_status` and `ota` term
  lists, then every `opportunity` post, about three pages of 100. No browser and no login;
  robots.txt allows everything.
- Ids are `nstxl-<post id>` and stay the same when a page is edited.
- About a third of the open opportunities, mostly SpEC projects, are member-only pages: their
  public text is only NSTXL's "member only page" notice. They are stored with their title and
  the description "Member-only page on NSTXL: sign in as a member to read it", and
  `extra.nstxl_members_only`. Reading them needs a member sign-in (PRO-531).

## What counts as open

- A status named Current or Coming Soon, for example "SpEC - Current" or "S2MARTS - Coming Soon".
- Dropped: a post that also carries an Under Eval, Awarded, Archived or Closed status; a post
  whose newest updates say canceled, awarded, now closed or no longer available; a post not
  updated in a year; NSTXL's "access test" page. Statuses lag, so these checks matter.
- A post whose deadline has passed is closed. A closed post is stored only if an earlier run
  stored it; then it is refreshed, so it shows as closed.

## Fields

- `type`, the first that fits: Industry day, White paper, RFI (RFIs and requests for network
  insight), Call for projects, Coming soon, Solicitation (RFS, RPP, solution papers), else OTA
  opportunity.
- `department` is the consortium.
- `due_date` is `YYYY-MM-DD`: the first date in the text introduced by a deadline word (due,
  deadline, by, extends to), skipping "posted" dates; the text lists updates newest first. A
  date without a year takes the first year on or after the post's date. The sentence it came
  from is in `extra.nstxl_deadline_text`.
- A post whose public text gives no deadline has `extra.nstxl_no_deadline` true, and the scan
  quality alert does not count it as badly read: coming-soon notices have none yet, member-only
  text cannot be read, and many posts keep the deadline in the attached RPP or RFS. Open the
  post's Key Documents for those.
- `extra` also holds `nstxl_post_id`, `nstxl_consortium`, `nstxl_statuses`, `nstxl_modified`
  and `nstxl_closed`.
