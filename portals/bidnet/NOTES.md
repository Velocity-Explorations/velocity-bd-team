# BidNet Direct

What the scanner knows about BidNet Direct, a site where state and local governments post bids
(PRO-544). The assistant reads this file when people ask about the portal.

## Status: shelved, not merged

On 24 Oct 2026, after letting about seven requests through, BidNet's AWS bot protection began
answering the scanner with an empty HTTP 202 challenge, for curl and Python alike. Only a browser
that runs its script gets past it, and getting around a site's block is something this project
does not do (IARPA was handled the same way, through SAM.gov). The adapter below is finished and
tested on its branch, kept unmerged, and can be merged if BidNet ever lets the scanner in or
offers a feed.

## What it is

BidNet Direct's open-bid lists for Colorado and Florida, the two states the old Yukon scanner
watched. On 24 Oct 2026 Colorado posted about 25 bids a day (about 400 open) and Florida a few a
day (about 75 open). Most are construction, facilities and services; the keyword filter and the
judges look for the software, IT and data ones.

## How it is read

- Each state's list is public: https://www.bidnetdirect.com/colorado/solicitations/open-bids
  and the same for florida, 25 bids a page, newest first, paged as `/open-bids/page2` and so on.
  No browser and no login.
- BidNet's robots.txt lets general crawlers read the lists, asks for 5 seconds between requests
  and forbids query-string paging (`?page=`). It blocks AI companies' crawlers by name (OpenAI's,
  Anthropic's and others). The scanner is neither: it names itself as velocity-bd-team, waits 5
  seconds before every request and pages by path. David chose to read BidNet on those terms on
  24 Oct 2026; the judges see each kept bid's title.
- Each run reads the bids published in the last 8 days, so a weekly scan sees each bid once and
  the first run posts no backlog: about 9 pages, under a minute.
- A bid's own page shows its location, dates and closing time; the issuing agency, solicitation
  number, description, documents and contact are for registered members with a paid vendor
  package. The scanner does not read them.
- A list whose first page has no bids it can read fails the run, and the pipeline alerts.

## Fields

- `id` is `bidnet-<state>-<bid number>`, for example `bidnet-colorado-0000441390`; `url` is the
  bid's page on BidNet.
- `type` is RFP, RFQ, RFI, Invitation to bid, Sole source or Solicitation, from the title.
- `department` is "Colorado state and local agencies" or "Florida state and local agencies".
- `posted_date` and `due_date` are the list's published and closing dates, without a time.
- `description` is one generic sentence: the state, the two dates, and that the details are for
  members. The keyword filter therefore matches on the title.
- `extra`: `bidnet_state`, `bidnet_bid_id`, `bidnet_closing` (the list's wording),
  `bidnet_no_deadline` (the list shows no closing date) and `bidnet_closed` (the closing date has
  passed in the state's time).

## How to respond

The issuing agency, documents and response instructions are for registered BidNet members. Once
the agency is known, its own procurement page usually carries them too.
