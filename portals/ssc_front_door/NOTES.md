# SSC Front Door: portal notes

What the assistant should know about this portal. Facts only; update them when the portal
changes.

## What it is

Space Systems Command's industry intake site, renamed "USSF Front Door" in Sep 2025 (the
address still says SSCFrontDoor): https://sscfrontdoor.experience.crmforce.mil/SSCFrontDoor/s/.
Companies share ideas or ask questions through two forms, and staff route them to mission
owners. It funds and awards nothing itself.

## Signing in

There is no login. Everything the scanner reads is public, so this portal needs no credential.
Being "registered" on Front Door means a company has shared an idea, product or service, which
puts it in the Front Door catalog and on the Orbital Watch mailing list.

## The listings

- The Events calendar is the list the scanner reads: 214 listings on 2026-10-20, published since
  Aug 2023, about 7 new a month in 2026, and 10 still open on 2026-10-21.
- Most listings are events: conferences, industry days and Zoom webinars. The rest are SpaceWERX
  and AFWERX challenges and SBIR announcements, standing documents, and SSC notices reposted from
  SAM.gov (RFIs, sources sought, CSOs), about one a month.
- Listings have no notice type, NAICS code, set-aside, solicitation number, office or contacts.
  The scanner reads the type from the title, and for SAM.gov reposts without one in the title,
  from the description.
- Listings that ended before the scanner first saw them are never stored. A stored listing is
  marked closed (extra.sscfd_closed) once its end date passes.

## Reading a listing

- Every listing has a start and an end date in its own time zone. due_date is the end date
  in that zone, for example "11 SEP 2026 : 15:00 PDT".
- On reposted SAM.gov notices the dates have no fixed meaning: the end date is sometimes the
  response deadline and sometimes the date SAM.gov marks the notice inactive. When
  extra.sscfd_sam_notice_id is set, SAM.gov's own dates and full text win
  (extra.sscfd_sam_url). Front Door posts these the same day as SAM.gov or up to seven weeks later.
- Descriptions of reposted notices are short summaries; the full text and attachments are only
  on SAM.gov.
- SpaceWERX runs an event series named "Velocity", for example "Velocity: Advancing Space Force
  Capabilities in Cislunar Space". It has nothing to do with Velocity Explorations.
- The JCO and OTTI organization pages list standing capability needs with no dates. The scanner
  does not read them.

## Submitting

Front Door takes no bids. For an event, register through its own link
(extra.sscfd_registration or extra.sscfd_event_url). For a reposted notice, respond on SAM.gov.
To pitch an idea or product to SSC, use the site's "Share an Idea, Product, or Service" form.

## Running the scanner

- Two plain web requests per scan, no browser: the home page (for the site framework's current
  id, which changes at each Salesforce release) and the Events list.
- If the list call fails, the scanner reads the id again and retries once, then the run fails
  and alerts.
- The address answers any visitor; robots.txt allows it and no bot protection was seen on
  2026-10-20. SSC's own www.ssc.spaceforce.mil pages refuse automated clients, so the scanner
  stores links to them and never opens them.
