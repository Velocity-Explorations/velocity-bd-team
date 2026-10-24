"""BidNet Direct: Colorado's and Florida's open bids, read from the public lists (PRO-544).

The pages below are made up but shaped like BidNet's: a table row per bid with its link, state,
published date and closing date, newest first, paged as /open-bids/page2 and so on.
"""
from __future__ import annotations

import json
import urllib.error
from datetime import date, datetime, timezone
from typing import Any

import pytest

from ledger import queries as lq
from portals import registry
from portals.bidnet import api, records, scrape

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
CUTOFF = date(2026, 10, 16)   # 8 days before 24 Oct
BASE = "https://www.bidnetdirect.com"
GROUPS = {"Colorado": "8409951", "Florida": "8408751"}


def row(index: int, state: str, bid_id: str, title: str, published: str, closing: str | None) -> str:
    closing_span = ('<span class="sol-closing-date open"><span class="date-label"><span class="accessibility-hidden">'
                    f'Clock</span>Closing</span> <span class="date-value">{closing}</span></span>') if closing else ""
    return (f'<tr\n\t\tdata-index="{index}" class="mets-table-row odd"><td class="mainCol"><div class="sol-info-container">'
            f'<div class="sol-info-col"><div class="sol-title"><a id="g_{index}" href="/{state.lower()}/solicitations/'
            f'open-bids/Bid/{bid_id}?purchasingGroupId={GROUPS[state]}&origin=1" class="solicitation-link '
            f'mets-command-link">{title}</a><script type="text/javascript" src="data:text/javascript;base64,AAAA" '
            f'defer="defer"></script></div><div class="sol-region"><span class="sol-region-item">{state}</span></div>'
            '</div><span class="dates-col"><span class="dates-col-content"><span class="sol-publication-date">'
            '<span class="date-label"><svg viewBox="0 0 20 22"><title>Calendar</title></svg><span '
            f'class="accessibility-hidden">Calendar</span>Published</span> <span class="date-value">{published}</span>'
            f'</span>{closing_span}</span></span></div></td></tr>')


def page(*rows: str) -> str:
    return ('<html><body><table class="mets-table"><thead><tr><th>Solicitations</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table></body></html>")


CO_1 = page(row(0, "Colorado", "0000441384", "RFQ#FY26-017 37th Street Widening Phase 4 Design", "10/23/2026", "11/27/2026"),
            row(1, "Colorado", "0000441390", "RFP 2026-118 Computer Aided Dispatch Software Replacement", "10/23/2026", "11/20/2026"),
            row(2, "Colorado", "0000441300", "Janitorial Maintenance Services", "10/22/2026", "11/05/2026"))
CO_2 = page(row(0, "Colorado", "0000441200", "Cybersecurity Assessment &amp; Penetration Testing", "10/20/2026", "11/10/2026"),
            row(1, "Colorado", "0000441100", "HVAC Repair at Fire Station 3", "10/16/2026", "10/30/2026"),
            row(2, "Colorado", "0000441000", "Data Center Generator Replacement", "10/14/2026", "11/01/2026"))
CO_3 = page(row(0, "Colorado", "0000440900", "Network Cabling Upgrade", "10/13/2026", "11/02/2026"))
FL_1 = page(row(0, "Florida", "0000500001", "ITB 26-14 Body-Worn Camera Program", "10/23/2026", "11/19/2026"),
            row(1, "Florida", "0000500002", "Request for Information: AI Chatbot for Resident Services", "10/19/2026", None),
            row(2, "Florida", "0000499000", "Fuel Supplier Services", "10/09/2026", "10/31/2026"))
PAGES = {
    f"{BASE}/colorado/solicitations/open-bids": CO_1,
    f"{BASE}/colorado/solicitations/open-bids/page2": CO_2,
    f"{BASE}/colorado/solicitations/open-bids/page3": CO_3,
    f"{BASE}/florida/solicitations/open-bids": FL_1,
}
IN_WINDOW = {"bidnet-colorado-0000441384", "bidnet-colorado-0000441390", "bidnet-colorado-0000441300",
             "bidnet-colorado-0000441200", "bidnet-colorado-0000441100", "bidnet-florida-0000500001",
             "bidnet-florida-0000500002"}


class Reply:
    def __init__(self, body: str, status: int = 200) -> None:
        self.body = body.encode("utf-8")
        self.status = status

    def __enter__(self) -> "Reply":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def read(self) -> bytes:
        return self.body


class FakeBidNet:
    def __init__(self, pages: dict[str, str] | None = None, failures: int = 0) -> None:
        self.pages = pages if pages is not None else PAGES
        self.failures = failures
        self.requests: list[str] = []

    def __call__(self, request: Any, timeout: float) -> Reply:
        assert timeout >= 10 and "velocity-bd-team" in request.get_header("User-agent")
        self.requests.append(request.full_url)
        if len(self.requests) <= self.failures:
            raise urllib.error.URLError("timed out")
        return Reply(self.pages.get(request.full_url, page()))


class Naps:
    def __init__(self) -> None:
        self.taken: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.taken.append(seconds)


def throttle() -> api.Throttle:
    return api.Throttle(sleep=Naps())


# ------------------------------------------------------------------------------ the lists

def test_a_list_page_gives_each_bid() -> None:
    assert api.parse_page(CO_2)[0] == {
        "bid_id": "0000441200", "title": "Cybersecurity Assessment & Penetration Testing", "state": "Colorado",
        "link": f"{BASE}/colorado/solicitations/open-bids/Bid/0000441200?purchasingGroupId=8409951&origin=1",
        "published": "10/20/2026", "closing": "11/10/2026"}
    assert api.parse_page(FL_1)[1]["closing"] == ""
    assert len(api.parse_page(CO_1)) == 3   # the header row is not a bid


def test_a_state_is_read_newest_first_until_its_bids_are_older_than_the_window() -> None:
    site = FakeBidNet()
    bids = api.fetch_state("colorado", CUTOFF, site, throttle())
    assert [b["bid_id"] for b in bids] == ["0000441384", "0000441390", "0000441300", "0000441200", "0000441100"]
    assert site.requests == [f"{BASE}/colorado/solicitations/open-bids", f"{BASE}/colorado/solicitations/open-bids/page2"]
    assert not any("?" in url for url in site.requests)   # robots.txt forbids query-string paging


def test_requests_wait_five_seconds_between_them() -> None:
    site, gate = FakeBidNet(), throttle()
    for state in api.STATES:
        api.fetch_state(state, CUTOFF, site, gate)
    assert len(site.requests) == 3 and gate.sleep.taken == [5, 5]   # type: ignore[attr-defined]


def test_a_first_page_without_bids_is_an_error_and_an_empty_later_page_ends_the_state() -> None:
    with pytest.raises(api.BidNetError, match="no bids"):
        api.fetch_state("florida", CUTOFF, FakeBidNet({}), throttle())
    long_window = date(2026, 1, 1)
    bids = api.fetch_state("colorado", long_window, FakeBidNet(), throttle())
    assert len(bids) == 7   # pages 1 to 3; page 4 has no bids


def test_a_bot_challenge_is_reported_as_one() -> None:
    # On 24 Oct 2026 BidNet's AWS bot protection began answering the scanner with an empty 202.
    def challenged(request: Any, timeout: float) -> Reply:
        return Reply("", status=202)

    with pytest.raises(api.BidNetError, match="bot protection"):
        api.fetch_state("colorado", CUTOFF, challenged, throttle())


def test_a_page_is_fetched_with_one_retry() -> None:
    assert len(api.fetch_state("florida", CUTOFF, FakeBidNet(failures=1), throttle())) == 2
    with pytest.raises(api.BidNetError, match="did not answer"):
        api.fetch_state("florida", CUTOFF, FakeBidNet(failures=2), throttle())


# ------------------------------------------------------------------------------ records

def listing(state: str, number: int) -> dict[str, Any]:
    pages = {"colorado": (CO_1, CO_2), "florida": (FL_1,)}[state]
    return [bid for p in pages for bid in api.parse_page(p)][number]


def test_a_bid_becomes_a_calls_row() -> None:
    assert records.build_record(listing("colorado", 1), NOW) == {
        "id": "bidnet-colorado-0000441390",
        "portal": "BidNet Direct",
        "title": "RFP 2026-118 Computer Aided Dispatch Software Replacement",
        "type": "RFP",
        "department": "Colorado state and local agencies",
        "naics_code": "",
        "set_aside": "",
        "posted_date": "2026-10-23",
        "due_date": "2026-11-20",
        "description": ("A Colorado state or local government solicitation listed on BidNet Direct. Published 23 Oct "
                        "2026, closes 20 Nov 2026. Its issuing agency, description and documents are for registered "
                        "BidNet members only."),
        "url": f"{BASE}/colorado/solicitations/open-bids/Bid/0000441390?purchasingGroupId=8409951&origin=1",
        "source_type": "scrape",
        "extra": {"bidnet_state": "Colorado", "bidnet_bid_id": "0000441390", "bidnet_closing": "11/20/2026",
                  "bidnet_no_deadline": False, "bidnet_closed": False},
    }


def test_types_from_the_title() -> None:
    titles = ("RFP 2026-118 Computer Aided Dispatch Software Replacement", "RFQ#FY26-017 37th Street Widening",
              "ITB 26-14 Body-Worn Camera Program", "IFB 2026-3 Asphalt", "Invitation to Bid: Road Salt",
              "Request for Proposals for Fleet Telematics", "Request for Information: AI Chatbot",
              "Sole Source Notice: Radio Maintenance", "Janitorial Maintenance Services")
    assert [records.derive_type(t) for t in titles] == [
        "RFP", "RFQ", "Invitation to bid", "Invitation to bid", "Invitation to bid", "RFP", "RFI", "Sole source",
        "Solicitation"]


def test_a_bid_without_a_closing_date_and_the_closed_flag_in_the_states_time() -> None:
    open_ended = records.build_record(listing("florida", 1), NOW)
    assert (open_ended["due_date"], open_ended["type"], open_ended["department"]) == ("", "RFI", "Florida state and local agencies")
    assert "Published 19 Oct 2026, with no closing date shown." in open_ended["description"]
    assert open_ended["extra"]["bidnet_no_deadline"] is True and open_ended["extra"]["bidnet_closing"] is None
    bid = listing("colorado", 1)   # closes 20 Nov
    late_that_day = datetime(2026, 11, 21, 6, 0, tzinfo=timezone.utc)    # 23:00 in Denver
    next_day = datetime(2026, 11, 21, 8, 0, tzinfo=timezone.utc)         # 01:00 in Denver
    assert records.build_record(bid, late_that_day)["extra"]["bidnet_closed"] is False
    assert records.build_record(bid, next_day)["extra"]["bidnet_closed"] is True


# ------------------------------------------------------------------------------ a run

def test_fetch_all_stores_the_last_eight_days_of_bids_from_both_states(ledger_db: str) -> None:
    naps = Naps()
    counts = scrape.fetch_all(lq.start_run("BidNet Direct", component="bidnet"), now=NOW, opener=FakeBidNet(), sleep=naps)
    assert {row["id"] for row in lq.calls_where(portal="BidNet Direct")} == IN_WINDOW
    assert counts == {"found": 7, "scraped": 7, "new": 7, "failed": 0} and naps.taken == [5, 5]


def test_fetch_all_honours_the_limit(ledger_db: str) -> None:
    counts = scrape.fetch_all(lq.start_run("BidNet Direct", component="bidnet"), limit=2, now=NOW,
                              opener=FakeBidNet(), sleep=Naps())
    assert counts["scraped"] == 2 and len(lq.calls_where(portal="BidNet Direct")) == 2


def test_the_keyword_filter_keeps_software_and_it_bids(ledger_db: str) -> None:
    scrape.fetch_all(lq.start_run("BidNet Direct", component="bidnet"), now=NOW, opener=FakeBidNet(), sleep=Naps())
    kept, rejected = registry.get("bidnet").filter(lq.calls_where(portal="BidNet Direct"))
    assert {d.id for d in kept} == {"bidnet-colorado-0000441390", "bidnet-colorado-0000441200", "bidnet-florida-0000500002"}
    reasons = {d.id: d.reason for d in rejected}
    assert reasons["bidnet-colorado-0000441300"] == "no keyword match"   # "maintenance" is not "ai"
    assert reasons["bidnet-colorado-0000441100"].startswith("blocklist")
    stored = json.loads(lq.get_call("bidnet-florida-0000500002")["extra"])   # type: ignore[index]
    assert stored["bidnet_no_deadline"] is True


def test_the_registry_finds_bidnet() -> None:
    found = registry.get("bidnet")
    assert found.name == "BidNet Direct" and not found.needs_browser and found.fetch_timeout == 300
    assert found.keywords and found.keywords.exists() and found.notes and found.notes.exists()
    assert "registered" in found.how_to_submit
