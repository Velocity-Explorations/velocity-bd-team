"""AFWERX: the SBIR and STTR cycles listed on its Get Funded page (PRO-536).

The page reader is shared with SpaceWERX (portals/shared/funding_list.py), and its own tests are
in test_shared_funding_list.py; the made-up page is in funding_pages.py.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ledger import queries as lq
from portals import registry
from portals.afwerx import portal
from portals.shared import funding_list as fl
from tests.funding_pages import AFWERX_PAGE, FakeSite

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
FIRST_ID = "afwerx-dow-sbir-specific-topic-27-bz-27-bx-release-1"
SECOND_ID = "afwerx-dow-sttr-specific-topic-27-tz-release-1"
CLOSED_ID = "afwerx-dod-sbir-specific-topic-26-bz-release-2"
STRATFI_ID = "afwerx-stratfi-tacfi-27-1"


def built(now: datetime = NOW) -> list[dict[str, Any]]:
    return [fl.build_record(listing, now, portal.SITE) for listing in fl.solicitations(AFWERX_PAGE)]


def fetch(now: datetime = NOW, limit: int | None = None) -> dict[str, int]:
    run_id = lq.start_run("AFWERX", component="afwerx")
    return fl.fetch_all(run_id, portal.SITE, limit=limit, now=now, opener=FakeSite(AFWERX_PAGE))


# ------------------------------------------------------------------------------ records

def test_a_cycle_becomes_a_calls_row() -> None:
    assert built()[0] == {
        "id": FIRST_ID,
        "portal": "AFWERX",
        "title": "DOW SBIR SPECIFIC TOPIC 27.BZ & 27.BX Release 1",
        "type": "SBIR cycle",
        "department": "Department of the Air Force",
        "naics_code": "",
        "set_aside": "",
        "posted_date": "2026-10-07",
        "due_date": "2026-11-25",
        "description": ("An SBIR solicitation cycle listed on AFWERX's Get Funded page, with U.S. Air Force topics. "
                        "Pre-release 7 Oct 2026, opens 28 Oct 2026, closes 25 Nov 2026. "
                        "AFWERX lists solicitations, not their topics. The topics are on DSIP, the Defense "
                        "Department's portal for these solicitations, which the scanner does not read. The "
                        "call's link opens DSIP's topic search."),
        "url": "https://www.dodsbirsttr.mil/topics-app/",
        "source_type": "scrape",
        "extra": {"afwerx_branches": ["Air Force"], "afwerx_pre_release": "2026-10-07",
                  "afwerx_open": "2026-10-28", "afwerx_no_deadline": False, "afwerx_closed": False},
    }


def test_types_dates_and_the_closed_flag() -> None:
    sbir, sttr, closed, stratfi = built()
    assert [r["id"] for r in (sbir, sttr, closed, stratfi)] == [FIRST_ID, SECOND_ID, CLOSED_ID, STRATFI_ID]
    assert [r["type"] for r in (sbir, sttr, closed, stratfi)] == ["SBIR cycle", "STTR cycle", "SBIR cycle", "STRATFI/TACFI"]
    assert sttr["description"].startswith("An STTR solicitation cycle listed on AFWERX's Get Funded page, "
                                          "with U.S. Air Force and Space Force topics. ")
    assert (closed["posted_date"], closed["due_date"]) == ("2026-04-13", "2026-05-13")   # no pre-release: the open date
    assert "Pre-release N/A, opens 13 Apr 2026, closes 13 May 2026." in closed["description"]
    assert closed["extra"]["afwerx_closed"] is True and closed["extra"]["afwerx_pre_release"] is None
    assert (stratfi["posted_date"], stratfi["due_date"]) == ("", "")
    assert stratfi["description"] == (
        "A STRATFI/TACFI solicitation listed on AFWERX's Get Funded page, with U.S. Air Force and Space Force "
        "topics. Pre-release TBD, opens TBD, closes TBD. STRATFI and TACFI are only for companies with a current "
        "or recent Phase II award, and not twice for the same technology. The call's link opens DSIP's topic search.")
    assert stratfi["extra"]["afwerx_no_deadline"] is True and stratfi["extra"]["afwerx_closed"] is False


# ------------------------------------------------------------------------------ a run

def test_fetch_all_stores_the_open_cycles(ledger_db: str) -> None:
    counts = fetch()
    assert {row["id"] for row in lq.calls_where(portal="AFWERX")} == {FIRST_ID, SECOND_ID, STRATFI_ID}
    assert counts == {"found": 4, "scraped": 3, "new": 3, "failed": 0}


def test_a_stored_cycle_that_closes_is_refreshed_as_closed(ledger_db: str) -> None:
    fetch()
    counts = fetch(now=datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc))
    assert counts == {"found": 4, "scraped": 3, "new": 0, "failed": 0}
    assert json.loads(lq.get_call(FIRST_ID)["extra"])["afwerx_closed"] is True   # type: ignore[index]


def test_fetch_all_honours_the_limit(ledger_db: str) -> None:
    counts = fetch(limit=1)
    assert counts["scraped"] == 1 and len(lq.calls_where(portal="AFWERX")) == 1


def test_the_keyword_filter_keeps_the_sbir_and_sttr_cycles(ledger_db: str) -> None:
    fetch()
    kept, rejected = registry.get("afwerx").filter(lq.calls_where(portal="AFWERX"))
    assert {d.id for d in kept} == {FIRST_ID, SECOND_ID}
    assert [(d.id, d.reason) for d in rejected] == [(STRATFI_ID, "no keyword match")]


def test_the_registry_finds_afwerx() -> None:
    found = registry.get("afwerx")
    assert found.name == "AFWERX" and not found.needs_browser and found.fetch_timeout == 120
    assert found.keywords and found.keywords.exists() and found.notes and found.notes.exists()
    assert "DSIP" in found.how_to_submit
