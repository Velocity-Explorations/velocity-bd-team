"""NSTXL: the consortia's opportunities from the site's public WordPress API (PRO-530).

The fake site below answers like nstxl.org's /wp-json/wp/v2 routes: the opp_status and ota
term lists, and the opportunity posts, page by page with X-WP-TotalPages. Every item is made up.
"""
from __future__ import annotations

import json
import urllib.parse
from datetime import date, datetime, timezone
from typing import Any

import pytest

from ledger import queries as lq
from portals import registry
from portals.nstxl import api, records, scrape

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)

STATUSES = [
    {"id": 325, "name": "SpEC - Current"}, {"id": 340, "name": "SpEC - Coming Soon"},
    {"id": 314, "name": "SPEC - Under Eval / Awarded"}, {"id": 344, "name": "S2MARTS - Current"},
    {"id": 408, "name": "S2MARTS - Under Eval / Awarded"}, {"id": 388, "name": "MEC - Current Call for Projects"},
    {"id": 445, "name": "JDEC - Coming Soon"}, {"id": 380, "name": "RFI/RNI - Archived"},
    {"id": 433, "name": "Drone Dominance"},
]
OTAS = [{"id": 222, "name": "S2MARTS"}, {"id": 223, "name": "SpEC"}, {"id": 452, "name": "JDEC"}, {"id": 224, "name": "TrEX"}]
MEMBERS_PAGE = ("<p>Oops! Looks like you have reached a member only page. If you are already an NSTXL member, "
                "login to view the page. Not a member? Apply today !</p>")


def item(post_id: int, title: str, statuses: list[int], text: str, ota: list[int] | None = None,
         posted: str = "2026-10-05T09:00:00", modified: str = "2026-10-20T10:00:00") -> dict[str, Any]:
    return {"id": post_id, "date": posted, "modified": modified, "slug": f"opp-{post_id}",
            "link": f"https://nstxl.org/opportunity/opp-{post_id}/", "title": {"rendered": title},
            "content": {"rendered": text}, "opp_status": statuses, "ota": ota or []}


PROTO = item(101, "Autonomous C2 Prototype | Project 26-30", [344], (
    "<p>RFS REVISION 1: Posted on 20 October 2026. The Government extended the solution deadline to "
    "30 October 2026 at 12:00 PM ET.</p><p>REQUEST FOR SOLUTIONS: Posted on 05 October 2026. Solutions are "
    "due 23 October 2026.</p><p>The Navy seeks autonomy software for command and control.</p>"), [222])
SOON = item(102, "Space Data Fusion | Project 26-31", [340], (
    "<p>COMING SOON NOTICE: Posted 10 October 2026. Space Systems Command is preparing to release a "
    "prototype opportunity for space data fusion.</p>"), [223])
MEMBERS = item(103, "Command and Control (C2) Capability Prototype | Project No. 26-08", [325], MEMBERS_PAGE, [223])
AWARDED = item(104, "Hypersonic Test Bed | Project 26-02", [344, 408], "<p>Solutions are due 30 October 2026.</p>", [222])
CANCELED = item(105, "Test Cabinet | Project 26-12", [445], (
    "<p>The Test Cabinet opportunity has been canceled.</p><p>Coming Soon Notice: Posted 19 August 2026.</p>"))
STALE = item(106, "Infrared Imaging Advances", [325], "<p>Responses due 30 September 2023.</p>",
             posted="2023-08-01T09:00:00", modified="2023-09-21T09:00:00")
ACCESS = item(107, "access test", [388], "")
INDUSTRY = item(108, "DE Enhancement SWaP ISV", [445], (
    "<p>OPPORTUNITY OVERVIEW: INDUSTRY DAY. Posted 08 October 2026. Date: Tuesday, October 27, 2026. "
    "Registration Deadline: Thursday, October 22, 2026.</p>"), [452])
NO_YEAR = item(109, "Ground Station Modernization | Project 26-14", [325], (
    "<p>Solution Paper Submission Deadline Extension: Posted 21 October 2026. The submission deadline "
    "for Solution Papers is now 26 October at 11:00 AM PT.</p>"), posted="2026-10-01T08:00:00", modified="2026-10-21T10:00:00")
MEC = item(110, "FY24 Microelectronics Commons Call for Projects", [388], (
    "<p>Full proposals are due by 12:00pm ET on 10 September 2026.</p>"))
DRONE = item(111, "Drone Dominance", [433], "")
ITEMS = [PROTO, SOON, MEMBERS, AWARDED, CANCELED, STALE, ACCESS, INDUSTRY, NO_YEAR, MEC, DRONE]


class Reply:
    def __init__(self, body: Any, headers: dict[str, str]) -> None:
        self.body = json.dumps(body).encode("utf-8")
        self.headers = headers

    def __enter__(self) -> "Reply":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def read(self) -> bytes:
        return self.body


class FakeNstxl:
    """Serves the term lists and the opportunity posts, paged the way WordPress pages them."""

    def __init__(self, items: list[dict[str, Any]] | None = None) -> None:
        self.items = items if items is not None else ITEMS
        self.requests: list[tuple[str, dict[str, str]]] = []

    def __call__(self, request: Any, timeout: float) -> Reply:
        assert timeout >= 10
        parts = urllib.parse.urlsplit(request.full_url)
        params = dict(urllib.parse.parse_qsl(parts.query))
        route = parts.path.rsplit("/", 1)[-1]
        self.requests.append((route, params))
        rows = {"opp_status": STATUSES, "ota": OTAS, "opportunity": self.items}[route]
        size, page = int(params["per_page"]), int(params.get("page", "1"))
        pages = max(1, -(-len(rows) // size))
        return Reply(rows[(page - 1) * size: page * size], {"X-WP-TotalPages": str(pages), "X-WP-Total": str(len(rows))})


def statuses() -> dict[int, str]:
    return {t["id"]: t["name"] for t in STATUSES}


def otas() -> dict[int, str]:
    return {t["id"]: t["name"] for t in OTAS}


# ------------------------------------------------------------------------------ the API

def test_it_reads_the_term_lists_then_every_opportunity_page_by_page(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "PER_PAGE", 4)
    site = FakeNstxl()
    assert api.fetch_terms("opp_status", site)[325] == "SpEC - Current"
    found = api.fetch_opportunities(site)
    assert [i["id"] for i in found] == [i["id"] for i in ITEMS]
    pages = [p for route, p in site.requests if route == "opportunity"]
    assert [p["page"] for p in pages] == ["1", "2", "3"]
    assert {"id", "title", "content", "opp_status", "ota", "link", "date", "modified"} <= set(pages[0]["_fields"].split(","))


# ------------------------------------------------------------------------------ records

def test_what_counts_as_open() -> None:
    reasons = {i["id"]: records.is_open(i, statuses(), NOW) for i in ITEMS}
    assert reasons[101] is None and reasons[102] is None and reasons[103] is None
    assert reasons[108] is None and reasons[109] is None and reasons[110] is None
    assert reasons[104] == "status S2MARTS - Under Eval / Awarded"
    assert reasons[105] == "text says 'has been canceled'"
    assert reasons[106] == "not updated since 2023-09-21"
    assert reasons[107] == "test page"
    assert reasons[111] == "no open status"


def test_the_deadline_is_the_newest_one_in_the_text() -> None:
    def due(entry: dict[str, Any]) -> str | None:
        found = records.deadline(records.plain_text(entry["content"]["rendered"]), date.fromisoformat(entry["date"][:10]))
        return found[0] if found else None

    assert due(PROTO) == "2026-10-30"          # the extension, not the original 23 October
    assert due(INDUSTRY) == "2026-10-22"       # the registration deadline, not the event date
    assert due(NO_YEAR) == "2026-10-26"        # no year: the next 26 October after the post
    assert due(MEC) == "2026-09-10"
    assert due(SOON) is None and due(MEMBERS) is None
    assert records.deadline("Responses are due 5 January.", date(2026, 12, 15)) == ("2027-01-05", "Responses are due 5 January.")
    assert "extended the solution deadline to 30 October 2026" in records.deadline(
        records.plain_text(PROTO["content"]["rendered"]), date(2026, 10, 5))[1]   # type: ignore[index]


def test_an_open_item_becomes_a_calls_row() -> None:
    rec = records.build_record(PROTO, statuses(), otas(), NOW)
    assert (rec["id"], rec["portal"], rec["url"], rec["posted_date"], rec["due_date"]) == (
        "nstxl-101", "NSTXL", "https://nstxl.org/opportunity/opp-101/", "2026-10-05", "2026-10-30")
    assert (rec["type"], rec["department"], rec["source_type"]) == ("Solicitation", "S2MARTS", "api")
    assert rec["description"].startswith("RFS REVISION 1: Posted on 20 October 2026.")
    extra = rec["extra"]
    assert extra["nstxl_post_id"] == 101 and extra["nstxl_consortium"] == "S2MARTS"
    assert extra["nstxl_statuses"] == ["S2MARTS - Current"] and extra["nstxl_closed"] is False
    assert "deadline to 30 October 2026" in extra["nstxl_deadline_text"]
    assert not extra.get("nstxl_no_deadline") and not extra.get("nstxl_members_only")


def test_types_and_consortia() -> None:
    built = {i["id"]: records.build_record(i, statuses(), otas(), NOW) for i in (SOON, INDUSTRY, NO_YEAR, MEC)}
    assert {k: (r["type"], r["department"]) for k, r in built.items()} == {
        102: ("Coming soon", "SpEC"), 108: ("Industry day", "JDEC"),
        109: ("Solicitation", "SpEC"),           # no OTA term: read from the status name
        110: ("Call for projects", "Microelectronics Commons")}
    assert built[102]["extra"]["nstxl_no_deadline"] is True and built[102]["due_date"] == ""
    assert built[110]["extra"]["nstxl_closed"] is True   # its deadline has passed


def test_a_post_whose_text_gives_no_deadline_says_so_and_a_white_paper_call_is_typed_as_one() -> None:
    # Many posts keep the deadline in the attached RPP; a coming-soon notice may ask for a white paper.
    draft = item(112, "New 52 | Project 26-20", [325], (
        "<p>Finalized Request for Prototype Proposals: 16 October 2026. The RPP is under Key Documents.</p>"), [223])
    rec = records.build_record(draft, statuses(), otas(), NOW)
    assert (rec["due_date"], rec["type"], rec["extra"]["nstxl_no_deadline"]) == ("", "Solicitation", True)
    paper = item(113, "GPS Ground | Project 26-18", [340], (
        "<p>OPPORTUNITY OVERVIEW: White Paper Submission Details. Posted 13 October 2026. Submit a 4-page "
        "White Paper by 30 October 2026.</p>"), [223])
    rec = records.build_record(paper, statuses(), otas(), NOW)
    assert (rec["type"], rec["due_date"], rec["extra"]["nstxl_no_deadline"]) == ("White paper", "2026-10-30", False)


def test_a_member_only_item_keeps_its_title_and_says_it_is_for_members() -> None:
    rec = records.build_record(MEMBERS, statuses(), otas(), NOW)
    assert rec["title"] == "Command and Control (C2) Capability Prototype | Project No. 26-08"
    assert rec["description"] == records.MEMBERS_NOTE and rec["due_date"] == ""
    assert rec["extra"]["nstxl_members_only"] is True and rec["extra"]["nstxl_no_deadline"] is True
    assert rec["department"] == "SpEC"


# ------------------------------------------------------------------------------ a run

def test_fetch_all_stores_the_open_items_and_skips_the_rest(ledger_db: str) -> None:
    counts = scrape.fetch_all(lq.start_run("NSTXL", component="nstxl"), now=NOW, opener=FakeNstxl())
    stored = {row["id"] for row in lq.calls_where(portal="NSTXL")}
    assert stored == {"nstxl-101", "nstxl-102", "nstxl-103", "nstxl-108", "nstxl-109"}
    assert counts == {"found": 11, "scraped": 5, "new": 5, "failed": 0}


def test_a_stored_item_that_closes_is_refreshed_as_closed(ledger_db: str) -> None:
    scrape.fetch_all(lq.start_run("NSTXL", component="nstxl"), now=NOW, opener=FakeNstxl())
    awarded = {**PROTO, "opp_status": [344, 408]}
    counts = scrape.fetch_all(lq.start_run("NSTXL", component="nstxl"), now=NOW, opener=FakeNstxl([awarded]))
    assert counts == {"found": 1, "scraped": 1, "new": 0, "failed": 0}
    assert json.loads(lq.get_call("nstxl-101")["extra"])["nstxl_closed"] is True   # type: ignore[index]


def test_fetch_all_honours_the_limit(ledger_db: str) -> None:
    counts = scrape.fetch_all(lq.start_run("NSTXL", component="nstxl"), limit=2, now=NOW, opener=FakeNstxl())
    assert counts["scraped"] == 2 and len(lq.calls_where(portal="NSTXL")) == 2


def test_the_registry_finds_nstxl() -> None:
    found = registry.get("nstxl")
    assert found.name == "NSTXL" and not found.needs_browser and found.fetch_timeout == 120
    assert found.keywords and found.keywords.exists() and found.notes and found.notes.exists()
    assert "member" in found.how_to_submit
