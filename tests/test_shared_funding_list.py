"""The Open Funding Opportunities list that AFWERX's and SpaceWERX's Get Funded pages share (PRO-536, PRO-538)."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from portals.shared import funding_list as fl
from tests.funding_pages import (AFWERX_CYCLES, AFWERX_PAGE, DSIP_LOGIN, SPACEWERX_PAGE, TACFI, TACFI_LINK, FakeSite,
                                 grid_row, labelled, page)

NOW = datetime(2026, 10, 23, 12, 0, tzinfo=timezone.utc)
SITE = fl.Site(portal="AFWERX", prefix="afwerx", page_url="https://afwerx.com/get-funded/",
               department="Department of the Air Force")


# ------------------------------------------------------------------------------ the page

def test_listings_are_read_from_the_labelled_blocks() -> None:
    assert fl.solicitations(AFWERX_PAGE) == [
        {"title": "DOW SBIR SPECIFIC TOPIC 27.BZ & 27.BX Release 1", "branches": ["Air Force"],
         "pre_release": "7 Oct 26", "open": "28 Oct 26", "close": "25 Nov 26", "link": DSIP_LOGIN},
        {"title": "DOW STTR SPECIFIC TOPIC 27.TZ Release 1", "branches": ["Air Force", "Space Force"],
         "pre_release": "7 Oct 26", "open": "28 Oct 26", "close": "25 Nov 26", "link": DSIP_LOGIN},
        {"title": "DOD SBIR SPECIFIC TOPIC 26.BZ Release 2", "branches": ["Space Force"],
         "pre_release": "N/A", "open": "13 APRIL 26", "close": "13 MAY 26", "link": DSIP_LOGIN},
        {"title": "STRATFI/TACFI 27.1", "branches": ["Air Force", "Space Force"],
         "pre_release": "TBD", "open": "TBD", "close": "TBD", "link": DSIP_LOGIN},
    ]
    assert fl.solicitations(SPACEWERX_PAGE) == [
        {"title": "PY26.2 TACFI Notice of Opportunity", "branches": [], "pre_release": "N/A", "open": "5 JUN 26",
         "close": "Accepting Submissions on a Continuous Basis", "link": TACFI_LINK}]


def test_a_listing_shown_twice_is_read_once_and_a_missing_date_is_empty() -> None:
    first = AFWERX_CYCLES[0]
    no_pre_release = ('<div class="brxe-m1 brxe-block"><a href="#"><strong>SOLICITATION</strong>: DOW SBIR OPEN TOPIC 27.1</a>'
                      '<p><strong>OPEN</strong>: 1 Dec 26<br /><strong>CLOSE</strong>: 5 Jan 27</p></div>')
    found = fl.solicitations(page(labelled(*first) + labelled(*first) + no_pre_release))
    assert [s["title"] for s in found] == ["DOW SBIR SPECIFIC TOPIC 27.BZ & 27.BX Release 1", "DOW SBIR OPEN TOPIC 27.1"]
    assert found[1] == {"title": "DOW SBIR OPEN TOPIC 27.1", "branches": [], "pre_release": "",
                        "open": "1 Dec 26", "close": "5 Jan 27", "link": "#"}


def test_an_empty_list_has_no_listings() -> None:
    assert fl.solicitations(page("")) == []   # the date below the list is not part of it


def test_a_page_without_the_list_or_with_a_list_that_cannot_be_read_is_an_error() -> None:
    with pytest.raises(fl.FundingListError, match="Open Funding Opportunities"):
        fl.solicitations("<html><body>Maintenance</body></html>")
    with_badges = page("".join(grid_row(*c) for c in AFWERX_CYCLES))
    dates_only = page(grid_row(*TACFI), site="SpaceWERX")   # SpaceWERX shows no badges
    for grid_only in (with_badges, dates_only):
        with pytest.raises(fl.FundingListError, match="could not read"):
            fl.solicitations(grid_only)


def test_the_page_is_fetched_with_one_retry() -> None:
    site = FakeSite(failures=1)
    assert "Open Funding Opportunities" in fl.fetch_page(SITE, site)
    assert site.requests == [SITE.page_url] * 2
    with pytest.raises(fl.FundingListError, match="AFWERX did not answer"):
        fl.fetch_page(SITE, FakeSite(failures=2))


# ------------------------------------------------------------------------------ records

def test_dates_as_the_pages_write_them() -> None:
    assert fl.parse_date("7 Oct 26") == date(2026, 10, 7)
    assert fl.parse_date("13 APRIL 26") == date(2026, 4, 13)
    assert fl.parse_date(" 6  Sept. 2027 ") == date(2027, 9, 6)
    for text in ("N/A", "TBD", "", "31 Feb 26", "7 Oc 26", "Oct 7 26", "Accepting Submissions on a Continuous Basis"):
        assert fl.parse_date(text) is None, text


def test_types_from_the_title() -> None:
    titles = ("DOW SBIR SPECIFIC TOPIC 27.BZ", "DOW STTR SPECIFIC TOPIC 27.TZ", "SBIR/STTR OPEN TOPIC",
              "PY26.2 TACFI Notice of Opportunity", "SPACEWERX STRATFI PY27.1", "STRATFI/TACFI 27.1", "DAF CSO 27.1")
    assert [fl.derive_type(t) for t in titles] == [
        "SBIR cycle", "STTR cycle", "SBIR/STTR cycle", "TACFI", "STRATFI", "STRATFI/TACFI", "Solicitation"]


def test_the_dates_in_words() -> None:
    assert fl.dates_sentence({"pre_release": "7 Oct 26", "open": "28 Oct 26", "close": "25 Nov 26"}) == (
        "Pre-release 7 Oct 2026, opens 28 Oct 2026, closes 25 Nov 2026.")
    assert fl.dates_sentence({"pre_release": "N/A", "open": "5 JUN 26", "close": "Accepting Submissions on a Continuous Basis"}) == (
        "Pre-release N/A, opens 5 Jun 2026, takes submissions on a continuous basis.")
    assert fl.dates_sentence({"pre_release": "", "open": "", "close": "11/25/26"}) == "Closes 11/25/26."
    assert fl.dates_sentence({"pre_release": "", "open": "", "close": ""}) == ""


def test_the_calls_link() -> None:
    assert fl.call_url(DSIP_LOGIN, SITE) == fl.TOPICS_URL   # DSIP's sign-in page: its topic search instead
    assert fl.call_url(TACFI_LINK, SITE) == TACFI_LINK
    assert fl.call_url("/accelerate/stratfi-tacfi/", SITE) == "https://afwerx.com/accelerate/stratfi-tacfi/"
    assert fl.call_url("", SITE) == fl.call_url("#", SITE) == SITE.page_url


def test_a_listing_closes_after_its_close_day_in_eastern_time() -> None:
    listing = fl.solicitations(AFWERX_PAGE)[0]
    late_on_the_day = datetime(2026, 11, 26, 4, 30, tzinfo=timezone.utc)    # 25 Nov, 23:30 Eastern
    next_day = datetime(2026, 11, 26, 5, 30, tzinfo=timezone.utc)           # 26 Nov, 00:30 Eastern
    assert fl.build_record(listing, late_on_the_day, SITE)["extra"]["afwerx_closed"] is False
    assert fl.build_record(listing, next_day, SITE)["extra"]["afwerx_closed"] is True


def test_no_deadline_by_design_and_a_close_date_that_cannot_be_read() -> None:
    listing = fl.solicitations(AFWERX_PAGE)[0]
    unreadable = fl.build_record({**listing, "close": "11/25/26"}, NOW, SITE)
    assert unreadable["due_date"] == "" and unreadable["extra"]["afwerx_no_deadline"] is False   # the quality alert counts it
    assert "closes 11/25/26." in unreadable["description"]
    for text in ("TBD", "N/A", "Accepting Submissions on a Continuous Basis"):
        assert fl.build_record({**listing, "close": text}, NOW, SITE)["extra"]["afwerx_no_deadline"] is True, text
