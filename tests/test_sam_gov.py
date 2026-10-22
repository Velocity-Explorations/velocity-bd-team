"""SAM.gov: the public Opportunities API, one key, read into calls (PRO-525).

The fake site below answers like api.sam.gov: a search per NAICS code, paged by record offset,
and a description link per notice that costs a request of its own. Every notice is made up.
"""
from __future__ import annotations

import io
import json
import logging
import socket
import urllib.error
import urllib.parse
from datetime import date, datetime, timezone
from typing import Any

import pytest

from ledger import queries as lq
from portals import registry
from portals.sam_gov import api, portal, records, scrape

KEY = "FAKEkey0123456789abcdefFAKEkey0123456789"
NOW = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
TODAY = date(2026, 10, 22)
ARMY = "DEPT OF DEFENSE.DEPT OF THE ARMY.AMC.ACC.ACC-APG"

EDGE = "a" * 32       # solicitation, full and open: kept
CYBER = "b" * 32      # combined synopsis, small business set-aside: kept
DATA = "c" * 32       # sources sought, WOSB: kept; SAM.gov has no description for it
AWARD = "d" * 32      # award notice: dropped by type
EIGHT_A = "e" * 32    # 8(a) set-aside: dropped
REPAIR = "f" * 32     # title on the blocklist: dropped before its description is read
SPECIAL = "1" * 32    # special notice, listed under two NAICS codes
REPOST = "2" * 32     # sources sought that Front Door may already carry


def desc_url(notice_id: str) -> str:
    return f"https://api.sam.gov/prod/opportunities/v1/noticedesc?noticeid={notice_id}"


def notice(notice_id: str, title: str, kind: str = "Solicitation", set_aside: str | None = None,
           naics: str = "541715", deadline: str = "2026-11-20T17:00:00-05:00", **more: Any) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "noticeId": notice_id, "title": title, "solicitationNumber": f"SOL-{notice_id[:4]}", "type": kind,
        "baseType": kind, "fullParentPathName": ARMY, "postedDate": "2026-10-01", "responseDeadLine": deadline,
        "naicsCode": naics, "naicsCodes": [naics], "classificationCode": "AC12", "active": "Yes",
        "typeOfSetAside": set_aside, "typeOfSetAsideDescription": {
            None: None, "SBA": "Total Small Business Set-Aside (FAR 19.5)", "WOSB": "Women-Owned Small Business",
            "8A": "8(a) Set-Aside (FAR 19.8)"}.get(set_aside, set_aside),
        "description": desc_url(notice_id), "uiLink": f"https://sam.gov/opp/{notice_id}/view",
        "pointOfContact": [{"type": "primary", "fullName": "Pat Example", "email": "pat.example@army.mil", "phone": "5550100"}],
        "placeOfPerformance": {"city": {"name": "Aberdeen Proving Ground"}, "state": {"code": "MD"}},
        "resourceLinks": [f"https://sam.gov/api/prod/opps/v3/opportunities/resources/files/{notice_id[:8]}/download"],
    }
    raw.update(more)
    return raw


NOTICES = {
    EDGE: notice(EDGE, "Edge AI Autonomy for Contested Logistics", deadline="2026-11-05T17:00:00-05:00"),
    CYBER: notice(CYBER, "Cyber Range Modernization", "Combined Synopsis/Solicitation", "SBA", "541512",
                  deadline="2026-11-10T14:00:00-05:00"),
    DATA: notice(DATA, "Data Platform Market Research", "Sources Sought", "WOSB", "541511"),
    AWARD: notice(AWARD, "Cloud Hosting Services", "Award Notice", None, "541512"),
    EIGHT_A: notice(EIGHT_A, "Software Sustainment Services", "Solicitation", "8A", "541511"),
    REPAIR: notice(REPAIR, "Repair of Circuit Card Assemblies", naics="541511"),
    SPECIAL: notice(SPECIAL, "Industry Day: Machine Learning for ISR", "Special Notice"),
    REPOST: notice(REPOST, "Zero Trust Architecture Sources Sought", "Sources Sought", None, "541511",
                   deadline="2026-12-01T12:00:00-05:00"),
}
BY_CODE = {
    "541715": [EDGE, SPECIAL],
    "541512": [CYBER, AWARD, SPECIAL],
    "541511": [DATA, EIGHT_A, REPAIR, REPOST],
    "541513": [],
    "541519": [],
}
DESCRIPTIONS = {
    EDGE: "<p>Develop edge AI for contested logistics.</p><p>Phase I &amp; II.</p>",
    CYBER: "<p>Modernize the cyber range software and data pipeline.</p>",
    SPECIAL: "<p>Machine learning for ISR: an industry day.</p>",
    REPOST: "<p>Zero trust architecture for C2 software.</p>",
}


class Reply:
    def __init__(self, body: Any) -> None:
        self.body = json.dumps(body).encode("utf-8")

    def __enter__(self) -> "Reply":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def read(self) -> bytes:
        return self.body


def http_error(url: str, code: int, body: bytes = b"") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, code, {404: "Not Found", 429: "Too Many Requests"}.get(code, "Error"), None,  # type: ignore[arg-type]
                                  io.BytesIO(body))


class FakeSam:
    """Answers searches and description links from NOTICES; can run out of quota or fail."""

    def __init__(self, quota: int | None = None, fail: BaseException | None = None) -> None:
        self.by_code = {code: [NOTICES[n] for n in ids] for code, ids in BY_CODE.items()}
        self.searches: list[dict[str, str]] = []
        self.descriptions: list[str] = []
        self.quota = quota
        self.fail = fail
        self.requests = 0

    def __call__(self, request: Any, timeout: float) -> Reply:
        assert timeout >= 60
        url = request.full_url
        parts = urllib.parse.urlsplit(url)
        params = dict(urllib.parse.parse_qsl(parts.query))
        assert params.pop("api_key") == KEY
        self.requests += 1
        if self.fail is not None:
            raise self.fail
        if self.quota is not None and self.requests > self.quota:
            raise http_error(url, 429)
        if parts.path == "/opportunities/v2/search":
            self.searches.append(params)
            items = self.by_code[params["ncode"]]
            offset, limit = int(params["offset"]), int(params["limit"])
            return Reply({"totalRecords": len(items), "opportunitiesData": items[offset:offset + limit]})
        if parts.path == "/prod/opportunities/v1/noticedesc":
            self.descriptions.append(params["noticeid"])
            if params["noticeid"] not in DESCRIPTIONS:
                raise http_error(url, 404, b'{"error": "Description not found"}')
            return Reply({"description": DESCRIPTIONS[params["noticeid"]]})
        raise AssertionError(f"unexpected request to {parts.path}")


def run_id() -> int:
    return lq.start_run("SAM.gov", component="sam_gov")


# ------------------------------------------------------------------------------ the API

def test_search_asks_for_open_notices_one_naics_code_at_a_time_and_pages_by_offset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "PAGE_SIZE", 2)
    site = FakeSam()
    found = api.search("541511", TODAY, KEY, site, api.Budget(10))
    assert [n["noticeId"] for n in found] == [DATA, EIGHT_A, REPAIR, REPOST]
    assert [s["offset"] for s in site.searches] == ["0", "2"]
    first = site.searches[0]
    assert (first["ncode"], first["limit"], first["rdlfrom"], first["postedFrom"], first["postedTo"]) == (
        "541511", "2", "10/22/2026", "10/23/2025", "10/22/2026")
    assert "ptype" not in first   # notice types are checked here, not in the query


def test_the_budget_caps_requests_and_a_429_means_the_day_is_spent() -> None:
    budget = api.Budget(1)
    budget.spend()
    with pytest.raises(api.SamQuota):
        budget.spend()
    assert budget.used == 1
    with pytest.raises(api.SamQuota):
        api.search("541715", TODAY, KEY, FakeSam(quota=0), api.Budget(10))


def test_the_key_never_appears_in_errors_or_logs(caplog: pytest.LogCaptureFixture) -> None:
    url = f"https://api.sam.gov/opportunities/v2/search?api_key={KEY}"
    for failure in (http_error(url, 500), urllib.error.URLError("timed out")):
        site = FakeSam(fail=failure)
        with caplog.at_level(logging.DEBUG), pytest.raises(api.SamError) as raised:
            api.search("541715", TODAY, KEY, site, api.Budget(10))
        assert KEY not in str(raised.value) and raised.value.__cause__ is None
        assert site.requests == 2   # one retry
    assert KEY not in caplog.text


def test_a_description_is_plain_text_cut_to_4000_characters(monkeypatch: pytest.MonkeyPatch) -> None:
    site = FakeSam()
    assert api.description(desc_url(EDGE), KEY, site, api.Budget(5)) == "Develop edge AI for contested logistics.\nPhase I & II."
    assert api.description(desc_url(DATA), KEY, site, api.Budget(5)) == ""      # SAM.gov has none
    assert api.description("", KEY, site, api.Budget(5)) == ""                   # no link, no request
    assert site.descriptions == [EDGE, DATA]
    monkeypatch.setitem(DESCRIPTIONS, EDGE, "<p>" + "x" * 5000 + "</p>")
    assert len(api.description(desc_url(EDGE), KEY, site, api.Budget(5))) == records.DESCRIPTION_CHARS


def test_connections_use_ipv4_only(monkeypatch: pytest.MonkeyPatch) -> None:
    # api.sam.gov also publishes an IPv6 address, which hangs from the scan PC.
    asked: dict[str, Any] = {}

    def resolve(host: str, port: int, family: int = 0, kind: int = 0, *rest: Any) -> list[Any]:
        asked["family"] = family
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.10", port))]

    monkeypatch.setattr(api.socket, "getaddrinfo", resolve)
    monkeypatch.setattr(api.socket, "create_connection", lambda address, *rest, **kw: ("connected", address))
    assert api.ipv4_connect(("api.sam.gov", 443), 60) == ("connected", ("192.0.2.10", 443))
    assert asked["family"] == socket.AF_INET


# ------------------------------------------------------------------------------ records

def test_a_notice_becomes_a_calls_row() -> None:
    rec = records.build_record(NOTICES[EDGE], NOW, "Develop edge AI.")
    assert rec["id"] == f"samgov-{EDGE}" and rec["portal"] == "SAM.gov" and rec["source_type"] == "api"
    assert (rec["type"], rec["naics_code"], rec["set_aside"], rec["posted_date"], rec["due_date"]) == (
        "Solicitation", "541715", "", "2026-10-01", "2026-11-05T17:00:00-05:00")
    assert rec["department"] == "DEPT OF DEFENSE / DEPT OF THE ARMY / AMC / ACC / ACC-APG"
    assert rec["url"] == f"https://sam.gov/opp/{EDGE}/view" and rec["description"] == "Develop edge AI."
    extra = rec["extra"]
    assert extra["samgov_notice_id"] == EDGE and extra["samgov_solicitation_number"] == "SOL-aaaa"
    assert extra["samgov_type"] == "Solicitation" and extra["samgov_closed"] is False
    assert extra["samgov_contacts"] == [{"name": "Pat Example", "email": "pat.example@army.mil", "phone": "5550100", "role": "primary"}]
    assert extra["samgov_place_of_performance"] == "Aberdeen Proving Ground, MD"
    assert extra["samgov_attachments"] == [f"https://sam.gov/api/prod/opps/v3/opportunities/resources/files/{EDGE[:8]}/download"]
    assert "description" not in records.build_record(NOTICES[EDGE], NOW)   # a refresh never blanks stored text


def test_types_set_asides_and_the_closed_flag() -> None:
    types = {kind: records.build_record(notice(EDGE, "x", kind), NOW)["type"] for kind in (
        "Solicitation", "Combined Synopsis/Solicitation", "Presolicitation", "Sources Sought", "Special Notice")}
    assert types == {"Solicitation": "Solicitation", "Combined Synopsis/Solicitation": "Solicitation",
                     "Presolicitation": "Presolicitation", "Sources Sought": "Sources sought", "Special Notice": "Special notice"}
    assert records.build_record(NOTICES[CYBER], NOW)["set_aside"] == "Total Small Business Set-Aside (FAR 19.5)"
    assert records.build_record(notice(EDGE, "x", deadline="2026-10-21T17:00:00-05:00"), NOW)["extra"]["samgov_closed"] is True
    assert records.build_record(notice(EDGE, "x", active="No"), NOW)["extra"]["samgov_closed"] is True


def test_the_search_settings_keep_what_velocity_can_bid_on() -> None:
    rules = records.load_rules(portal.SEARCH_PATH)
    assert rules.naics_codes == ["541511", "541512", "541513", "541519", "541715"]
    assert records.keep(NOTICES[EDGE], rules) is None
    assert records.keep(NOTICES[CYBER], rules) is None
    assert records.keep(NOTICES[DATA], rules) is None
    assert records.keep(NOTICES[AWARD], rules) == "type Award Notice"
    assert records.keep(NOTICES[EIGHT_A], rules) == "set-aside 8A"
    assert records.keep(notice(EDGE, "x", set_aside="NONE"), rules) is None


# ------------------------------------------------------------------------------ a run

def test_fetch_all_stores_new_notices_and_spends_requests_only_where_needed(ledger_db: str) -> None:
    site = FakeSam()
    counts = scrape.fetch_all(run_id(), now=NOW, opener=site, key=KEY)
    assert sorted(s["ncode"] for s in site.searches) == ["541511", "541512", "541513", "541519", "541715"]
    assert sorted(site.descriptions) == sorted([EDGE, CYBER, DATA, SPECIAL, REPOST])   # none for the dropped
    assert counts == {"found": 8, "scraped": 5, "new": 5, "failed": 0, "dropped": 3, "reposts": 0,
                      "pending": 0, "requests": 10}
    stored = {row["id"]: row for row in lq.calls_where(portal="SAM.gov")}
    assert set(stored) == {f"samgov-{n}" for n in (EDGE, CYBER, DATA, SPECIAL, REPOST)}
    assert stored[f"samgov-{EDGE}"]["description"].startswith("Develop edge AI")
    assert not stored[f"samgov-{DATA}"]["description"]


def test_a_second_run_refreshes_stored_notices_without_reading_descriptions_again(ledger_db: str) -> None:
    scrape.fetch_all(run_id(), now=NOW, opener=FakeSam(), key=KEY)
    site = FakeSam()
    site.by_code["541715"][0] = {**NOTICES[EDGE], "responseDeadLine": "2026-12-01T17:00:00-05:00"}
    counts = scrape.fetch_all(run_id(), now=NOW, opener=site, key=KEY)
    assert site.descriptions == [] and counts["new"] == 0 and counts["scraped"] == 5 and counts["requests"] == 5
    edge = lq.get_call(f"samgov-{EDGE}")
    assert edge is not None and edge["due_date"] == "2026-12-01T17:00:00-05:00"
    assert edge["description"].startswith("Develop edge AI")


def test_a_spent_budget_keeps_what_was_read_and_leaves_the_rest_for_the_next_run(ledger_db: str,
                                                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scrape, "REQUEST_BUDGET", 7)   # 5 searches, then 2 descriptions
    counts = scrape.fetch_all(run_id(), now=NOW, opener=FakeSam(), key=KEY)
    assert (counts["requests"], counts["new"], counts["pending"]) == (7, 2, 3)
    stored = {row["id"] for row in lq.calls_where(portal="SAM.gov")}
    assert stored == {f"samgov-{EDGE}", f"samgov-{CYBER}"}   # the soonest deadlines first
    monkeypatch.setattr(scrape, "REQUEST_BUDGET", 900)       # the next day
    counts = scrape.fetch_all(run_id(), now=NOW, opener=FakeSam(), key=KEY)
    assert counts["new"] == 3 and counts["pending"] == 0


def test_sam_gov_saying_the_day_is_spent_ends_the_run_cleanly(ledger_db: str) -> None:
    counts = scrape.fetch_all(run_id(), now=NOW, opener=FakeSam(quota=6), key=KEY)
    assert counts["new"] == 1 and counts["pending"] == 4


def test_the_limit_caps_new_notices(ledger_db: str) -> None:
    site = FakeSam()
    counts = scrape.fetch_all(run_id(), limit=2, now=NOW, opener=site, key=KEY)
    assert counts["new"] == 2 and len(site.descriptions) == 2 and counts["pending"] == 3


def test_a_notice_front_door_already_carries_is_not_stored_twice(ledger_db: str) -> None:
    lq.upsert_call({"id": "sscfd-MCZEROTRUST", "portal": "SSC Front Door", "title": "Zero Trust RFI",
                    "extra": {"sscfd_sam_notice_id": REPOST}}, run_id())
    site = FakeSam()
    counts = scrape.fetch_all(run_id(), now=NOW, opener=site, key=KEY)
    assert counts["reposts"] == 1 and REPOST not in site.descriptions
    assert lq.get_call(f"samgov-{REPOST}") is None


def test_the_registry_finds_sam_gov() -> None:
    found = registry.get("sam_gov")
    assert found.name == "SAM.gov" and not found.needs_browser and found.fetch_timeout == 1800
    assert found.keywords and found.keywords.exists() and found.notes and found.notes.exists()
    assert "contracting officer" in found.how_to_submit
