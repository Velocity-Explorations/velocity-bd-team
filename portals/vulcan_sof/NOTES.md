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

- Engagement Objectives: one or more of OTA Prototype, Tech Experimentation, Capability
  Demonstration, CRADA, Market Research, FAR Acquisition, SBIR / STTR, Prize Challenge. The
  first is stored as the call's type; all of them in extra.vulcan_objectives.
- Open Date and Deadline are shown in Mountain time, MDT or MST, often 21:59 local.
- Documents, Files Required for Submission and Tags are lists on the page, stored in extra.
  Only some calls list required files; the Additional Instructions usually say what to send.
- The Problem Statement or Bottom Line Upfront is the description.

## Submitting

Responses go in as a Vulcan Scout Card: create a new card or submit an existing one from the
call's page, attaching what the call asks for, often a white paper, quad chart or proposal.
Some calls instead ask for documents by email; the instructions say so.

## Running the scraper

- A full scan reads every call page and takes about three minutes.
- Pages are an Angular app: never wait for "networkidle". A few pages render one to two
  seconds late; the scraper waits for them.
