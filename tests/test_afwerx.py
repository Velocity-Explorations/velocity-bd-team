"""AFWERX: the SBIR and STTR cycles listed on its Get Funded page (PRO-536).

The page below is made up but shaped like AFWERX's: each cycle appears twice, as a grid row
(badges, title, three dates) and as a labelled block for small screens.
"""
from __future__ import annotations

import json
import urllib.error
from datetime import date, datetime, timezone
from typing import Any

import pytest

from ledger import queries as lq
from portals import registry
from portals.afwerx import api, records, scrape

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
DSIP_LOGIN = "https://www.dodsbirsttr.mil/submissions/login"


def badge_divs(badges: list[str]) -> str:
    return "".join(f'<div class="brxe-b1 brxe-block"><div class="brxe-b2 brxe-text-basic '
                   f'afw-v2-funding-opps__icon-text">{badge}</div></div>' for badge in badges)


def grid_row(badges: list[str], title: str, pre: str, opens: str, closes: str) -> str:
    cells = "".join(f'<div class="brxe-d1 brxe-block"><div class="brxe-d2 brxe-text-basic">{d}</div></div>'
                    for d in (pre, opens, closes))
    return (f'<div class="brxe-r1 brxe-block" data-brx-loop-start="r1">{badge_divs(badges)}'
            f'<div class="brxe-t1 brxe-block"><a class="brxe-t2 brxe-text-basic" href="{DSIP_LOGIN}">{title}</a></div>'
            f'{cells}</div><div class="brx-query-trail" data-query-element-id="r1"></div>')


def labelled(badges: list[str], title: str, pre: str, opens: str, closes: str) -> str:
    return (f'<div class="brxe-m1 brxe-block" data-brx-loop-start="m1">{badge_divs(badges)}'
            f'<div class="brxe-m2 brxe-block"><a class="brxe-m3 brxe-text-basic" href="{DSIP_LOGIN}">'
            f'<strong>SOLICITATION</strong>: {title}</a><div class="brxe-m4 brxe-text">'
            f'<p><strong>PRE-RELEASE</strong>: {pre}<br /><strong>OPEN</strong>: {opens}<br />'
            f'<strong>CLOSE</strong>: {closes}</p> </div></div></div>'
            '<div class="brx-query-trail" data-query-element-id="m1"></div>')


CYCLES = [
    (["AF"], "DOW SBIR SPECIFIC TOPIC 27.BZ &#038; 27.BX Release 1", "7 Oct 26", "28 Oct 26", "25 Nov 26"),
    (["AF", "SF"], "DOW  STTR SPECIFIC TOPIC 27.TZ Release 1", "7 Oct 26", "28 Oct 26", "25 Nov 26"),
    (["SF"], "DOD SBIR SPECIFIC TOPIC 26.BZ Release 2", "N/A", "13 APRIL 26", "13 MAY 26"),
    (["AF / SF"], "STRATFI/TACFI 27.1", "TBD", "TBD", "TBD"),
]
TOP = ('<html><head><style>.afw-v2-funding-opps__icon-text {color: #fff}</style></head><body>'
       '<h2 class="brxe-heading">Who can apply</h2><p>500 or fewer employees</p>'
       '<h2 class="brxe-heading">Open Funding Opportunities</h2>'
       '<div class="brxe-text"><p>Discover how your small business can partner with AFWERX.</p></div>'
       '<div class="brxe-block brx-grid"><div class="brxe-text-basic">Upcoming<br>Solicitations</div>'
       '<div class="brxe-text-basic">Pre-Release</div><div class="brxe-text-basic">Open</div>'
       '<div class="brxe-text-basic">Close</div></div>')
END = ('<script>\nSOLICITATION : DOW SBIR SPECIFIC TOPIC 99.ZZ\n</script>'   # never read as a cycle
       '<div class="brxe-block"><div class="brxe-text"><p>Dates subject to change</p>'
       '<p><strong>AF</strong> &#8211; Solicitation includes U.S. Air Force topics<br />'
       '<strong>SF</strong> &#8211; Solicitation includes U.S. Space Force topics</p></div>'
       '<a class="brxe-button" href="https://www.dodsbirsttr.mil/submissions/solicitation-documents/active-solicitations">'
       'View All DoW Active Solicitations</a></div>'
       '<h2>Funding Avenues by Phase of Development</h2><p><strong>KEY DETAILS</strong>: Up to six months</p>'
       '</body></html>')
PAGE = TOP + "".join(grid_row(*c) + labelled(*c) for c in CYCLES) + END

FIRST_ID = "afwerx-dow-sbir-specific-topic-27-bz-27-bx-release-1"
SECOND_ID = "afwerx-dow-sttr-specific-topic-27-tz-release-1"
CLOSED_ID = "afwerx-dod-sbir-specific-topic-26-bz-release-2"
STRATFI_ID = "afwerx-stratfi-tacfi-27-1"


class Reply:
    def __init__(self, body: str) -> None:
        self.body = body.encode("utf-8")

    def __enter__(self) -> "Reply":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def read(self) -> bytes:
        return self.body


class FakeAfwerx:
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


def built(now: datetime = NOW) -> list[dict[str, Any]]:
    return [records.build_record(c, now) for c in api.cycles(PAGE)]


# ------------------------------------------------------------------------------ the page

def test_cycles_are_read_from_the_labelled_blocks() -> None:
    assert api.cycles(PAGE) == [
        {"title": "DOW SBIR SPECIFIC TOPIC 27.BZ & 27.BX Release 1", "branches": ["Air Force"],
         "pre_release": "7 Oct 26", "open": "28 Oct 26", "close": "25 Nov 26"},
        {"title": "DOW STTR SPECIFIC TOPIC 27.TZ Release 1", "branches": ["Air Force", "Space Force"],
         "pre_release": "7 Oct 26", "open": "28 Oct 26", "close": "25 Nov 26"},
        {"title": "DOD SBIR SPECIFIC TOPIC 26.BZ Release 2", "branches": ["Space Force"],
         "pre_release": "N/A", "open": "13 APRIL 26", "close": "13 MAY 26"},
        {"title": "STRATFI/TACFI 27.1", "branches": ["Air Force", "Space Force"],
         "pre_release": "TBD", "open": "TBD", "close": "TBD"},
    ]


def test_a_cycle_listed_twice_is_read_once_and_a_missing_date_is_empty() -> None:
    first = CYCLES[0]
    no_pre_release = ('<div class="brxe-m1 brxe-block"><a href="#"><strong>SOLICITATION</strong>: DOW SBIR OPEN TOPIC 27.1</a>'
                      '<p><strong>OPEN</strong>: 1 Dec 26<br /><strong>CLOSE</strong>: 5 Jan 27</p></div>')
    page = TOP + labelled(*first) + labelled(*first) + no_pre_release + END
    found = api.cycles(page)
    assert [c["title"] for c in found] == ["DOW SBIR SPECIFIC TOPIC 27.BZ & 27.BX Release 1", "DOW SBIR OPEN TOPIC 27.1"]
    assert found[1] == {"title": "DOW SBIR OPEN TOPIC 27.1", "branches": [], "pre_release": "",
                        "open": "1 Dec 26", "close": "5 Jan 27"}


def test_an_empty_list_has_no_cycles() -> None:
    assert api.cycles(TOP + END) == []


def test_a_page_without_the_list_or_with_a_list_that_cannot_be_read_is_an_error() -> None:
    with pytest.raises(api.AfwerxError, match="Open Funding Opportunities"):
        api.cycles("<html><body>Maintenance</body></html>")
    grid_only = TOP + "".join(grid_row(*c) for c in CYCLES) + END
    with pytest.raises(api.AfwerxError, match="could not read"):
        api.cycles(grid_only)


def test_the_page_is_fetched_with_one_retry() -> None:
    site = FakeAfwerx(failures=1)
    assert "Open Funding Opportunities" in api.fetch_page(site)
    assert site.requests == [api.GET_FUNDED_URL] * 2
    with pytest.raises(api.AfwerxError, match="did not answer"):
        api.fetch_page(FakeAfwerx(failures=2))


# ------------------------------------------------------------------------------ records

def test_dates_as_afwerx_writes_them() -> None:
    assert records.parse_date("7 Oct 26") == date(2026, 10, 7)
    assert records.parse_date("13 APRIL 26") == date(2026, 4, 13)
    assert records.parse_date(" 6  Sept. 2027 ") == date(2027, 9, 6)
    for text in ("N/A", "TBD", "", "31 Feb 26", "7 Oc 26", "Oct 7 26"):
        assert records.parse_date(text) is None, text


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
                        "Department's portal for these solicitations, which the scanner does not read: the "
                        "call's link opens DSIP's topic search."),
        "url": "https://www.dodsbirsttr.mil/topics-app/",
        "source_type": "scrape",
        "extra": {"afwerx_branches": ["Air Force"], "afwerx_pre_release": "2026-10-07",
                  "afwerx_open": "2026-10-28", "afwerx_no_deadline": False, "afwerx_closed": False},
    }


def test_types_dates_and_the_closed_flag() -> None:
    sbir, sttr, closed, stratfi = built()
    assert [r["id"] for r in (sbir, sttr, closed, stratfi)] == [FIRST_ID, SECOND_ID, CLOSED_ID, STRATFI_ID]
    assert [r["type"] for r in (sbir, sttr, closed, stratfi)] == ["SBIR cycle", "STTR cycle", "SBIR cycle", "Solicitation"]
    assert sttr["description"].startswith("An STTR solicitation cycle listed on AFWERX's Get Funded page, "
                                          "with U.S. Air Force and Space Force topics. ")
    assert (closed["posted_date"], closed["due_date"]) == ("2026-04-13", "2026-05-13")   # no pre-release: the open date
    assert "Pre-release N/A, opens 13 Apr 2026, closes 13 May 2026." in closed["description"]
    assert closed["extra"]["afwerx_closed"] is True and closed["extra"]["afwerx_pre_release"] is None
    assert (stratfi["posted_date"], stratfi["due_date"]) == ("", "")
    assert stratfi["description"].startswith("A solicitation listed on AFWERX's Get Funded page, with U.S. Air Force "
                                             "and Space Force topics. Pre-release TBD, opens TBD, closes TBD. ")
    assert stratfi["extra"]["afwerx_no_deadline"] is True and stratfi["extra"]["afwerx_closed"] is False


def test_a_cycle_closes_after_its_close_day_in_eastern_time() -> None:
    cycle = api.cycles(PAGE)[0]
    late_on_the_day = datetime(2026, 11, 26, 4, 30, tzinfo=timezone.utc)    # 25 Nov, 23:30 Eastern
    next_day = datetime(2026, 11, 26, 5, 30, tzinfo=timezone.utc)           # 26 Nov, 00:30 Eastern
    assert records.build_record(cycle, late_on_the_day)["extra"]["afwerx_closed"] is False
    assert records.build_record(cycle, next_day)["extra"]["afwerx_closed"] is True


def test_a_close_date_that_cannot_be_read_is_not_marked_as_having_no_deadline() -> None:
    cycle = {**api.cycles(PAGE)[0], "close": "11/25/26"}
    rec = records.build_record(cycle, NOW)
    assert rec["due_date"] == "" and rec["extra"]["afwerx_no_deadline"] is False   # the quality alert counts it
    assert "closes 11/25/26." in rec["description"]


# ------------------------------------------------------------------------------ a run

def test_fetch_all_stores_the_open_cycles(ledger_db: str) -> None:
    counts = scrape.fetch_all(lq.start_run("AFWERX", component="afwerx"), now=NOW, opener=FakeAfwerx())
    assert {row["id"] for row in lq.calls_where(portal="AFWERX")} == {FIRST_ID, SECOND_ID, STRATFI_ID}
    assert counts == {"found": 4, "scraped": 3, "new": 3, "failed": 0}


def test_a_stored_cycle_that_closes_is_refreshed_as_closed(ledger_db: str) -> None:
    scrape.fetch_all(lq.start_run("AFWERX", component="afwerx"), now=NOW, opener=FakeAfwerx())
    later = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
    counts = scrape.fetch_all(lq.start_run("AFWERX", component="afwerx"), now=later, opener=FakeAfwerx())
    assert counts == {"found": 4, "scraped": 3, "new": 0, "failed": 0}
    assert json.loads(lq.get_call(FIRST_ID)["extra"])["afwerx_closed"] is True   # type: ignore[index]


def test_fetch_all_honours_the_limit(ledger_db: str) -> None:
    counts = scrape.fetch_all(lq.start_run("AFWERX", component="afwerx"), limit=1, now=NOW, opener=FakeAfwerx())
    assert counts["scraped"] == 1 and len(lq.calls_where(portal="AFWERX")) == 1


def test_the_keyword_filter_keeps_the_sbir_and_sttr_cycles(ledger_db: str) -> None:
    scrape.fetch_all(lq.start_run("AFWERX", component="afwerx"), now=NOW, opener=FakeAfwerx())
    kept, rejected = registry.get("afwerx").filter(lq.calls_where(portal="AFWERX"))
    assert {d.id for d in kept} == {FIRST_ID, SECOND_ID}
    assert [(d.id, d.reason) for d in rejected] == [(STRATFI_ID, "no keyword match")]


def test_the_registry_finds_afwerx() -> None:
    found = registry.get("afwerx")
    assert found.name == "AFWERX" and not found.needs_browser and found.fetch_timeout == 120
    assert found.keywords and found.keywords.exists() and found.notes and found.notes.exists()
    assert "DSIP" in found.how_to_submit
