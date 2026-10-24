"""APFIT: the cycle-status posts on the APFIT page (PRO-547).

The page below is made up but shaped like ac.cto.mil/apfit/: a Beaver Builder post grid whose
posts carry schema.org dates, a title link and a one-line status.
"""
from __future__ import annotations

import json
import urllib.error
from datetime import datetime, timezone
from typing import Any

import pytest

from ledger import queries as lq
from portals import registry
from portals.apfit import api, records, scrape

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)


def post(number: int, slug: str, title: str, published: str, modified: str, status: str) -> str:
    return (f'<div class="fl-post-grid-post fl-post-align-left post-{number} post type-post status-publish hentry '
            f'category-apfit" itemscope itemtype="https://schema.org/BlogPosting"><meta itemscope itemprop="mainEntityOfPage" '
            f'itemtype="https://schema.org/WebPage" itemid="https://ac.cto.mil/{slug}/" content="{title}" />'
            f'<meta itemprop="datePublished" content="{published}" /><meta itemprop="dateModified" content="{modified}" />'
            f'<div class="fl-post-grid-text"><h3 class="fl-post-grid-title" itemprop="headline"> <a href="https://ac.cto.mil/'
            f'{slug}/" title="{title}">{title}</a> </h3><div class="fl-post-grid-meta"><span class="fl-post-grid-date"> '
            f'Nov 2, 2026 </span></div><div class="fl-post-grid-content"><p>{status}</p></div></div></div>')


OPEN = post(4801, "fy27-2-cycle-status", "FY27-2 Cycle Status", "2026-11-02", "2026-11-02",
            "The FY27-2 APFIT cycle is open. Government sponsors submit through their service APFIT representative by "
            "January 15, 2027.")
FINAL = post(4721, "fy27-1-cycle-status", "FY27-1 Cycle Status", "2026-10-20", "2026-10-20",
             "The FY27-1 APFIT selection cycle is in final selection. See the Frequently Asked Questions for more "
             "information about the selection process and cycle schedule.")
AWARDED = post(4565, "fy26-2-cycle-status", "FY26-2 Cycle Status", "2025-12-03", "2026-10-20",
               "Awards have been announced. See the Department of War announcement for details.")


def page(*posts: str) -> str:
    return ('<html><head><style>.fl-post-grid-post {visibility: hidden;}</style></head><body><h1>APFIT</h1>'
            '<p>Funding amounts of $10M-$50M are awarded to projects with small business or non-traditional performers.</p>'
            '<div class="fl-module fl-module-post-grid" aria-label="Posts"><div class="fl-post-grid" itemscope="itemscope" '
            f'itemtype="https://schema.org/Blog">{"".join(posts)}</div></div><h2>APFIT Submission Totals by Fiscal Year</h2>'
            '</body></html>')


PAGE = page(OPEN, FINAL, AWARDED)


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


# ------------------------------------------------------------------------------ the page

def test_each_cycle_post_is_read_with_its_dates_link_and_status() -> None:
    posts = api.cycle_posts(PAGE)
    assert [p["title"] for p in posts] == ["FY27-2 Cycle Status", "FY27-1 Cycle Status", "FY26-2 Cycle Status"]
    assert posts[0] == {"post_id": "4801", "title": "FY27-2 Cycle Status", "link": "https://ac.cto.mil/fy27-2-cycle-status/",
                        "published": "2026-11-02", "modified": "2026-11-02",
                        "status": ("The FY27-2 APFIT cycle is open. Government sponsors submit through their service "
                                   "APFIT representative by January 15, 2027.")}


def test_an_empty_grid_has_no_cycles_and_a_page_without_it_is_an_error() -> None:
    assert api.cycle_posts(page()) == []
    with pytest.raises(api.ApfitError, match="post grid"):
        api.cycle_posts("<html><body>Maintenance</body></html>")


def test_the_page_is_fetched_with_one_retry() -> None:
    site = FakeSite(failures=1)
    assert "fl-post-grid" in api.fetch_page(site) and site.requests == [api.PAGE_URL] * 2
    with pytest.raises(api.ApfitError, match="did not answer"):
        api.fetch_page(FakeSite(failures=2))


# ------------------------------------------------------------------------------ records

def test_an_open_cycle_becomes_a_calls_row() -> None:
    assert records.build_record(api.cycle_posts(PAGE)[0], NOW) == {
        "id": "apfit-fy27-2",
        "portal": "APFIT",
        "title": "APFIT FY27-2 cycle",
        "type": "APFIT cycle",
        "department": "OUSW(R&E)",
        "naics_code": "",
        "set_aside": "",
        "posted_date": "2026-11-02",
        "due_date": "",
        "description": ("APFIT (Accelerate the Procurement and Fielding of Innovative Technologies) awards $10M to $50M "
                        "to projects with small business or nontraditional performers to speed initial production. "
                        "Proposals come from government sponsors through an approved service APFIT representative, "
                        "and each participating organization sets its own deadlines.\n\n"
                        "FY27-2 status on 2 Nov 2026: The FY27-2 APFIT cycle is open. Government sponsors submit "
                        "through their service APFIT representative by January 15, 2027."),
        "url": "https://ac.cto.mil/fy27-2-cycle-status/",
        "source_type": "scrape",
        "extra": {"apfit_cycle": "FY27-2", "apfit_post_id": "4801",
                  "apfit_status": ("The FY27-2 APFIT cycle is open. Government sponsors submit through their service "
                                   "APFIT representative by January 15, 2027."),
                  "apfit_no_deadline": True, "apfit_closed": False},
    }


def test_final_selection_evaluation_and_awards_close_a_cycle() -> None:
    final, awarded = (records.build_record(p, NOW) for p in api.cycle_posts(PAGE)[1:])
    assert (final["id"], final["extra"]["apfit_closed"]) == ("apfit-fy27-1", True)
    assert (awarded["id"], awarded["extra"]["apfit_closed"]) == ("apfit-fy26-2", True)
    assert awarded["description"].endswith("FY26-2 status on 20 Oct 2026: Awards have been announced. See the "
                                           "Department of War announcement for details.")
    for status in ("Proposals are under evaluation.", "The cycle has closed.", "Projects were awarded in May."):
        assert records.is_closed(status) is True, status
    assert records.is_closed("The FY28-1 APFIT cycle is anticipated to open in March.") is False
    other = records.build_record({**api.cycle_posts(PAGE)[0], "title": "APFIT Industry Day"}, NOW)
    assert (other["id"], other["title"]) == ("apfit-post-4801", "APFIT Industry Day")


# ------------------------------------------------------------------------------ a run

def test_fetch_all_stores_the_open_cycle(ledger_db: str) -> None:
    counts = scrape.fetch_all(lq.start_run("APFIT", component="apfit"), now=NOW, opener=FakeSite())
    assert {row["id"] for row in lq.calls_where(portal="APFIT")} == {"apfit-fy27-2"}
    assert counts == {"found": 3, "scraped": 1, "new": 1, "failed": 0}


def test_a_stored_cycle_that_moves_to_selection_is_refreshed_as_closed(ledger_db: str) -> None:
    scrape.fetch_all(lq.start_run("APFIT", component="apfit"), now=NOW, opener=FakeSite())
    in_selection = OPEN.replace("is open. Government sponsors submit through their service APFIT representative by "
                                "January 15, 2027.", "is in final selection.")
    counts = scrape.fetch_all(lq.start_run("APFIT", component="apfit"), now=NOW,
                              opener=FakeSite(page(in_selection, FINAL, AWARDED)))
    assert counts == {"found": 3, "scraped": 1, "new": 0, "failed": 0}
    assert json.loads(lq.get_call("apfit-fy27-2")["extra"])["apfit_closed"] is True   # type: ignore[index]


def test_every_apfit_cycle_reaches_the_judges(ledger_db: str) -> None:
    scrape.fetch_all(lq.start_run("APFIT", component="apfit"), now=NOW, opener=FakeSite())
    kept, rejected = registry.get("apfit").filter(lq.calls_where(portal="APFIT"))
    assert [d.id for d in kept] == ["apfit-fy27-2"] and rejected == []


def test_the_registry_finds_apfit() -> None:
    found = registry.get("apfit")
    assert found.name == "APFIT" and not found.needs_browser and found.fetch_timeout == 120
    assert found.keywords and found.keywords.exists() and found.notes and found.notes.exists()
    assert "government sponsor" in found.how_to_submit
