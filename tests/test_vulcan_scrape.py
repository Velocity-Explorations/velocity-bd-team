from __future__ import annotations

from collections.abc import Iterator

import pytest

from ledger import queries as lq
from portals.shared import browser
from portals.vulcan_sof import scrape
from portals.vulcan_sof.run_scrape import fill_rates

BODY = (
    "Vulcan\nHome Explore Calendar\n"
    "Resilient Airborne Free-Space Optical Communications Turret (AOI 27-A001)\n"
    "NIWC Atlantic\n"
    "Open Date: Oct 1, 2026, 8:00 AM MDT\n"
    "Deadline: Nov 14, 2026, 5:00 PM MDT\n"
    "Engagement Objectives:\n"
    "OTA Prototype\n"
    "Tech Experimentation\n"
    "\n"
    "Bottom Line Upfront\n"
    "NIWC Atlantic seeks a gimbal-stabilised free-space optical terminal that keeps a link "
    "through aircraft manoeuvres and weather, with a path to airworthiness on Group 3 platforms. "
    "Offerors should show a demonstrated link budget and a plan for flight testing.\n"
    "\n"
    "Problem Statement\n"
    "Radio frequency links are detectable and jammable.\n"
)
URL = "https://vulcan-sof.com/login/ng2/collection/detail?collectionUuid=0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b&x=1"


def test_extract_fields_from_representative_body() -> None:
    f = scrape.extract_fields(BODY)
    assert f["due_date"] == "Nov 14, 2026, 5:00 PM MDT"
    assert f["posted_date"] == "Oct 1, 2026, 8:00 AM MDT"
    assert f["type"] == "OTA Prototype"
    assert f["description"].startswith("NIWC Atlantic seeks a gimbal-stabilised")
    assert f["description_is_fallback"] == ""


def test_extract_fields_fallbacks() -> None:
    body = "x" * 700
    f = scrape.extract_fields(body)
    assert f["due_date"] == "" and f["posted_date"] == ""
    assert f["type"] == scrape.DEFAULT_TYPE
    assert f["description"] == body[200:600] and f["description_is_fallback"] == "1"
    assert f["closed"] == ""


def test_description_survives_long_first_paragraph_and_numbered_heading() -> None:
    # Real pages: first paragraph after the heading runs 700 to 1,250 chars with no blank line.
    long_para = "The U.S. military must be prepared to fight and win in a constant state of contest. " * 15
    body = f"Deadline:\n30 OCT 2026 : 21:59 MDT\nProblem Statement\n\n{long_para}\n\nThe objective is X.\n"
    f = scrape.extract_fields(body)
    assert f["description"].startswith("The U.S. military must be prepared")
    assert 400 < len(f["description"]) <= 1500 and "\n" not in f["description"]
    assert f["description_is_fallback"] == ""

    numbered = ("Problem Statement\n\n1. Problem Statement & Executive Summary\n\n"
                "The organization requires a scalable way to ingest threat reports from many feeds and reduce noise.\n")
    f = scrape.extract_fields(numbered)
    assert f["description"].startswith("1. Problem Statement & Executive Summary The organization requires")


def test_closed_call_flag_and_sample_file_shape() -> None:
    body = BODY + "\nAdditional Instructions\nThis call has closed.\nSubmissions are no longer accepted.\n"
    rec = scrape.build_record(URL, "T", body)
    assert rec["extra"]["vulcan_closed"] is True
    assert scrape.build_record(URL, "T", BODY)["extra"]["vulcan_closed"] is False


def test_call_id_from_uuid_or_hash() -> None:
    assert scrape.call_id_for(URL) == "vulcan-0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b"
    hashed = scrape.call_id_for("https://vulcan-sof.com/other")
    assert hashed.startswith("vulcan-") and hashed == scrape.call_id_for("https://vulcan-sof.com/other")


def test_build_record_matches_ledger_columns() -> None:
    rec = scrape.build_record(URL, "Turret", BODY)
    assert set(rec) - {"id"} == set(lq.SCRAPED_COLUMNS)
    assert rec["portal"] == "Vulcan SOF" and rec["department"] == "USSOCOM / SOF Enterprise"
    assert rec["source_type"] == "regular" and rec["naics_code"] == "" and rec["set_aside"] == ""
    assert rec["extra"]["vulcan_description_fallback"] is False and rec["extra"]["vulcan_closed"] is False
    assert rec["extra"]["vulcan_objectives"] == ["OTA Prototype", "Tech Experimentation"]


def test_fill_rates_exclude_fallbacks() -> None:
    rows = [
        {"due_date": "Nov 1", "posted_date": "", "type": "OTA Prototype", "description": "real", "extra": '{"vulcan_description_fallback": false}'},
        {"due_date": "", "posted_date": "Oct 1", "type": scrape.DEFAULT_TYPE, "description": "fallback text", "extra": '{"vulcan_description_fallback": true}'},
    ]
    rates = fill_rates(rows)
    assert rates == {"due_date": 50.0, "posted_date": 50.0, "type": 50.0, "description": 50.0}
    assert fill_rates([]) == {f: 0.0 for f in ("due_date", "posted_date", "type", "description")}


@pytest.fixture(scope="module")
def page() -> Iterator[object]:
    pw, b, ctx, pg = browser.launch()
    try:
        yield pg
    finally:
        browser.close_all(pw, b, ctx, pg)


def test_list_calls_dedupes_and_drops_empty(page, monkeypatch: pytest.MonkeyPatch) -> None:
    html = """
    <a href="/d?collectionUuid=0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b"><img></a>
    <a href="/d?collectionUuid=0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b">  Turret  </a>
    <a href="/d?collectionUuid=1f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b">Power</a>
    <a href="/elsewhere">Not a call</a>
    """
    monkeypatch.setattr(page, "goto", lambda url, **kw: page.set_content(html))
    calls = scrape.list_calls(page)
    assert [c["title"] for c in calls] == ["Turret", "Power"]
    assert all("collectionUuid" in c["href"] for c in calls)


def test_scrape_call_returns_none_on_failure(page, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(url: str, **kw: object) -> None:
        raise TimeoutError("navigation took too long")

    monkeypatch.setattr(page, "goto", boom)
    assert scrape.scrape_call(page, "https://vulcan-sof.com/x?collectionUuid=abc", "Some call") is None


def test_scrape_all_counts_and_upserts(page, ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    pages = {
        "ok": "<html><body><pre>" + BODY.replace("\n", "<br>") + "</pre></body></html>",
    }
    monkeypatch.setattr(scrape, "list_calls", lambda p: [
        {"title": "Turret", "href": URL},
        {"title": "Broken", "href": "https://vulcan-sof.com/broken?collectionUuid=ffffffff-0000-0000-0000-000000000000"},
    ])

    def goto(url: str, **kw: object) -> None:
        if "broken" in url:
            raise RuntimeError("500")
        page.set_content(pages["ok"])

    monkeypatch.setattr(page, "goto", goto)
    monkeypatch.setattr(scrape, "DETAIL_WAIT_MS", 10)
    monkeypatch.setattr(scrape, "PAGE_GAP_MS", 1)
    run1 = lq.start_run("Vulcan SOF")
    counts = scrape.scrape_all(page, run1, save_samples=False)
    assert counts == {"found": 2, "scraped": 1, "new": 1, "failed": 1}
    run2 = lq.start_run("Vulcan SOF")
    assert scrape.scrape_all(page, run2, save_samples=False)["new"] == 0
    row = lq.get_call("vulcan-0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b")
    assert row is not None and row["first_run_id"] == run1 and row["last_run_id"] == run2
    assert [r["id"] for r in lq.calls_in_run(run2)] == [row["id"]]


PAGE = (
    "Me ▼\nExpeditionary Basing Power Generation and Distribution\nSUBMIT A SCOUT CARD TO:\nACTIVE CALL\nFullscreen\n"
    "Engagement Objectives:\nCRADA\nMarket Research\nOTA Prototype\n"
    "Open Date:\n04 Oct 2026 : 22:00 MDT\nDeadline:\n30 OCT 2026 : 21:59 MDT\n\nDays\n13\nHours\n15\n"
    "Documents:\n Power Generation and Distribution TIIs\n"
    "Files Required for Submission:\nWhite Paper Template (See template)\nQuad Chart Template (See template)\n"
    "Tags\nPower & Energy\nEnergy Storage\n"
    "Problem Statement\n\nThe U.S. military must be prepared to fight and win in a constant state of contest unseen "
    "during the last 25 years of warfare, and needs mission critical energy without reliance on bulk fuel.\n\n"
    "Additional Instructions\n\nAll submissions must be UNCLASSIFIED.\n\nCreate a Vulcan Scout Card and upload a white paper.\n"
    "This call has closed.\n Submissions are no longer accepted. \n1\nRecent Activity\n2\nSubmit Existing Card(s)\n"
    "Image\tName\tOrganization\tCreated by\nEcho C2 AI\tVelocity Explorations\tSomeone Named\n"
)


def test_extract_sections_reads_each_labelled_section() -> None:
    s = scrape.extract_sections(PAGE)
    assert s["objectives"] == ["CRADA", "Market Research", "OTA Prototype"]
    assert s["documents"] == ["Power Generation and Distribution TIIs"]
    assert s["files_required"] == ["White Paper Template (See template)", "Quad Chart Template (See template)"]
    assert s["tags"] == ["Power & Energy", "Energy Storage"]
    assert s["instructions"] == "All submissions must be UNCLASSIFIED. Create a Vulcan Scout Card and upload a white paper."


def test_extract_sections_never_reads_past_the_instructions() -> None:
    s = scrape.extract_sections(PAGE)
    assert "Someone Named" not in s["instructions"] and "Recent Activity" not in s["instructions"]


def test_extract_sections_tolerates_missing_sections() -> None:
    s = scrape.extract_sections("Engagement Objectives:\nTech Experimentation\nOpen Date:\n01 Jun 2026 : 09:00 MDT\n")
    assert s == {"objectives": ["Tech Experimentation"], "documents": [], "files_required": [], "tags": [], "instructions": ""}


def test_build_record_carries_the_sections_in_extra() -> None:
    rec = scrape.build_record(URL, "Power", PAGE)
    extra = rec["extra"]
    assert extra["vulcan_files_required"] == ["White Paper Template (See template)", "Quad Chart Template (See template)"]
    assert extra["vulcan_objectives"][0] == "CRADA" and extra["vulcan_tags"] == ["Power & Energy", "Energy Storage"]
    assert extra["vulcan_instructions"].startswith("All submissions must be UNCLASSIFIED.")
    assert extra["vulcan_closed"] is True
