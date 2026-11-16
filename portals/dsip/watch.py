"""After each DSIP scan: the open DoD cycles with no topics in the ledger, each as an alert for run.py to send.

    messages = missed_releases(run_id)

A cycle is an AFWERX or SpaceWERX SBIR or STTR listing whose title names a release ("27.BZ & 27.BX Release 1"). Once it
is released (its pre-release date, or its open date, has come) and until it closes, it should have topics: a DSIP call
from SBIR.gov or from a dropped DOCX whose topic number names one of its solicitations and its release. When none does,
SBIR.gov has missed the release (as it missed all 23 topics of Release 1 on 16 Nov 2026), and a person has to bring the
topics in from DSIP.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ledger.queries import calls_on
from portals.dsip.cycles import stored_cycles
from portals.dsip.inbox import SHOWN
from portals.dsip.records import EASTERN, PORTAL, shown
from portals.dsip.topics import key_of_call


def missed_releases(run_id: int, now: datetime | None = None) -> list[str]:
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(EASTERN).date()
    have = {key for call in calls_on([PORTAL]) if (key := key_of_call(call["id"], call["extra"])) is not None}
    messages: list[str] = []
    for cycle in stored_cycles():
        released = cycle.pre_release or cycle.open
        if cycle.closed or released is None or released > today or (cycle.close is not None and cycle.close < today):
            continue
        if cycle.keys & have:
            continue
        closes = f", closes {shown(cycle.close)}" if cycle.close else ""
        messages.append(
            f"velocity-bd-team: no DSIP topics for {cycle.portal}'s {cycle.title} (released {shown(released)}{closes}): "
            f"SBIR.gov, where the scan reads them, does not list them. DSIP bars automated reading, so a person downloads "
            f"each topic there (Download Topic Details as DOCX) into {SHOWN}; the next scan, or run.py --portal dsip, "
            f"makes them calls."
        )
    return messages
