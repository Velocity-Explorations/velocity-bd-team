"""SpaceWERX: the listings on its Get Funded page, which uses AFWERX's site template (PRO-538).

The page reader is shared with AFWERX (portals/shared/funding_list.py); the made-up pages are in
funding_pages.py.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ledger import queries as lq
from portals import registry
from portals.shared import funding_list as fl
from portals.spacewerx import portal
from tests.funding_pages import SPACEWERX_PAGE, TACFI, TACFI_LINK, FakeSite, labelled, page

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
TACFI_ID = "spacewerx-py26-2-tacfi-notice-of-opportunity"


def test_the_tacfi_notice_becomes_a_calls_row() -> None:
    [listing] = fl.solicitations(SPACEWERX_PAGE)
    assert fl.build_record(listing, NOW, portal.SITE) == {
        "id": TACFI_ID,
        "portal": "SpaceWERX",
        "title": "PY26.2 TACFI Notice of Opportunity",
        "type": "TACFI",
        "department": "U.S. Space Force",
        "naics_code": "",
        "set_aside": "",
        "posted_date": "2026-06-05",
        "due_date": "",
        "description": ("A TACFI solicitation listed on SpaceWERX's Get Funded page. Pre-release N/A, opens 5 Jun "
                        "2026, takes submissions on a continuous basis. STRATFI and TACFI are only for companies "
                        "with a current or recent Phase II award, and not twice for the same technology. The "
                        "call's link opens the solicitation's own page."),
        "url": TACFI_LINK,
        "source_type": "scrape",
        "extra": {"spacewerx_branches": [], "spacewerx_pre_release": None, "spacewerx_open": "2026-06-05",
                  "spacewerx_no_deadline": True, "spacewerx_closed": False},
    }


def test_fetch_all_stores_the_listing(ledger_db: str) -> None:
    run_id = lq.start_run("SpaceWERX", component="spacewerx")
    counts = fl.fetch_all(run_id, portal.SITE, now=NOW, opener=FakeSite(SPACEWERX_PAGE))
    assert counts == {"found": 1, "scraped": 1, "new": 1, "failed": 0}
    stored = lq.get_call(TACFI_ID)
    assert stored is not None and stored["portal"] == "SpaceWERX" and stored["url"] == TACFI_LINK


def test_the_keyword_filter_keeps_sbir_sttr_stratfi_and_tacfi_listings(ledger_db: str) -> None:
    listings = (labelled(*TACFI, link=TACFI_LINK)
                + labelled([], "SPACEWERX STRATFI PY27.1", "1 Nov 26", "1 Dec 26", "15 Jan 27", link=TACFI_LINK)
                + labelled(["SF"], "DOW STTR SPECIFIC TOPIC 27.TZ Release 1", "7 Oct 26", "28 Oct 26", "25 Nov 26")
                + labelled([], "Orbital Prime Industry Day", "N/A", "1 Nov 26", "2 Nov 26", link="https://spacewerx.us/events/"))
    run_id = lq.start_run("SpaceWERX", component="spacewerx")
    fl.fetch_all(run_id, portal.SITE, now=NOW, opener=FakeSite(page(listings, site="SpaceWERX")))
    kept, rejected = registry.get("spacewerx").filter(lq.calls_where(portal="SpaceWERX"))
    assert {d.title for d in kept} == {"PY26.2 TACFI Notice of Opportunity", "SPACEWERX STRATFI PY27.1",
                                       "DOW STTR SPECIFIC TOPIC 27.TZ Release 1"}
    assert [(d.title, d.reason) for d in rejected] == [("Orbital Prime Industry Day", "no keyword match")]


def test_the_registry_finds_spacewerx() -> None:
    found = registry.get("spacewerx")
    assert found.name == "SpaceWERX" and not found.needs_browser and found.fetch_timeout == 120
    assert found.keywords and found.keywords.exists() and found.notes and found.notes.exists()
    assert "DSIP" in found.how_to_submit and "Phase II" in found.how_to_submit
