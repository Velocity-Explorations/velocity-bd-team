"""DIU: the open solicitations carried in the page's embedded Nuxt state (PRO-534).

The page below is made up but shaped like DIU's: window.__NUXT__ is a function whose
parameters stand for repeated values, with one assignment before it returns the state.
"""
from __future__ import annotations

import json
import urllib.error
from datetime import datetime, timezone
from typing import Any

import pytest

from ledger import queries as lq
from portals import registry
from portals.diu import api, records, scrape

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)

PAYLOAD = (
    r'window.__NUXT__=(function(a,b,c,d,e,f){d.fields={title:"Open Solicitations",count:2};'
    r'return {layout:"default",data:[{}],fetch:{},error:null,state:{page:d,shared:d,latest:[],aois:['
    r'{number:"PROJ00683",sys_id:"a0Pcr1",u_project_type:b,'
    r'u_aoi_title:"Improved Mobile Electric Power Distribution System",'
    r'u_aoi_close_date_string:"2026-10-28 23:59:59 US/Eastern Time",u_aoi_close_date:"2026-10-28",'
    r'u_area_of_interest:"<p>DIU seeks a \"plug and play\" power distribution system.</p>'
    r'<p>Prototypes within 12 months.</p>",'
    r'u_eligibility_requirements:"<p>U.S. companies only.</p>",'
    r'u_intended_contracting_shop:c,u_posted:e,show_scores:f,description:a,portfolio_id:"a0Lt1"},'
    r'{number:"PROJ00721",sys_id:"a0Pcr2",u_project_type:"2374a Prize Challenge",'
    r'u_aoi_title:"Suitable Warfighting Adaptive Payloads (SWAP)-USV Sprint 2",'
    r'u_aoi_close_date_string:"2026-11-30 23:59:59 US/Eastern Time",u_aoi_close_date:"2026-11-30",'
    r'u_area_of_interest:"<p>Payloads for uncrewed surface vessels.</p>",'
    r'u_eligibility_requirements:a,u_intended_contracting_shop:a,u_posted:true,show_scores:false,description:a},'
    r'{number:"PROJ00650",sys_id:"a0Pcr3",u_project_type:"4022 OT - CLASS ACT",'
    r'u_aoi_title:"Counter Uncrewed Systems, Maritime",'
    r'u_aoi_close_date_string:"2026-10-20 23:59:59 US/Eastern Time",u_aoi_close_date:"2026-10-20",'
    r'u_area_of_interest:"<p>Cleared entities that counter uncrewed systems at sea.</p>",'
    r'u_eligibility_requirements:"<p>Top secret facility clearance required.</p>",'
    r'u_intended_contracting_shop:c,u_posted:true,show_scores:!1,description:a,count:-3.5e1}'
    r']},serverRendered:true}}("","2371b OT - CSO","Army Contracting Command",{},true,!1));'
)
PAGE = f'<html><head><title>Open Solicitations</title></head><body><div id="__nuxt"></div><script>{PAYLOAD}</script></body></html>'


class Reply:
    def __init__(self, body: str) -> None:
        self.body = body.encode("utf-8")

    def __enter__(self) -> "Reply":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def read(self) -> bytes:
        return self.body


class FakeDiu:
    def __init__(self, page: str = PAGE, failures: int = 0) -> None:
        self.page = page
        self.failures = failures
        self.requests: list[str] = []

    def __call__(self, request: Any, timeout: float) -> Reply:
        assert timeout >= 10
        self.requests.append(request.full_url)
        if len(self.requests) <= self.failures:
            raise urllib.error.URLError("timed out")
        return Reply(self.page)


def solicitations() -> list[dict[str, Any]]:
    return api.open_solicitations(PAGE)


# ------------------------------------------------------------------------------ the page

def test_the_state_is_read_without_running_the_pages_code() -> None:
    state = api.nuxt_state(PAGE)
    assert state["page"]["fields"] == {"title": "Open Solicitations", "count": 2}   # set before return
    assert state["page"] is state["shared"]                                          # one object, two references
    first, second, third = state["aois"]
    assert first["u_project_type"] == "2371b OT - CSO" and first["u_intended_contracting_shop"] == "Army Contracting Command"
    assert first["u_posted"] is True and first["show_scores"] is False and second["show_scores"] is False
    assert first["description"] == "" and third["count"] == -35.0
    assert first["u_aoi_close_date_string"] == "2026-10-28 23:59:59 US/Eastern Time"
    assert '"plug and play"' in first["u_area_of_interest"] and first["u_area_of_interest"].startswith("<p>")


def test_a_page_without_the_state_or_the_list_is_an_error() -> None:
    with pytest.raises(api.DiuError, match="state"):
        api.open_solicitations("<html><body>Maintenance</body></html>")
    without_list = PAGE.replace("aois:[", "other:[")
    with pytest.raises(api.DiuError, match="solicitation list"):
        api.open_solicitations(without_list)


def test_the_page_is_fetched_with_one_retry() -> None:
    site = FakeDiu(failures=1)
    assert "window.__NUXT__" in api.fetch_page(site)
    assert site.requests == [api.SOLICITATIONS_URL] * 2
    with pytest.raises(api.DiuError, match="did not answer"):
        api.fetch_page(FakeDiu(failures=2))


# ------------------------------------------------------------------------------ records

def test_a_solicitation_becomes_a_calls_row() -> None:
    rec = records.build_record(solicitations()[0], NOW)
    assert (rec["id"], rec["portal"], rec["type"], rec["department"]) == (
        "diu-PROJ00683", "DIU", "CSO", "Defense Innovation Unit")
    assert rec["url"] == "https://www.diu.mil/work-with-us/submit-solution/PROJ00683"
    assert rec["due_date"] == "2026-10-28T23:59:59-04:00" and rec["posted_date"] == ""
    assert rec["description"] == ('DIU seeks a "plug and play" power distribution system.\nPrototypes within 12 months.'
                                  "\n\nEligibility: U.S. companies only.")
    assert rec["extra"] == {"diu_number": "PROJ00683", "diu_project_type": "2371b OT - CSO",
                            "diu_contracting_shop": "Army Contracting Command",
                            "diu_close": "2026-10-28 23:59:59 US/Eastern Time", "diu_closed": False}


def test_types_close_times_and_the_closed_flag() -> None:
    built = [records.build_record(s, NOW) for s in solicitations()]
    assert [r["type"] for r in built] == ["CSO", "Challenge", "Bridge program"]
    assert built[1]["due_date"] == "2026-11-30T23:59:59-05:00"   # after the clocks change
    assert built[1]["description"] == "Payloads for uncrewed surface vessels."   # no eligibility text
    assert built[1]["extra"]["diu_contracting_shop"] is None
    assert built[2]["extra"]["diu_closed"] is True and "Top secret facility clearance" in built[2]["description"]


# ------------------------------------------------------------------------------ a run

def test_fetch_all_stores_the_open_solicitations(ledger_db: str) -> None:
    counts = scrape.fetch_all(lq.start_run("DIU", component="diu"), now=NOW, opener=FakeDiu())
    assert {row["id"] for row in lq.calls_where(portal="DIU")} == {"diu-PROJ00683", "diu-PROJ00721"}
    assert counts == {"found": 3, "scraped": 2, "new": 2, "failed": 0}


def test_a_stored_solicitation_that_closes_is_refreshed_as_closed(ledger_db: str) -> None:
    scrape.fetch_all(lq.start_run("DIU", component="diu"), now=NOW, opener=FakeDiu())
    later = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
    counts = scrape.fetch_all(lq.start_run("DIU", component="diu"), now=later, opener=FakeDiu())
    assert counts == {"found": 3, "scraped": 2, "new": 0, "failed": 0}
    assert json.loads(lq.get_call("diu-PROJ00683")["extra"])["diu_closed"] is True   # type: ignore[index]


def test_fetch_all_honours_the_limit(ledger_db: str) -> None:
    counts = scrape.fetch_all(lq.start_run("DIU", component="diu"), limit=1, now=NOW, opener=FakeDiu())
    assert counts["scraped"] == 1 and len(lq.calls_where(portal="DIU")) == 1


def test_the_registry_finds_diu() -> None:
    found = registry.get("diu")
    assert found.name == "DIU" and not found.needs_browser and found.fetch_timeout == 120
    assert found.keywords and found.keywords.exists() and found.notes and found.notes.exists()
    assert "diu.mil" in found.how_to_submit
