# Where the Top 10 comes from, and calls on two portals

18 Nov 2026. Evidence for Task 6 of the 9 Nov review (#193): Shaun saw the Top 10 picking mostly from SAM.gov, and the
task asked for calls found on several portals to list every source. Read-only queries on the live ledger (calls,
briefs, runs) and the scan logs in data/logs.

## Calls per portal

SAM.gov 439, DSIP 105, NASA Forecast 94, Vulcan SOF 63, NSTXL 16, SSC Front Door 10, AFWERX 4, DIU 2, SpaceWERX 1,
DOE SBIR 1: 735 in all. APFIT and Space Florida hold none; their newest scans found nothing open.

## The Top 10 by portal, per Monday brief

| Week of | Portals |
|---|---|
| 19 Oct | Vulcan SOF 10 (before SAM.gov was scanned) |
| 26 Oct | Vulcan SOF 7, NSTXL 1, NASA Forecast 1, SSC Front Door 1 |
| 2 Nov | SAM.gov 9, Vulcan SOF 1 |
| 9 Nov | SAM.gov 8, Vulcan SOF 2 |
| 16 Nov | SAM.gov 5, DSIP 5 |

SAM.gov leads because it lists the most calls (60% of the ledger), not because other portals feed it. DSIP's topics,
read since 16 Nov, took half of the newest Top 10.

## Calls on two portals

The only key two portals share is an SSC Front Door repost of a SAM.gov notice (`sscfd_sam_notice_id`); whichever
adapter sees it first stores it and the other skips it. Every scan logged since 24 Oct counts 0 both ways (Front Door's
"already on SAM.gov", SAM.gov's "on Front Door"), and none of Front Door's 10 calls carries a SAM.gov notice id. Nothing
has needed merging, so source merging waits until a call turns up on two portals (David, 18 Nov 2026).
