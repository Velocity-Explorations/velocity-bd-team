"""Space Florida: the active RFPs on its solicitations page (PRO-546).

The page below is made up but shaped like Space Florida's Webflow page: an Active RFPs list
whose items carry a title, document links (with empty hidden slots), notes, and the published
and due dates; then Awarded RFPs; then a mobile copy of both lists.
"""
from __future__ import annotations

import json
import urllib.error
from datetime import datetime, timezone
from typing import Any

import pytest

from ledger import queries as lq
from portals import registry
from portals.space_florida import api, records, scrape

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
CDN = "https://cdn.prod.website-files.com/site/"
HIDDEN_SLOT = ('<a aria-label="Additional notes for active Space Florida RFPs" href="#" class="link-block-20 '
               'w-inline-block w-condition-invisible"><div class="paragraph _16-px regular w-dyn-bind-empty"></div></a>')


def item(title: str, docs: list[str], published: str, due: str, notes: str = "", mobile: bool = False) -> str:
    links = "".join(f'<a aria-label="Additional notes for active Space Florida RFPs" href="{CDN}{name.replace(" ", "%20")}.pdf" '
                    f'target="_blank" class="link-block-22 w-inline-block">\n<div class="paragraph _16-px regular">{name}</div></a>'
                    for name in docs)
    rich = (f'<div class="rfps-rich-text w-richtext"><p>{notes}</p></div>' if notes
            else '<div class="rfps-rich-text w-condition-invisible w-dyn-bind-empty w-richtext"></div>')
    label = '<div class="resources-title _25"><h3 class="h3-title-small">Published</h3></div>' if mobile else ""
    return (f'<div role="listitem" class="w-dyn-item"><div class="rfps-wrapper{" mobile" if mobile else ""}">'
            f'<div id="w-node-a" class="proposal-title"><div><div class="paragraph _16-px regular">{title}</div></div></div>'
            f'<div id="w-node-b" class="additional-materials-rfps"><div class="div-block-15">{links}{HIDDEN_SLOT * 3}{rich}'
            f'</div></div><div class="published-rfps">{label}<div class="paragraph link _75">{published}</div></div>'
            f'<div class="due-rfps"><div class="paragraph link _75">{due}</div></div></div></div>')


def listing(items: str) -> str:
    return f'<div class="overflow-x"><div class="rfps-div"><div class="w-dyn-list"><div role="list" class="w-dyn-items">{items}</div></div></div></div>'


OPEN = ("RFP-SF-03-0-2026 Spaceport Data Integration Platform",
        ["RFP-SF-03-0-2026 Spaceport Data Integration Platform", "RFP-SF-03-0-2026 Addendum 01"],
        "October 20, 2026", "November 18, 2026", "Pre-proposal meeting on November 2, 2026 at 10 AM.")
AWARDING = ("RFP-SF-02-0-2026 Space Based Data Pilot Program",
            ["RFP-SF-02-0-2026 Space Based Data Pilot Program", "RFP-SF-02-0-2026 Notice of Intent to Award"],
            "September 21, 2026", "October 7, 2026")
RFQ = ("Request for Qualifications For Launch Complex Engineering Services", ["RFQ 03-0-2026 Request for Qualifications"],
       "October 22, 2026", "December 1, 2026")
BOILER = ("RFB 01-0-2025 SLSL Boiler Replacement", ["RFB 01-0-2025 Addendum 01"], "January 29, 2025", "Thermal Tech, Inc.")


def page(active: list[tuple[Any, ...]], awarded: list[tuple[Any, ...]] = [BOILER]) -> str:
    desktop = "".join(item(*a) for a in active)
    mobile = "".join(item(*a, mobile=True) if len(a) == 5 else item(*a, "", True) for a in active)
    return ('<html><head><script>var label = "Active RFPs";</script></head><body><h1>Space Florida Solicitations</h1>'
            '<p class="paragraph center">The Space Florida Procurement Department is responsible for the management '
            'of the acquisition of all materials and services.</p><h2 class="display-8">Active RFPs</h2>'
            '<div class="w-layout-grid rfps-grid"><div class="resources-title"><h3 class="h3-title-small">Proposal Title'
            '</h3></div><div class="resources-title"><h3 class="h3-title-small">Due By</h3></div></div>'
            + listing(desktop) + '<h2 class="display-8">Awarded RFPs</h2>' + listing("".join(item(*a) for a in awarded))
            + '<h3 id="active-rfps" class="display-8">Active RFPs</h3>' + listing(mobile)
            + '<h3 id="awarded-rfps" class="display-8">Awarded RFPs</h3></body></html>')


PAGE = page([OPEN, AWARDING, RFQ])


class Reply:
    def __init__(self, body: str) -> None:
        self.body = body.encode("utf-8")

    def __enter__(self) -> "Reply":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def read(self) -> bytes:
        return self.body


class FakeSite:
    def __init__(self, body: str = PAGE, failures: int = 0) -> None:
        self.body = body
        self.failures = failures
        self.requests: list[str] = []

    def __call__(self, request: Any, timeout: float) -> Reply:
        assert timeout >= 10 and "velocity-bd-team" in request.get_header("User-agent")
        self.requests.append(request.full_url)
        if len(self.requests) <= self.failures:
            raise urllib.error.URLError("timed out")
        return Reply(self.body)


def found() -> list[dict[str, Any]]:
    return api.solicitations(PAGE)


# ------------------------------------------------------------------------------ the page

def test_active_rfps_are_read_once_with_their_documents_and_dates() -> None:
    listings = found()
    assert [s["title"] for s in listings] == [OPEN[0], AWARDING[0], RFQ[0]]   # not the awarded list, not the mobile copy
    assert listings[0] == {
        "title": "RFP-SF-03-0-2026 Spaceport Data Integration Platform",
        "documents": [{"name": "RFP-SF-03-0-2026 Spaceport Data Integration Platform",
                       "url": f"{CDN}RFP-SF-03-0-2026%20Spaceport%20Data%20Integration%20Platform.pdf"},
                      {"name": "RFP-SF-03-0-2026 Addendum 01", "url": f"{CDN}RFP-SF-03-0-2026%20Addendum%2001.pdf"}],
        "notes": "Pre-proposal meeting on November 2, 2026 at 10 AM.",
        "published": "October 20, 2026",
        "due": "November 18, 2026",
    }
    assert listings[1]["notes"] == ""   # the hidden, empty notes block is not read


def test_an_empty_list_has_no_rfps_and_a_page_without_the_list_is_an_error() -> None:
    assert api.solicitations(page([])) == []
    with pytest.raises(api.SpaceFloridaError, match="Active RFPs"):
        api.solicitations("<html><body>Maintenance</body></html>")


def test_the_page_is_fetched_with_one_retry() -> None:
    site = FakeSite(failures=1)
    assert "Active RFPs" in api.fetch_page(site) and site.requests == [api.PAGE_URL] * 2
    with pytest.raises(api.SpaceFloridaError, match="did not answer"):
        api.fetch_page(FakeSite(failures=2))


# ------------------------------------------------------------------------------ records

def test_an_active_rfp_becomes_a_calls_row() -> None:
    assert records.build_record(found()[0], NOW) == {
        "id": "spacefl-rfp-sf-03-0-2026-spaceport-data-integration-platform",
        "portal": "Space Florida",
        "title": "RFP-SF-03-0-2026 Spaceport Data Integration Platform",
        "type": "RFP",
        "department": "Space Florida",
        "naics_code": "",
        "set_aside": "",
        "posted_date": "2026-10-20",
        "due_date": "2026-11-18",
        "description": ("A Space Florida solicitation (Florida's aerospace finance and development authority). "
                        "Published 20 Oct 2026, due 18 Nov 2026. Pre-proposal meeting on November 2, 2026 at 10 AM.\n\n"
                        "Documents: RFP-SF-03-0-2026 Spaceport Data Integration Platform; RFP-SF-03-0-2026 Addendum 01."),
        "url": "https://www.spaceflorida.gov/solicitations",
        "source_type": "scrape",
        "extra": {"spacefl_documents": ["RFP-SF-03-0-2026 Spaceport Data Integration Platform", "RFP-SF-03-0-2026 Addendum 01"],
                  "spacefl_document_links": found()[0]["documents"],
                  "spacefl_notes": "Pre-proposal meeting on November 2, 2026 at 10 AM.",
                  "spacefl_intent_to_award": False, "spacefl_no_deadline": False, "spacefl_closed": False},
    }


def test_the_assistant_lists_the_documents_by_name() -> None:
    # `<prefix>_documents` is a page field the assistant reads as a list of names (docs/LEDGER_SCHEMA.md).
    from assistant.tools import _extra_list

    extra = records.build_record(found()[0], NOW)["extra"]
    assert _extra_list(extra, "_documents") == ["RFP-SF-03-0-2026 Spaceport Data Integration Platform",
                                                "RFP-SF-03-0-2026 Addendum 01"]


def test_types_and_a_notice_of_intent_to_award_closes_an_rfp() -> None:
    titles = ("RFP-SF-03-0-2026 Spaceport Data", "Request for Qualifications For Launch Complex", "RFB 01-0-2025 SLSL Boiler",
              "RFI-01-0-2025 Request for Information For Process Water", "ITN 01-0-2026 Spaceport Concessions",
              "Spaceport Master Plan Update")
    assert [records.derive_type(t) for t in titles] == ["RFP", "RFQ", "RFB", "RFI", "ITN", "Solicitation"]
    awarding = records.build_record(found()[1], NOW)
    assert awarding["extra"]["spacefl_intent_to_award"] is True and awarding["extra"]["spacefl_closed"] is True
    rfq = records.build_record(found()[2], NOW)
    assert (rfq["type"], rfq["due_date"], rfq["extra"]["spacefl_closed"]) == ("RFQ", "2026-12-01", False)
    still_open_on_the_day = datetime(2026, 11, 19, 4, 0, tzinfo=timezone.utc)   # 18 Nov, 23:00 Eastern
    assert records.build_record(found()[0], still_open_on_the_day)["extra"]["spacefl_closed"] is False


# ------------------------------------------------------------------------------ a run

def test_fetch_all_stores_the_open_rfps(ledger_db: str) -> None:
    counts = scrape.fetch_all(lq.start_run("Space Florida", component="space_florida"), now=NOW, opener=FakeSite())
    stored = {row["id"] for row in lq.calls_where(portal="Space Florida")}
    assert stored == {"spacefl-rfp-sf-03-0-2026-spaceport-data-integration-platform",
                      "spacefl-request-for-qualifications-for-launch-complex-engineering-services"}
    assert counts == {"found": 3, "scraped": 2, "new": 2, "failed": 0}


def test_a_stored_rfp_that_closes_is_refreshed_as_closed(ledger_db: str) -> None:
    scrape.fetch_all(lq.start_run("Space Florida", component="space_florida"), now=NOW, opener=FakeSite())
    later = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    counts = scrape.fetch_all(lq.start_run("Space Florida", component="space_florida"), now=later, opener=FakeSite())
    assert counts == {"found": 3, "scraped": 2, "new": 0, "failed": 0}
    row = lq.get_call("spacefl-rfp-sf-03-0-2026-spaceport-data-integration-platform")
    assert json.loads(row["extra"])["spacefl_closed"] is True   # type: ignore[index]


def test_the_keyword_filter_keeps_the_data_rfp(ledger_db: str) -> None:
    scrape.fetch_all(lq.start_run("Space Florida", component="space_florida"), now=NOW, opener=FakeSite())
    kept, rejected = registry.get("space_florida").filter(lq.calls_where(portal="Space Florida"))
    assert [d.id for d in kept] == ["spacefl-rfp-sf-03-0-2026-spaceport-data-integration-platform"]
    assert [d.reason for d in rejected] == ["no keyword match"]


def test_the_registry_finds_space_florida() -> None:
    found_portal = registry.get("space_florida")
    assert found_portal.name == "Space Florida" and not found_portal.needs_browser and found_portal.fetch_timeout == 120
    assert found_portal.keywords and found_portal.keywords.exists() and found_portal.notes and found_portal.notes.exists()
    assert "spaceflorida.gov" in found_portal.how_to_submit
