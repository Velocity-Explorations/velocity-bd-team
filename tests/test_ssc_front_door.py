"""SSC Front Door: the public Events list, read over plain HTTP and stored as calls (PRO-482)."""
from __future__ import annotations

import copy
import json
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from ledger import queries as lq
from portals import registry
from portals.shared.keyword_filter import filter_calls
from portals.ssc_front_door import api, records, scrape

FIXTURES = Path(__file__).resolve().parent / "fixtures"
EVENTS = json.loads((FIXTURES / "ssc_front_door_events.json").read_text(encoding="utf-8"))
HOME = (FIXTURES / "ssc_front_door_home.html").read_text(encoding="utf-8")
LISTINGS: list[dict[str, Any]] = EVENTS["actions"][0]["returnValue"]["returnValue"]
REPO = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)

ZTA = "MCRMZYBYDC7ZCZBECOKP7CZIMPQQ"               # RFI reposted from SAM.gov, ended 11 Sep 2026
INDUSTRY_DAYS = "MC3Z3PADFN6BHZHEA7L5MQH6JIHE"     # open until 22 Oct 2026
DEFENCE_IN_SPACE = "MCGRCMXTQ5VRBL7BEDCTBF5UAKCQ"  # open, in London, names two SSC offices
WEBINAR = "MCHUADDDWURVCP3PZXC7ORXPDZSU"           # ended 22 Apr 2026
KRONOS = "MC3L3H44ALMRBS3KSJNVH5BDFCCM"            # CSO reposted from SAM.gov, ended
OLD_INDUSTRY_DAYS = "MC6IZKBLUPOJHU7KWVPV5YXVIOAQ"  # its Summary only repeats the audience
CHALLENGE = "MCB3S2G4PAZVFQBGBS36GPYITRVE"         # ended


def listing(key: str) -> dict[str, Any]:
    return next(r for r in LISTINGS if r["contentKey"] == key)


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
    """Serves the home page and the Events data call from the fixtures, page by page like the real site."""

    def __init__(self, failed_posts: int = 0) -> None:
        self.gets = 0
        self.posts: list[dict[str, Any]] = []
        self.failed_posts = failed_posts

    def __call__(self, request: Any, timeout: float) -> Reply:
        assert timeout >= 10
        if request.data is None:
            self.gets += 1
            return Reply(HOME)
        form = urllib.parse.parse_qs(request.data.decode("utf-8"))
        params = json.loads(form["message"][0])["actions"][0]["params"]["params"]
        self.posts.append(params)
        if len(self.posts) <= self.failed_posts:
            return Reply(json.dumps({"actions": [{"state": "ERROR", "error": [{"message": "stale framework"}]}]}))
        start = params["page"] * params["pageSize"]
        page = LISTINGS[start:start + params["pageSize"]]
        return Reply(json.dumps({"actions": [{"state": "SUCCESS", "returnValue": {"returnValue": page}}]}))


# ------------------------------------------------------------------------------ the site

def test_framework_ids_come_from_the_home_page() -> None:
    assert api.framework_ids(HOME) == (
        "SGRNczhXdnNHNDNKUWhIdXFhdFJlUWtVMjdnTGFERUU2S3FfSVdrcU92bkExNS4zLjE2MDEw", "1893_tc0hDgV9c96ds91w6tiHCw")
    with pytest.raises(api.FrontDoorError):
        api.framework_ids("<html><body>Sorry to interrupt</body></html>")


def test_request_body_asks_for_one_page_of_events() -> None:
    form = urllib.parse.parse_qs(api.request_body(2, 250, ("fw", "hash")))
    action = json.loads(form["message"][0])["actions"][0]
    assert (action["params"]["classname"], action["params"]["method"]) == ("SSCFD_ManagedContentController", "getContentList")
    assert action["params"]["params"] == {"page": 2, "pageSize": 250, "language": "en_US", "filterby": "Events"}
    context = json.loads(form["aura.context"][0])
    assert context["fwuid"] == "fw" and context["loaded"] == {"APPLICATION@markup://siteforce:communityApp": "hash"}
    assert form["aura.pageURI"] == ["/SSCFrontDoor/s/events"] and form["aura.token"] == ["null"]


def test_records_from_returns_the_listings_and_refuses_a_failed_call() -> None:
    assert [r["contentKey"] for r in api.records_from(EVENTS)] == [r["contentKey"] for r in LISTINGS]
    with pytest.raises(api.FrontDoorError):
        api.records_from({"actions": [{"state": "ERROR"}]})
    with pytest.raises(api.FrontDoorError):
        api.records_from({"unexpected": True})


def test_fetch_records_pages_until_a_short_page() -> None:
    site = FakeSite()
    assert len(api.fetch_records(site, page_size=3)) == len(LISTINGS) == 7
    assert [p["page"] for p in site.posts] == [0, 1, 2] and site.gets == 1


def test_fetch_records_rereads_the_framework_ids_and_retries_once() -> None:
    site = FakeSite(failed_posts=1)
    assert len(api.fetch_records(site)) == 7
    assert site.gets == 2 and len(site.posts) == 2
    with pytest.raises(api.FrontDoorError):
        api.fetch_records(FakeSite(failed_posts=2))


# ---------------------------------------------------------------------------- the records

def test_a_reposted_sam_notice_maps_to_a_call() -> None:
    rec = records.build_record(listing(ZTA), NOW)
    assert rec["id"] == f"sscfd-{ZTA}" and rec["portal"] == "SSC Front Door"
    assert rec["title"] == "RFI - Zero Trust Architecture (ZTA) Vendor Framework"
    assert rec["type"] == "RFI" and rec["department"] == "Space Systems Command"
    assert rec["due_date"] == "11 SEP 2026 : 15:00 PDT" and rec["posted_date"] == "2026-08-03"
    assert rec["url"] == ("https://sscfrontdoor.experience.crmforce.mil/SSCFrontDoor/s/events/"
                          f"rfi-zero-trust-architecture-zta-vendor-framework-{ZTA}")
    assert rec["source_type"] == "scrape" and rec["naics_code"] == "" and rec["set_aside"] == ""
    extra = rec["extra"]
    assert extra["sscfd_sam_notice_id"] == "df6f48b65a7d43cf92c7402317ccaaf4"
    assert extra["sscfd_sam_url"] == "https://sam.gov/opp/df6f48b65a7d43cf92c7402317ccaaf4/view"
    assert extra["sscfd_closed"] is True and extra["sscfd_location"] == "SAM.GOV"


def test_an_open_conference_abroad_keeps_its_own_time_zone_and_offices() -> None:
    rec = records.build_record(listing(DEFENCE_IN_SPACE), NOW)
    assert rec["type"] == "Conference" and rec["department"] == "SSC/SYD88, SSC/IA"
    assert rec["due_date"] == "28 OCT 2026 : 15:00 GMT"
    assert rec["description"].startswith("A Free Event By the Space & Defence Community")
    assert "​" not in rec["description"] and "&amp;" not in rec["description"]
    extra = rec["extra"]
    assert extra["sscfd_closed"] is False and extra["sscfd_sam_notice_id"] is None
    assert extra["sscfd_start"] == "2026-10-27T08:00:00Z" and extra["sscfd_time_zone"] == "Europe/London"


def test_types_and_descriptions_of_the_other_listings() -> None:
    built = {key: records.build_record(listing(key), NOW) for key in (INDUSTRY_DAYS, WEBINAR, KRONOS, OLD_INDUSTRY_DAYS, CHALLENGE)}
    assert {key: rec["type"] for key, rec in built.items()} == {
        INDUSTRY_DAYS: "Industry day", WEBINAR: "Webinar", KRONOS: "CSO",
        OLD_INDUSTRY_DAYS: "Industry day", CHALLENGE: "Challenge"}
    assert built[INDUSTRY_DAYS]["due_date"] == "22 OCT 2026 : 17:00 PDT"
    assert built[WEBINAR]["due_date"] == "22 APR 2026 : 14:00 EDT"
    assert built[KRONOS]["extra"]["sscfd_sam_notice_id"] == "8f1cec2c41424a39bc2e6769f13af669"
    assert built[OLD_INDUSTRY_DAYS]["description"].startswith("Space Industry Days provides industry")
    assert len(built[INDUSTRY_DAYS]["description"]) <= records.DESCRIPTION_CHARS


@pytest.mark.parametrize("title, location, description, expected", [
    ("RFI - Zero Trust Architecture (ZTA) Vendor Framework", "SAM.GOV", "", "RFI"),
    ("Request for Information: Space C2", "", "", "RFI"),
    ("Sources Sought: Ground Systems", "", "", "Sources sought"),
    ("Kronos Family of Systems Commercial Solutions Opening (CSO)", "SAM.GOV", "", "CSO"),
    ("Space Domain Awareness BAA", "", "", "Solicitation"),
    ("Industry Day: Kronos Mission Catalyst Day", "", "", "Industry day"),
    ("Hyperspace Challenge Webinar: How to Win with Primes", "Virtual", "", "Webinar"),
    ("Tech Talk", "WEBINAR", "", "Webinar"),
    ("On-Orbit Space Logistics Challenge", "", "", "Challenge"),
    ("International Security Space Forum", "Arlington, VA", "", "Conference"),
    ("RTR VICTUS Responsive Launch Space Vehicle", "SAM.GOV", "This Sources Sought notice asks", "Sources sought"),
    ("Space Vehicle Notice", "SAM.GOV", "Details on SAM.gov", "SAM.gov notice"),
    ("CyberSat 2026", "Reston, VA", "", "Event"),
])
def test_derive_type(title: str, location: str, description: str, expected: str) -> None:
    assert records.derive_type(title, location, description) == expected


# ------------------------------------------------------------------------ into the ledger

def test_fetch_all_stores_the_open_listings_and_skips_ended_ones(ledger_db: str) -> None:
    site = FakeSite()
    counts = scrape.fetch_all(lq.start_run("SSC Front Door"), now=NOW, opener=site)
    stored = {row["id"] for row in lq.calls_where(portal="SSC Front Door")}
    assert stored == {f"sscfd-{INDUSTRY_DAYS}", f"sscfd-{DEFENCE_IN_SPACE}"}
    assert counts == {"found": 7, "scraped": 2, "new": 2, "failed": 0}
    assert site.gets == 1 and len(site.posts) == 1


def test_fetch_all_still_updates_a_stored_listing_once_it_ends(ledger_db: str) -> None:
    earlier = datetime(2026, 9, 1, tzinfo=timezone.utc)
    lq.upsert_call(records.build_record(listing(ZTA), earlier), lq.start_run("SSC Front Door"))
    assert json.loads(lq.get_call(f"sscfd-{ZTA}")["extra"])["sscfd_closed"] is False   # type: ignore[index]
    counts = scrape.fetch_all(lq.start_run("SSC Front Door"), now=NOW, opener=FakeSite())
    assert json.loads(lq.get_call(f"sscfd-{ZTA}")["extra"])["sscfd_closed"] is True    # type: ignore[index]
    assert counts["scraped"] == 3 and counts["new"] == 2


def test_fetch_all_honours_the_limit(ledger_db: str) -> None:
    counts = scrape.fetch_all(lq.start_run("SSC Front Door"), limit=1, now=NOW, opener=FakeSite())
    assert counts["scraped"] == 1 and len(lq.calls_where(portal="SSC Front Door")) == 1


def test_a_repost_of_a_notice_sam_gov_already_stored_is_skipped(ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    # Whichever copy reaches the ledger first stays, so nobody decides the same notice twice (PRO-525).
    notice = "0123456789abcdef0123456789abcdef"
    lq.upsert_call({"id": f"samgov-{notice}", "portal": "SAM.gov", "title": "Industry days"}, lq.start_run("SAM.gov"))
    reposted = copy.deepcopy(listing(INDUSTRY_DAYS))
    reposted["contentNodes"]["eventURL"] = {"value": f"https://sam.gov/opp/{notice}/view"}
    monkeypatch.setattr(scrape, "fetch_records", lambda opener=None: [reposted, listing(DEFENCE_IN_SPACE)])
    counts = scrape.fetch_all(lq.start_run("SSC Front Door"), now=NOW)
    assert lq.get_call(f"sscfd-{INDUSTRY_DAYS}") is None and lq.get_call(f"sscfd-{DEFENCE_IN_SPACE}") is not None
    assert counts == {"found": 2, "scraped": 1, "new": 1, "failed": 0}


# ------------------------------------------------------------------------ the portal entry

def test_the_registry_finds_ssc_front_door() -> None:
    portal = registry.get("ssc_front_door")
    assert portal.name == "SSC Front Door" and not portal.needs_browser and portal.fetch_timeout == 120
    assert portal.keywords and portal.keywords.exists() and portal.notes and portal.notes.exists()
    assert "SAM.gov" in portal.how_to_submit


def test_its_keywords_keep_an_ai_industry_day_that_vulcan_blocks(ledger_db: str) -> None:
    row = {"id": "sscfd-x", "portal": "SSC Front Door", "title": "Industry Day: AI for Space Command and Control",
           "description": "Machine learning for C2 software."}
    lq.upsert_call(row, lq.start_run("SSC Front Door"))
    kept, _ = filter_calls([row], REPO / "portals" / "ssc_front_door" / "keywords.yaml")
    _, vulcan_rejected = filter_calls([row], REPO / "portals" / "vulcan_sof" / "keywords.yaml")
    assert [d.id for d in kept] == ["sscfd-x"] and [d.id for d in vulcan_rejected] == ["sscfd-x"]
