"""The Vulcan SOF scraper: call links on the listing, ids, and each call read from its feed (records.py turns a feed
item into a row; tests/test_vulcan_records.py covers that). Feed items here are made up: Vulcan is behind a login."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from ledger import queries as lq
from portals.shared import browser
from portals.vulcan_sof import scrape
from portals.vulcan_sof.run_scrape import fill_rates

URL = "https://vulcan-sof.com/login/ng2/collection/detail?collectionUuid=0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b&x=1"
NEW_URL = "https://vulcan-sof.com/login/ng2/call/0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b"
FEED = {
    "uuid": "0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b",
    "name": "Example Turret",
    "description": "An example agency wants a stabilised optical terminal that keeps a link through manoeuvres.",
    "submissionEnd": "2026-12-01T04:59:00.000Z",
    "engagementObjectives": ["OTA_PROTOTYPE"],
}


def test_call_id_from_uuid_or_hash() -> None:
    assert scrape.call_id_for(URL) == "vulcan-0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b"
    hashed = scrape.call_id_for("https://vulcan-sof.com/other")
    assert hashed.startswith("vulcan-") and hashed == scrape.call_id_for("https://vulcan-sof.com/other")


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


def test_scrape_call_reads_the_call_s_feed(page, monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[str] = []
    monkeypatch.setattr(scrape, "fetch_feed", lambda p, uuid: asked.append(uuid) or FEED)
    rec = scrape.scrape_call(page, NEW_URL, "Listing title")
    assert asked == ["0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b"]
    assert rec is not None and rec["id"] == "vulcan-0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b" and rec["title"] == "Example Turret"
    assert rec["due_date"] == "30 NOV 2026 : 21:59 MST" and rec["url"] == NEW_URL


def test_scrape_call_returns_none_on_failure(page, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(p: object, uuid: str) -> dict:
        raise TimeoutError("the feed took too long")

    monkeypatch.setattr(scrape, "fetch_feed", boom)
    assert scrape.scrape_call(page, NEW_URL, "Some call") is None
    assert scrape.scrape_call(page, "https://vulcan-sof.com/login/ng2/calendar", "Not a call") is None   # no id to read


def test_scrape_all_counts_and_upserts(page, ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    broken = "ffffffff-0000-0000-0000-000000000000"
    monkeypatch.setattr(scrape, "list_calls", lambda p: [
        {"title": "Turret", "href": NEW_URL},
        {"title": "Broken", "href": f"https://vulcan-sof.com/login/ng2/call/{broken}"},
    ])

    def feed(p: object, uuid: str) -> dict:
        if uuid == broken:
            raise RuntimeError("call feed answered 500")
        return FEED

    monkeypatch.setattr(scrape, "fetch_feed", feed)
    monkeypatch.setattr(scrape, "PAGE_GAP_MS", 1)
    run1 = lq.start_run("Vulcan SOF")
    counts = scrape.scrape_all(page, run1, save_samples=False)
    assert counts == {"found": 2, "scraped": 1, "new": 1, "failed": 1}
    run2 = lq.start_run("Vulcan SOF")
    assert scrape.scrape_all(page, run2, save_samples=False)["new"] == 0
    row = lq.get_call("vulcan-0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b")
    assert row is not None and row["first_run_id"] == run1 and row["last_run_id"] == run2
    assert row["due_date"] == "30 NOV 2026 : 21:59 MST"
    assert [r["id"] for r in lq.calls_in_run(run2)] == [row["id"]]


def test_a_call_keeps_its_id_under_vulcan_s_new_links() -> None:
    """16 Nov 2026: Vulcan's cards link to /login/ng2/call/<uuid> (and its page to .../about), no longer to
    ?collectionUuid=<uuid>. The uuid is the same, so a call keeps the id it had; a new id would duplicate every call."""
    old = "https://vulcan-sof.com/login/ng2/collection/detail?collectionUuid=3c3c5337-e5ad-43a2-bf10-804c6d7e705a"
    new = "https://vulcan-sof.com/login/ng2/call/3c3c5337-e5ad-43a2-bf10-804c6d7e705a"
    about = new + "/about"
    assert scrape.call_id_for(old) == scrape.call_id_for(new) == scrape.call_id_for(about) == "vulcan-3c3c5337-e5ad-43a2-bf10-804c6d7e705a"


def test_list_calls_reads_vulcan_s_new_call_links(page, monkeypatch: pytest.MonkeyPatch) -> None:
    html = """
    <a class="collection__name" href="/login/ng2/call/a26a99ef-c351-464f-af93-dbcc064df521">Helmet-Mounted FPV Display</a>
    <a href="/login/ng2/call/a26a99ef-c351-464f-af93-dbcc064df521"><img></a>
    <a href="/login/ng2/call/8d7c3aeb-4368-4f1a-b09f-d90d5de908dc">Standalone Non-Radio Frequency Systems</a>
    <a href="/login/ng2/organization/12b03aa0-99a6-4d6f-ba7a-f02ed3712f46">An organization</a>
    <a href="/login/ng2/calendar">Calendar</a>
    """
    monkeypatch.setattr(page, "goto", lambda url, **kw: page.set_content(html))
    calls = scrape.list_calls(page)
    assert [c["title"] for c in calls] == ["Helmet-Mounted FPV Display", "Standalone Non-Radio Frequency Systems"]
    assert [scrape.call_id_for(c["href"]) for c in calls] == [
        "vulcan-a26a99ef-c351-464f-af93-dbcc064df521", "vulcan-8d7c3aeb-4368-4f1a-b09f-d90d5de908dc"]
