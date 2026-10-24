# Space Florida

What the scanner knows about Space Florida, the state of Florida's aerospace finance and
development authority (PRO-546). The assistant reads this file when people ask about the portal.

## What it is

Space Florida runs the Cape Canaveral Spaceport's state facilities (the Shuttle Landing Facility,
the Space Life Sciences Lab and others) and buys services, studies and facility work through
RFPs, RFQs, RFBs, RFIs and ITNs. It posts a few a year on https://www.spaceflorida.gov/solicitations.
On 24 Oct 2026 the one active listing was RFP-SF-02-0-2026, the Space Based Data Pilot Program,
due 7 Oct 2026, with a Notice of Intent to Award already posted, so no call was stored.

## How it is read

- One request a run for the solicitations page; robots.txt allows everything. No browser and no
  login.
- The page is a Webflow site: an Active RFPs list, then Awarded RFPs, then a mobile copy of both.
  The scanner reads the first Active RFPs list up to the Awarded RFPs heading. Each item gives
  its title, links to its documents (the RFP, addenda, notices), optional notes, and its
  published and due dates.
- A page without the Active RFPs heading fails the run and the pipeline alerts. An empty list
  means no active RFPs.

## Fields

- `id` is `spacefl-` and the title in lower case with dashes; a renamed RFP gets a new id. `url`
  is the solicitations page, which lists the documents.
- `type` is RFP, RFQ, RFB, RFI, ITN or Solicitation, from the title. `department` is Space Florida.
- `posted_date` and `due_date` are the page's published and due dates, without a time.
- `description` says what the listing is, its dates and notes, then the names of its documents.
- `extra`: `spacefl_documents` (the documents' names, the page field the assistant lists),
  `spacefl_document_links` (name and link of each), `spacefl_notes`,
  `spacefl_intent_to_award` (a Notice of Intent to Award or to Enter Into Negotiations is among
  the documents), `spacefl_no_deadline` (the page shows no due date) and `spacefl_closed` (past
  the due date in Eastern time, or an intent to award posted). A closed RFP is stored only if an
  earlier run stored it.

## How to respond

As the RFP document says: it names the procurement contact, the questions deadline and how to
deliver the proposal by its due date.
