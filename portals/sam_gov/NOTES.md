# SAM.gov

What the scanner knows about SAM.gov (PRO-525). The assistant reads this file when people ask
about the portal.

## How it is read

- The public Get Opportunities API (v2) at api.sam.gov, with one key, `BD_SAM_API_KEY`, from
  David's SAM.gov account. No browser and no login.
- One search per NAICS code in `search.yaml`, for open notices: a response deadline today or
  later, posted in the last year. Notices without a response deadline are not returned.
- Every request counts against the key's daily limit, and each notice's description is a
  request of its own. SAM.gov's published limits: 1,000 requests a day for an account with a
  role in an entity registration or a non-federal system account, 10 for an account with no
  role. A run spends at most 900 and stops cleanly when SAM.gov answers 429; the notices it
  could not read are read on the next run.
- Requests go over IPv4 only. api.sam.gov also publishes an IPv6 address that hangs from the
  scan PC: a request took over a minute that way, and about a second over IPv4.
- Personal SAM.gov keys expire every 90 days. A run that fails with HTTP 401 or 403 needs a new
  key from the SAM.gov account profile, put in `.env`.

## What is kept

- Types: solicitations, combined synopses, presolicitations, sources sought and special
  notices. Award notices, justifications, surplus sales and intent-to-bundle notices are dropped.
- Set-asides: none (full and open), total or partial small business, and WOSB. Velocity is a
  WOSB small business; 8(a), HUBZone, SDVOSB, VOSB and the rest are dropped.
- A title on the blocklist in `keywords.yaml` is dropped before its description is read.
- The keyword filter and the review then run as for every portal.

## Fields

- `id` is `samgov-<noticeId>`; `url` is the notice on sam.gov.
- `type`: Solicitation (also combined synopses), Presolicitation, Sources sought, Special notice.
- `department` is the agency path, for example "DEPT OF DEFENSE / DEPT OF THE ARMY / AMC".
- `due_date` is SAM.gov's response deadline as it gives it, ISO 8601 with its UTC offset.
- `description` is the notice text, cut to 4,000 characters. Attachments are not downloaded;
  their links are in `extra.samgov_attachments`.
- `extra` keys start with `samgov_`: notice id, solicitation number, SAM.gov's own type and
  set-aside code, classification (PSC) code, NAICS codes, place of performance, contacts,
  attachments, additional info link, and `samgov_closed` (deadline passed or no longer active).

## Front Door reposts

SSC Front Door reposts some SAM.gov notices (`extra.sscfd_sam_notice_id`). Whichever copy
reaches the ledger first stays: SAM.gov skips a notice Front Door already carries, and Front
Door skips a repost of a notice already stored here, so nobody decides the same notice twice.

## How to respond

Each notice says how: usually by email to the contracting officer it names, sometimes through a
system such as PIEE. Velocity's UEI and CAGE code are in drafting/company.yaml.
