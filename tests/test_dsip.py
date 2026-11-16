"""DSIP: the Defense Department's SBIR and STTR topics as calls, one call a topic (David, 16 Nov 2026).

DSIP's robots.txt forbids automated access, so the topics are read from SBIR.gov's copy, which allows it. SBIR.gov can
miss a whole release (on 16 Nov 2026 it had all 79 Release 2 topics and none of the 23 from Release 1), so two more
pieces close the gap: DSIP's own topic DOCX files, downloaded by a person and dropped in data/dsip/inbox, become calls on
the next scan; and after each scan the portal's watch alerts on any open DoD cycle on AFWERX or SpaceWERX that has no
topics in the ledger.

The pages below are made up but shaped like SBIR.gov's: a topic list with ten links a page, and a topic page with its
title, funding agency, topic number, solicitation number, tags, status, release schedule and description.
"""
from __future__ import annotations

import io
import json
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from ledger import queries as lq
from portals import registry
from portals.dsip import inbox, records, sbirgov, scrape, topics, watch
from portals.dsip.portal import KEYWORDS_PATH
from portals.shared.keyword_filter import decide, load_keywords

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def topic_page(title: str, topic: str, agency: str = "Navy", solicitation: str = "27.BZ", program: str = "SBIR",
               status: str = "Open", release: str = "November 4, 2026", opens: str = "December 2, 2026",
               close: str = "January 6, 2027", description: str = "Software that guides a maintainer step by step.") -> str:
    return (
        '<html><body><main><section>'
        '<p><a href="/topics">Back to Funding Opportunities Search</a></p> '
        f'<h2>{title}</h2>'
        '<div class="grid-row"><div><img src="/seal.png" alt="Seal of the Agency: DOD"></div>'
        f'<div> <h3>Funding Agency</h3> <p class="margin-bottom-0">DOW</p> <p class="margin-bottom-0"> {agency}</p> </div>'
        '<div class="border-top-05">'
        '<p class="margin-top-0"><strong>Year:</strong> 2027</p> '
        f'<p class="margin-top-0"><strong>Topic Number:</strong> {topic}</p> '
        f'<p class="margin-top-0"><strong>Solicitation Number:</strong> {solicitation}</p> '
        '<div class="display-inline-flex"> <p class="usa-sr-only">Tagged as:</p> '
        f'<p class="margin-right-1 bg-base-dark">{program}</p> <p class="margin-right-1 bg-base-dark">BOTH</p> </div></div></div>'
        f'<p class="font-serif-lg text-bold">Solicitation Status: <span class="margin-right-1 bg-green">{status}</span></p>'
        '<a href="https://www.dodsbirsttr.mil/topics-app/" class="ext usa-button">View Official Solicitation</a>'
        '</section><section><h2>Release Schedule</h2><ol>'
        f'<li><p><strong class="text-secondary">Release Date</strong><br>{release}</p></li>'
        f'<li><p><strong class="text-secondary">Open Date</strong><br>{opens}</p></li>'
        f'<li><p><strong class="text-secondary">Due Date(s)</strong><br>{close}</p></li>'
        f'<li><p><strong class="text-secondary">Close Date</strong><br>{close}</p></li>'
        '</ol></section><section><div><h2><span>Description</span></h2></div>'
        f'<div class="grid-col-12"><div class="pre-form-wrapped usa-prose">{description}</div> </div></section>'
        '</main></body></html>'
    )


def list_page(*node_ids: int) -> str:
    items = "".join(f'<div class="views-row"><a href="/topics/{n}">A topic</a><p>Open</p></div>' for n in node_ids)
    return f"<html><body><div class=\"view-content\">{items}</div></body></html>"


MAINTAINER = topic_page("Agentic maintenance associate for ship crews", "DON27BZ02-NV901")
SWARM = topic_page("Swarm control for small boats", "DON27TZ02-NV902", solicitation="27.TZ", program="STTR")
EDGE = topic_page("Edge autonomy test harness", "DAF27BZ02-DV903", agency="USAF")
CLOSED = topic_page("Closed topic", "DAF27BZ01-DV904", agency="USAF", status="Closed", close="November 25, 2026")
OLD_STYLE = topic_page("Rolling DARPA topic", "HR0011SB20264-01", agency="DARPA", solicitation="HR0011SB20264",
                       release="October 1, 2025", opens="October 1, 2025", close="April 1, 2027")


class Reply:
    def __init__(self, body: str) -> None:
        self.body = body.encode("utf-8")

    def read(self) -> bytes:
        return self.body

    def __enter__(self) -> Reply:
        return self

    def __exit__(self, *exc: Any) -> None:
        return None


class Site:
    """SBIR.gov as a test sees it: list pages by page number, topic pages by node id."""

    def __init__(self, lists: list[list[int]], pages: dict[int, str], down: bool = False) -> None:
        self.lists, self.pages, self.down = lists, pages, down
        self.asked: list[str] = []

    def __call__(self, request: Any, timeout: float | None = None) -> Reply:
        url = request.full_url
        self.asked.append(url)
        if self.down:
            raise urllib.error.HTTPError(url, 503, "Service Unavailable", {}, None)   # type: ignore[arg-type]
        if "/topics/" in url:
            node = int(url.rsplit("/", 1)[1])
            if node not in self.pages:
                raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)   # type: ignore[arg-type]
            return Reply(self.pages[node])
        page = int(url.split("page=")[1].split("&")[0])
        return Reply(list_page(*(self.lists[page] if page < len(self.lists) else [])))


def stored(call_id: str) -> dict[str, Any]:
    call = lq.get_call(call_id)
    assert call is not None, call_id
    call["extra"] = json.loads(call["extra"] or "{}")
    return call


# ------------------------------------------------------------------ topic numbers and cycles

def test_a_topic_number_names_the_component_solicitation_release_program_and_phase() -> None:
    edge = topics.parse_topic_number("DAF27BZ02-DV023")
    assert edge is not None
    assert (edge.component, edge.solicitation, edge.release, edge.program, edge.phase) == (
        "DAF", "27.BZ", 2, "SBIR", "Direct to Phase II")
    swarm = topics.parse_topic_number(" don27tz02-nv012 ")
    assert swarm is not None and (swarm.text, swarm.program, swarm.phase) == ("DON27TZ02-NV012", "STTR", "Phase I")
    army = topics.parse_topic_number("ARM27BX01-DP001")
    assert army is not None and army.key == ("27", "BX", 1)
    assert topics.parse_topic_number("HR0011SB20264-01") is None
    assert topics.parse_topic_number("") is None
    assert topics.call_id("DON27BZ02-NV021") == "dsip-don27bz02-nv021"   # the id of the topics added by hand on 10 Nov
    assert topics.component_name("DON") == "Department of the Navy (DON)"
    assert topics.component_name("XYZ") == "XYZ"


def test_a_cycle_title_names_its_solicitations_and_release() -> None:
    assert topics.cycle_keys("DOW SBIR SPECIFIC TOPIC 27.BZ & 27.BX Release 1") == {("27", "BZ", 1), ("27", "BX", 1)}
    assert topics.cycle_keys("DAF STTR Specific Topic 27.TZ \N{EN DASH} Release 2") == {("27", "TZ", 2)}
    assert topics.cycle_keys("PY26.2 TACFI Notice of Opportunity") == set()
    assert topics.cycle_keys("DAF SBIR 27.BZ") == set()   # no release named


# ------------------------------------------------------------------ SBIR.gov's topic page to a call

def test_a_topic_page_becomes_a_call() -> None:
    fields = records.read_topic_page(MAINTAINER)
    assert fields["title"] == "Agentic maintenance associate for ship crews"
    assert (fields["topic"], fields["solicitation"], fields["status"], fields["agency"]) == ("DON27BZ02-NV901", "27.BZ", "Open", "Navy")
    assert fields["tags"] == ["SBIR", "BOTH"]
    rec = records.from_sbirgov(fields, "https://www.sbir.gov/topics/13001", NOW)
    assert rec["id"] == "dsip-don27bz02-nv901"
    assert rec["portal"] == "DSIP"
    assert rec["title"] == "DON27BZ02-NV901 Agentic maintenance associate for ship crews"
    assert rec["type"] == "SBIR Phase I"
    assert rec["department"] == "Department of the Navy (DON)"
    assert (rec["posted_date"], rec["due_date"]) == ("2026-11-04", "2027-01-06")
    assert rec["url"] == "https://www.sbir.gov/topics/13001"
    assert rec["description"].startswith("A DoD SBIR Phase I topic from the Department of the Navy (DON), in solicitation 27.BZ Release 2.")
    assert "https://www.dodsbirsttr.mil/topics-app/" in rec["description"]
    assert rec["description"].endswith("Software that guides a maintainer step by step.")
    assert rec["extra"] == {
        "dsip_topic": "DON27BZ02-NV901", "dsip_solicitation": "27.BZ", "dsip_release": 2, "dsip_component": "DON",
        "dsip_program": "SBIR", "dsip_phase": "Phase I", "dsip_pre_release": "2026-11-04", "dsip_open": "2026-12-02",
        "dsip_source": "SBIR.gov", "dsip_sbirgov_id": "13001", "dsip_itar": None, "dsip_cmmc": None,
        "dsip_keywords": None, "dsip_closed": False,
    }


def test_a_closed_or_past_topic_is_marked_closed() -> None:
    closed = records.from_sbirgov(records.read_topic_page(CLOSED), "https://www.sbir.gov/topics/13004", NOW)
    assert closed["extra"]["dsip_closed"] is True
    past = topic_page("Past topic", "DON27BZ01-NV905", close="November 1, 2026")
    assert records.from_sbirgov(records.read_topic_page(past), "https://www.sbir.gov/topics/13005", NOW)["extra"]["dsip_closed"] is True


def test_a_topic_numbered_the_old_way_takes_its_details_from_the_page() -> None:
    rec = records.from_sbirgov(records.read_topic_page(OLD_STYLE), "https://www.sbir.gov/topics/13006", NOW)
    assert rec["id"] == "dsip-hr0011sb20264-01"
    assert rec["title"] == "HR0011SB20264-01 Rolling DARPA topic"
    assert rec["type"] == "SBIR topic"
    assert rec["department"] == "DARPA"
    assert rec["extra"]["dsip_release"] is None and rec["extra"]["dsip_component"] is None
    assert rec["extra"]["dsip_solicitation"] == "HR0011SB20264"


def test_a_page_with_no_topic_number_is_refused() -> None:
    with pytest.raises(ValueError):
        records.from_sbirgov(records.read_topic_page("<html><h2>Nothing here</h2></html>"), "https://www.sbir.gov/topics/1", NOW)


def test_every_topic_passes_the_keyword_filter_for_the_judges() -> None:
    keywords = load_keywords(KEYWORDS_PATH)
    repair = topic_page("Maintenance associate", "DON27BZ02-NV906",
                        description="Interactive guidance for complex diagnostic and repair tasks, with spare parts lists.")
    for page in (SWARM, repair):   # the other portals' blocklist would drop the second: DSIP's is empty
        rec = records.from_sbirgov(records.read_topic_page(page), "https://www.sbir.gov/topics/13002", NOW)
        assert decide({"id": rec["id"], "title": rec["title"], "description": rec["description"]}, keywords).result == "kept"


# ------------------------------------------------------------------ the scan

def test_a_scan_reads_every_list_page_then_each_topic(ledger_db: str) -> None:
    run_id = lq.start_run("DSIP", component="dsip")
    site = Site(lists=[[13001, 13002], [13003]], pages={13001: MAINTAINER, 13002: SWARM, 13003: EDGE})
    counts = scrape.fetch_all(run_id, now=NOW, opener=site, delay=0, folder=None)
    assert counts == {"found": 3, "scraped": 3, "new": 3, "failed": 0}
    lists = [u for u in site.asked if "/topics?" in u]
    assert len(lists) == 3 and all("status=Open" in u and "agency%5BDOD%5D=DOD" in u for u in lists)
    assert [u.rsplit("/", 1)[1] for u in site.asked if "/topics/" in u] == ["13001", "13002", "13003"]
    assert stored("dsip-don27tz02-nv902")["type"] == "STTR Phase I"
    again = scrape.fetch_all(lq.start_run("DSIP", component="dsip"), now=NOW, opener=site, delay=0, folder=None)
    assert again["new"] == 0 and again["scraped"] == 3


def test_a_topic_added_by_hand_is_refreshed_not_doubled(ledger_db: str) -> None:
    run_id = lq.start_run("dsip", component="dsip_manual")
    lq.upsert_call({"id": "dsip-don27bz02-nv901", "portal": "DSIP", "title": "DON27BZ02-NV901 Agentic maintenance",
                    "type": "SBIR Phase I", "due_date": "2027-01-06", "extra": {}}, run_id)
    site = Site(lists=[[13001]], pages={13001: MAINTAINER})
    counts = scrape.fetch_all(lq.start_run("DSIP", component="dsip"), now=NOW, opener=site, delay=0, folder=None)
    assert counts["new"] == 0 and counts["scraped"] == 1
    assert stored("dsip-don27bz02-nv901")["extra"]["dsip_source"] == "SBIR.gov"


def test_a_closed_topic_never_stored_is_skipped_and_an_unreadable_page_counts_as_failed(ledger_db: str) -> None:
    site = Site(lists=[[13004, 13009, 13001]], pages={13004: CLOSED, 13001: MAINTAINER})   # 13009 answers 404
    counts = scrape.fetch_all(lq.start_run("DSIP", component="dsip"), now=NOW, opener=site, delay=0, folder=None)
    assert counts == {"found": 3, "scraped": 1, "new": 1, "failed": 1}
    assert lq.get_call("dsip-daf27bz01-dv904") is None


def test_sbirgov_down_fails_the_scan_so_the_pipeline_alerts(ledger_db: str) -> None:
    with pytest.raises(sbirgov.SbirGovError):
        scrape.fetch_all(lq.start_run("DSIP", component="dsip"), now=NOW, opener=Site([], {}, down=True), delay=0, folder=None)


def test_a_stored_topic_past_its_close_date_is_marked_closed(ledger_db: str) -> None:
    run_id = lq.start_run("dsip", component="dsip_manual")
    lq.upsert_call({"id": "dsip-daf27bz01-dv007", "portal": "DSIP", "title": "DAF27BZ01-DV007 Reusable Illumination System",
                    "due_date": "2026-11-15", "extra": {}}, run_id)
    lq.upsert_call({"id": "dsip-don27bz02-nv021", "portal": "DSIP", "title": "DON27BZ02-NV021 Knowledge delivery",
                    "due_date": "2027-01-06", "extra": {}}, run_id)
    scrape.fetch_all(lq.start_run("DSIP", component="dsip"), now=NOW, opener=Site([[]], {}), delay=0, folder=None)
    assert stored("dsip-daf27bz01-dv007")["extra"] == {"dsip_closed": True}
    assert stored("dsip-don27bz02-nv021")["extra"] == {}


# ------------------------------------------------------------------ DSIP DOCX files dropped by a person

def write_topic_docx(path: Path, first: str, itar: bool = True) -> Path:
    import docx

    document = docx.Document()
    for text in [
        first,
        "PROJECTED CMMC LEVEL REQUIREMENT:", "Level 2 (Self)",
        "TECHNOLOGY AREAS:", "None",
        "MODERNIZATION PRIORITIES:", "Trusted AI and Autonomy",
        "KEYWORDS:", "autonomy; test harness; edge",
        "ADDITIONAL INFORMATION", "N/A",
        "OBJECTIVE:", "Build a test harness for edge autonomy.",
        "ITAR:",
        ("The technology within this topic is restricted under the International Traffic in Arms Regulation (ITAR)."
         if itar else "N/A"),
        "DESCRIPTION:", "Autonomy software fails in ways that lab tests miss.", "The harness replays field data.",
        "PHASE I:", "Show the harness on recorded data.",
        "PHASE II:", "Run it on a test range.",
        "REFERENCES:", "1. A made-up reference.",
    ]:
        document.add_paragraph(text)
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    document.save(buffer)
    with open(inbox.long_path(path), "wb") as handle:   # DSIP's long file names can run past Windows' 260 characters
        handle.write(buffer.getvalue())
    return path


def release_1_cycle(run_id: int) -> None:
    lq.upsert_call({"id": "afwerx-dow-sbir-specific-topic-27-bz-27-bx-release-1", "portal": "AFWERX",
                    "title": "DOW SBIR SPECIFIC TOPIC 27.BZ & 27.BX Release 1", "type": "SBIR cycle", "due_date": "2026-11-25",
                    "extra": {"afwerx_pre_release": "2026-10-07", "afwerx_open": "2026-10-28", "afwerx_closed": False}}, run_id)


def test_a_dsip_docx_in_the_inbox_becomes_a_call_with_its_cycles_dates(ledger_db: str, tmp_path: Path) -> None:
    run_id = lq.start_run("DSIP", component="dsip")
    release_1_cycle(run_id)
    folder = tmp_path / "dsip"
    write_topic_docx(folder / "inbox" / "topic_DAF27BZ01-DV901_Edge autonomy test harness.DOCX",
                     "DAF27BZ01-DV901: Edge autonomy test harness")
    counts = inbox.import_inbox(run_id, folder=folder, now=NOW)
    assert counts == {"found": 1, "scraped": 1, "new": 1, "failed": 0}
    call = stored("dsip-daf27bz01-dv901")
    assert call["title"] == "DAF27BZ01-DV901 Edge autonomy test harness"
    assert call["type"] == "SBIR Direct to Phase II"
    assert call["department"] == "Department of the Air Force (DAF)"
    assert (call["posted_date"], call["due_date"]) == ("2026-10-07", "2026-11-25")
    assert "Build a test harness for edge autonomy." in call["description"]
    assert "The harness replays field data." in call["description"]
    assert call["extra"]["dsip_source"] == "DSIP DOCX"
    assert (call["extra"]["dsip_itar"], call["extra"]["dsip_cmmc"], call["extra"]["dsip_keywords"]) == (
        True, "Level 2 (Self)", "autonomy; test harness; edge")
    assert call["extra"]["dsip_open"] == "2026-10-28" and call["extra"]["dsip_closed"] is False
    assert not list((folder / "inbox").iterdir())
    assert [p.name for p in (folder / "imported").iterdir()] == ["topic_DAF27BZ01-DV901_Edge autonomy test harness.DOCX"]


def test_a_docx_with_no_matching_cycle_has_no_close_date_and_an_unreadable_file_is_set_aside(ledger_db: str, tmp_path: Path) -> None:
    run_id = lq.start_run("DSIP", component="dsip")
    folder = tmp_path / "dsip"
    write_topic_docx(folder / "inbox" / "topic_DON27BZ03-NV950_Later release.DOCX", "DON27BZ03-NV950: Later release", itar=False)
    write_topic_docx(folder / "inbox" / "notes.docx", "Meeting notes, not a topic")
    counts = inbox.import_inbox(run_id, folder=folder, now=NOW)
    assert counts == {"found": 2, "scraped": 1, "new": 1, "failed": 1}
    call = stored("dsip-don27bz03-nv950")
    assert call["due_date"] == "" and call["extra"]["dsip_itar"] is False
    assert "Its close date is on DSIP" in call["description"]
    assert [p.name for p in (folder / "unreadable").iterdir()] == ["notes.docx"]


def test_a_file_whose_path_runs_past_260_characters_is_still_read_and_moved(ledger_db: str, tmp_path: Path) -> None:
    """DSIP names a file after its topic's title (up to 225 characters); on 10 Nov 2026 five such files would not open."""
    folder = tmp_path / ("deep" * 12) / "dsip"
    name = "topic_DAF27BZ02-DV023_" + "A unified model for specification and simulation " * 4 + "of a data system.DOCX"
    write_topic_docx(folder / "inbox" / name, "DAF27BZ02-DV023: A unified model for specification and simulation")
    assert len(str(folder / "inbox" / name)) > 260
    counts = inbox.import_inbox(lq.start_run("DSIP", component="dsip"), folder=folder, now=NOW)
    assert counts == {"found": 1, "scraped": 1, "new": 1, "failed": 0}
    assert inbox.docx_names(folder / "imported") == [name]


def test_a_dry_run_reads_the_inbox_but_leaves_the_files_where_they_are(ledger_db: str, tmp_path: Path,
                                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(inbox, "in_dry_run", lambda: True)
    folder = tmp_path / "dsip"
    write_topic_docx(folder / "inbox" / "topic_DAF27BZ01-DV901_Edge.DOCX", "DAF27BZ01-DV901: Edge autonomy test harness")
    assert inbox.import_inbox(lq.start_run("DSIP", component="dsip"), folder=folder, now=NOW)["scraped"] == 1
    assert [p.name for p in (folder / "inbox").iterdir()] == ["topic_DAF27BZ01-DV901_Edge.DOCX"]


def test_the_scan_reads_the_inbox_before_sbirgov_so_sbirgovs_copy_wins(ledger_db: str, tmp_path: Path) -> None:
    run_id = lq.start_run("DSIP", component="dsip")
    folder = tmp_path / "dsip"
    write_topic_docx(folder / "inbox" / "topic_DON27BZ02-NV901_Agentic.DOCX", "DON27BZ02-NV901: Agentic maintenance associate for ship crews")
    counts = scrape.fetch_all(run_id, now=NOW, opener=Site([[13001]], {13001: MAINTAINER}), delay=0, folder=folder)
    assert counts == {"found": 2, "scraped": 2, "new": 1, "failed": 0}
    assert stored("dsip-don27bz02-nv901")["extra"]["dsip_source"] == "SBIR.gov"


# ------------------------------------------------------------------ the watch: an open cycle with no topics

def test_the_watch_names_each_open_cycle_with_no_topics(ledger_db: str) -> None:
    run_id = lq.start_run("AFWERX", component="afwerx")
    release_1_cycle(run_id)
    lq.upsert_call({"id": "afwerx-daf-sbir-specific-topic-27-bz-release-2", "portal": "AFWERX",
                    "title": "DAF SBIR Specific Topic 27.BZ \N{EN DASH} Release 2", "type": "SBIR cycle", "due_date": "2027-01-05",
                    "extra": {"afwerx_pre_release": "2026-11-04", "afwerx_open": "2026-12-02", "afwerx_closed": False}}, run_id)
    lq.upsert_call({"id": "spacewerx-sttr-27-tz-release-3", "portal": "SpaceWERX", "title": "STTR 27.TZ Release 3",
                    "type": "STTR cycle", "due_date": "2027-02-03",
                    "extra": {"spacewerx_pre_release": "2026-12-02", "spacewerx_closed": False}}, run_id)   # not released yet
    lq.upsert_call({"id": "afwerx-sbir-26-bz-release-9", "portal": "AFWERX", "title": "SBIR 26.BZ Release 9",
                    "type": "SBIR cycle", "due_date": "2026-09-01",
                    "extra": {"afwerx_pre_release": "2026-07-01", "afwerx_closed": True}}, run_id)   # closed
    lq.upsert_call({"id": "spacewerx-py26-2-tacfi", "portal": "SpaceWERX", "title": "PY26.2 TACFI Notice of Opportunity",
                    "type": "TACFI", "due_date": "", "extra": {"spacewerx_closed": False}}, run_id)   # not a cycle
    lq.upsert_call({"id": "dsip-daf27bz02-dv903", "portal": "DSIP", "title": "DAF27BZ02-DV903 Edge autonomy",
                    "extra": {"dsip_topic": "DAF27BZ02-DV903"}}, run_id)
    messages = watch.missed_releases(run_id, now=NOW)
    assert len(messages) == 1
    assert "DOW SBIR SPECIFIC TOPIC 27.BZ & 27.BX Release 1" in messages[0]
    assert str(Path("data") / "dsip" / "inbox") in messages[0]
    assert "Download Topic Details" in messages[0]


def test_a_topic_added_by_hand_counts_for_its_cycle(ledger_db: str) -> None:
    run_id = lq.start_run("AFWERX", component="afwerx")
    release_1_cycle(run_id)
    lq.upsert_call({"id": "dsip-don27bx01-np001", "portal": "DSIP", "title": "DON27BX01-NP001 A topic", "extra": {}}, run_id)
    assert watch.missed_releases(run_id, now=NOW) == []   # the topic's id says 27.BX Release 1


# ------------------------------------------------------------------ the portal

def test_dsip_is_discovered_without_a_browser_and_with_a_watch() -> None:
    portal = registry.get("dsip")
    assert (portal.name, portal.needs_browser) == ("DSIP", False)
    assert portal.watch is not None and portal.keywords == KEYWORDS_PATH
    assert "DSIP" in portal.how_to_submit
