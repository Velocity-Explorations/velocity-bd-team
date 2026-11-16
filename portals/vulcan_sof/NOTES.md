# Vulcan SOF: portal notes

What the assistant should know about this portal. Facts only; update them when the portal
changes.

## What it is

USSOCOM's industry engagement site. Commands and labs post "calls": problem statements,
RFIs, prototype opportunities, experimentation events and prize challenges. Posters seen so
far include NIWC Atlantic, NSWC, DONRCO, USTRANSCOM, SOUTHCOM, USINDOPACOM and NORAD and
USNORTHCOM, not only SOF units.

## Signing in

- Email and password, then a six-digit code emailed from notifications@vulcan-sof.com with
  the subject "Vulcan - OTP Code". The scraper reads the code from the mailbox itself.
- The site remembers this machine for a while, so a fresh login often skips the code.
- Saved cookies live in data/vulcan_sof/cookies.json and are reused first on every run.

## The calls listing

- One listing holds every call, open and closed. On 2026-10-16 it held 60: 18 open, 42 closed.
- Each call card carries two links to the same call; the scraper keeps one.
- A call's page says "This call has closed." once submissions stop. That is stored as
  extra.vulcan_closed; a closed call can still show a future deadline.

## Reading a call

- Since Vulcan redesigned its call pages (found 16 Nov 2026), each call is read from the call
  feed its page loads (/apiv1/call/get, through the logged-in session; portals/vulcan_sof/records.py),
  not from the page text, which no longer shows the deadline's time. Call links are now
  /login/ng2/call/<uuid>; the uuid is the one the old collectionUuid links carried, so ids hold.
- Engagement Objectives: one or more of OTA Prototype, Tech Experimentation, Capability
  Demonstration, CRADA, Market Research, FAR Acquisition, SBIR / STTR, Prize Challenge (the feed
  spells one code FAR_AQUISITION). The feed lists them alphabetically, so a call keeps the type
  it has while that is still one of them; a new call takes the most binding (FAR, OTA, SBIR,
  prize, CRADA, demonstration, experimentation, market research). All of them go in
  extra.vulcan_objectives.
- Open Date and Deadline are stored in Mountain time, as the old pages showed them (often 21:59 local).
- Documents, required files (the feed's custom requirements) and Tags are stored in extra as lists.
  Only some calls list required files; the instructions usually say what to send.
- The feed's description, the Problem Statement, is the description.

## Submitting

Responses go in as a Vulcan Scout Card: create a new card or submit an existing one from the
call's page, attaching what the call asks for, often a white paper, quad chart or proposal.
Some calls instead ask for documents by email; the instructions say so.

## Running the scraper

- A full scan reads every call's feed and takes about a minute.
- Pages are an Angular app: never wait for "networkidle". A few pages render one to two
  seconds late; the scraper waits for them.
