"""DOE SBIR: the solicitations on DOE's SBIR/STTR Application Hub, read from its WordPress API (PRO-543).

The items below are made up but shaped like the hub's: an Avada portfolio item whose classes
carry its Active, Upcoming or Closed category, and whose text starts with the title, the
category, the submission deadline and a contact line, then Information and Topics.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from typing import Any

import pytest

from ledger import queries as lq
from portals import registry
from portals.doe_sbir import api, records, scrape

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)


def item(post_id: int, title: str, status: str, deadline_line: str, body: str, excerpt: str = "",
         date: str = "2026-10-20T10:00:00") -> dict[str, Any]:
    content = (
        f'<div class="fusion-fullwidth"><div class="fusion-title"><h2>{title}</h2></div>'
        f'<div class="fusion-text"><p>{status} Solicitation</p></div>'
        f'<div class="fusion-text"><p><strong>{deadline_line}</strong></p></div>'
        '<p>Questions? Reach out to us at <a href="mailto:sbir-sttr@example.org">sbir-sttr@example.org</a></p>'
        f'<h3>Information</h3>{body}'
        '<h3>Process Details</h3><p>All applicants submit a Pitch application first.</p>'
        '<table><tr><th>File Title</th><th>Resource(s)</th><th>File Type</th></tr>'
        '<tr><td>Pitch Guide</td><td>Download</td><td>DOCX</td></tr></table></div>'
    )
    return {
        "id": post_id, "date": date, "modified": "2026-10-21T12:00:00",
        "link": f"https://sbir-sttr.connectwerx.org/portfolio-items/{post_id}/",
        "title": {"rendered": title}, "content": {"rendered": content}, "excerpt": {"rendered": f"<p>{excerpt}</p>"},
        "class_list": [f"post-{post_id}", "avada_portfolio", "type-avada_portfolio", "status-publish", "hentry",
                       f"portfolio_category-{status.lower()}-solicitation"],
    }


ACTIVE = item(1201, "FY27 Phase I Release 1", "Active", "Submission Deadline: December 3, 2026 at 5 PM ET",
              "<p>DOE intends to make approximately 120 SBIR/STTR Phase I awards across advanced manufacturing, "
              "critical minerals &amp; AI.</p><h3>Topics</h3><p>1. AI for Grid Operations</p>"
              "<p>This topic seeks machine learning software for grid control rooms.</p>"
              "<p>2. Advanced Manufacturing</p><p>This topic seeks additive manufacturing processes.</p>",
              excerpt="Submission Deadline: 12/03/2026")
UPCOMING = item(1202, "FY27 Phase II", "Upcoming", "Submission Deadline: TBD",
                "<p>Open to DOE Phase I awardees from FY 2025 releases.</p>")
CLOSED = item(903, "FY26 Phase I Genesis Mission", "Closed", "Submission Deadline: September 10, 2026 at 2 PM ET",
              "<p>Approximately 40 SBIR/STTR awards across four AI topic areas.</p>", date="2026-07-08T14:38:55")
ITEMS = [ACTIVE, UPCOMING, CLOSED]


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


class FakeHub:
    """Serves the portfolio items, paged the way WordPress pages them; can fail first."""

    def __init__(self, items: list[dict[str, Any]] | None = None, failures: int = 0) -> None:
        self.items = items if items is not None else ITEMS
        self.failures = failures
        self.requests: list[dict[str, str]] = []

    def __call__(self, request: Any, timeout: float) -> Reply:
        assert timeout >= 10
        parts = urllib.parse.urlsplit(request.full_url)
        assert parts.path == "/wp-json/wp/v2/avada_portfolio"
        params = dict(urllib.parse.parse_qsl(parts.query))
        self.requests.append(params)
        if len(self.requests) <= self.failures:
            raise urllib.error.URLError("timed out")
        size, page = int(params["per_page"]), int(params.get("page", "1"))
        pages = max(1, -(-len(self.items) // size))
        return Reply(self.items[(page - 1) * size: page * size], {"X-WP-TotalPages": str(pages)})


# ------------------------------------------------------------------------------ the API

def test_every_item_is_read_page_by_page_without_the_seo_block(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "PER_PAGE", 2)
    hub = FakeHub()
    assert [i["id"] for i in api.fetch_items(hub)] == [1201, 1202, 903]
    assert [r["page"] for r in hub.requests] == ["1", "2"]
    assert "class_list" in hub.requests[0]["_fields"] and "aioseo" not in hub.requests[0]["_fields"]


def test_the_hub_is_asked_again_once_then_the_run_fails() -> None:
    assert len(api.fetch_items(FakeHub(failures=1))) == 3
    with pytest.raises(api.DoeError, match="did not answer"):
        api.fetch_items(FakeHub(failures=2))


# ------------------------------------------------------------------------------ records

def test_an_active_solicitation_becomes_a_calls_row() -> None:
    assert records.build_record(ACTIVE, NOW) == {
        "id": "doe-1201",
        "portal": "DOE SBIR",
        "title": "FY27 Phase I Release 1",
        "type": "SBIR/STTR Phase I",
        "department": "DOE Office of Technology Commercialization",
        "naics_code": "",
        "set_aside": "",
        "posted_date": "2026-10-20",
        "due_date": "2026-12-03T17:00:00-05:00",
        "description": ("An active DOE SBIR/STTR solicitation on DOE's SBIR/STTR Application Hub. Submission "
                        "deadline: 3 Dec 2026 at 5 PM ET.\n\n"
                        "DOE intends to make approximately 120 SBIR/STTR Phase I awards across advanced "
                        "manufacturing, critical minerals & AI.\nTopics\n1. AI for Grid Operations\n"
                        "This topic seeks machine learning software for grid control rooms.\n"
                        "2. Advanced Manufacturing\nThis topic seeks additive manufacturing processes."),
        "url": "https://sbir-sttr.connectwerx.org/portfolio-items/1201/",
        "source_type": "api",
        "extra": {"doe_post_id": 1201, "doe_status": "Active", "doe_modified": "2026-10-21T12:00:00",
                  "doe_deadline_text": "Submission Deadline: December 3, 2026 at 5 PM ET",
                  "doe_no_deadline": False, "doe_closed": False},
    }


def test_upcoming_and_closed_solicitations() -> None:
    upcoming, closed = records.build_record(UPCOMING, NOW), records.build_record(CLOSED, NOW)
    assert (upcoming["type"], upcoming["due_date"]) == ("SBIR/STTR Phase II", "")
    assert upcoming["description"].startswith("An upcoming DOE SBIR/STTR solicitation on DOE's SBIR/STTR Application "
                                              "Hub. No submission deadline yet.\n\nOpen to DOE Phase I awardees")
    assert upcoming["extra"]["doe_no_deadline"] is True and upcoming["extra"]["doe_closed"] is False
    assert closed["due_date"] == "2026-09-10T14:00:00-04:00" and closed["posted_date"] == "2026-07-08"
    assert closed["extra"]["doe_status"] == "Closed" and closed["extra"]["doe_closed"] is True
    assert "Process Details" not in closed["description"] and "Pitch Guide" not in closed["description"]


def test_deadlines_as_the_hub_writes_them() -> None:
    later = item(1, "Phase I", "Active", "Submission Deadline: Sept. 9, 2027 at 11:30 AM ET", "<p>x</p>")
    assert records.build_record(later, NOW)["due_date"] == "2027-09-09T11:30:00-04:00"
    noon = item(2, "Phase I", "Active", "Submission Deadline: October 2, 2026 at 12 PM ET", "<p>x</p>")
    assert records.build_record(noon, NOW)["due_date"] == "2026-10-02T12:00:00-04:00"
    excerpt_only = item(3, "Phase I", "Active", "Deadline to be posted", "<p>x</p>", excerpt="Submission Deadline: 12/03/2026")
    rec = records.build_record(excerpt_only, NOW)
    assert rec["due_date"] == "2026-12-03" and rec["extra"]["doe_deadline_text"] == "Submission Deadline: 12/03/2026"
    unreadable = item(4, "Phase I", "Active", "Submissions open soon", "<p>x</p>")
    assert records.build_record(unreadable, NOW)["extra"]["doe_no_deadline"] is False   # the quality alert counts it


def test_an_active_solicitation_whose_deadline_passed_is_closed() -> None:
    after = datetime(2026, 12, 3, 22, 30, tzinfo=timezone.utc)   # 17:30 Eastern
    assert records.build_record(ACTIVE, after)["extra"]["doe_closed"] is True
    assert records.build_record(ACTIVE, datetime(2026, 12, 3, 21, 30, tzinfo=timezone.utc))["extra"]["doe_closed"] is False


# ------------------------------------------------------------------------------ a run

def test_fetch_all_stores_the_active_and_upcoming_solicitations(ledger_db: str) -> None:
    counts = scrape.fetch_all(lq.start_run("DOE SBIR", component="doe_sbir"), now=NOW, opener=FakeHub())
    assert {row["id"] for row in lq.calls_where(portal="DOE SBIR")} == {"doe-1201", "doe-1202"}
    assert counts == {"found": 3, "scraped": 2, "new": 2, "failed": 0}


def test_a_stored_solicitation_that_closes_is_refreshed_as_closed(ledger_db: str) -> None:
    scrape.fetch_all(lq.start_run("DOE SBIR", component="doe_sbir"), now=NOW, opener=FakeHub())
    later = datetime(2026, 12, 4, 12, 0, tzinfo=timezone.utc)
    counts = scrape.fetch_all(lq.start_run("DOE SBIR", component="doe_sbir"), now=later, opener=FakeHub())
    assert counts == {"found": 3, "scraped": 2, "new": 0, "failed": 0}
    assert json.loads(lq.get_call("doe-1201")["extra"])["doe_closed"] is True   # type: ignore[index]


def test_fetch_all_honours_the_limit(ledger_db: str) -> None:
    counts = scrape.fetch_all(lq.start_run("DOE SBIR", component="doe_sbir"), limit=1, now=NOW, opener=FakeHub())
    assert counts["scraped"] == 1 and len(lq.calls_where(portal="DOE SBIR")) == 1


def test_every_solicitation_reaches_the_judges(ledger_db: str) -> None:
    # A rejected row is never filtered again, so a sparse upcoming listing must not be dropped
    # before its topics appear; each description names it an SBIR/STTR solicitation.
    scrape.fetch_all(lq.start_run("DOE SBIR", component="doe_sbir"), now=NOW, opener=FakeHub())
    kept, rejected = registry.get("doe_sbir").filter(lq.calls_where(portal="DOE SBIR"))
    assert {d.id for d in kept} == {"doe-1201", "doe-1202"} and rejected == []
    assert {d.id: d.tier for d in kept} == {"doe-1201": "tight", "doe-1202": "broad"}   # the topics name machine learning


def test_the_registry_finds_doe_sbir() -> None:
    found = registry.get("doe_sbir")
    assert found.name == "DOE SBIR" and not found.needs_browser and found.fetch_timeout == 120
    assert found.keywords and found.keywords.exists() and found.notes and found.notes.exists()
    assert "Application Hub" in found.how_to_submit
