"""A Vulcan SOF call read from the call feed its page loads (16 Nov 2026: Vulcan redesigned its call pages, and the feed
carries what the page text no longer shows, such as the deadline's time). The feed item here is made up; the repo is
public and Vulcan is behind a login, so no real call's text belongs in it."""
from __future__ import annotations

from datetime import datetime, timezone

from ledger import queries as lq
from portals.vulcan_sof import records, scrape

UUID = "0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b"
URL = f"https://vulcan-sof.com/login/ng2/call/{UUID}"
NOW = datetime(2026, 11, 16, 15, 0, tzinfo=timezone.utc)
FEED = {
    "uuid": UUID,
    "name": "  Example   Optical Turret (AOI 99-X001) ",
    "description": "An example agency wants a stabilised optical terminal that keeps a link through manoeuvres.\n\n"
                   "Offerors should show a link budget and a plan for flight testing.",
    "submissionStart": "2026-11-02T05:00:00.000Z",
    "submissionEnd": "2026-12-01T04:59:00.000Z",
    "deadlineTimezone": {"abbreviation": "EST", "offset": "UTC -5"},
    "engagementObjectives": ["OTA_PROTOTYPE", "TECH_EXPERIMENTATION"],
    "documents": [{"description": "AOI 99-X001", "filename": "aoi.pdf"}, {"description": "", "filename": "Quad chart.pptx"}],
    "customRequirements": [{"name": "White paper"}, "Quad chart"],
    "tags": [{"name": "Optics"}, "Communications"],
    "instruction": "  All submissions must be UNCLASSIFIED.\n\nUpload a white paper.  ",
    "organization": {"company": "Example Command", "acronym": "EXC"},
}


def test_a_feed_item_becomes_a_record_with_the_ledger_s_columns() -> None:
    rec = records.build_record(FEED, URL, NOW)
    assert set(rec) - {"id"} == set(lq.SCRAPED_COLUMNS)
    assert rec["id"] == f"vulcan-{UUID}" == scrape.call_id_for(URL)   # the same id the link gives
    assert rec["title"] == "Example Optical Turret (AOI 99-X001)"
    assert rec["portal"] == "Vulcan SOF" and rec["department"] == "USSOCOM / SOF Enterprise" and rec["url"] == URL
    assert rec["type"] == "OTA Prototype"
    assert rec["description"].startswith("An example agency wants") and "\n" not in rec["description"]


def test_dates_keep_their_time_in_the_format_vulcan_s_pages_showed() -> None:
    """The ledger's Vulcan dates read like '21 OCT 2026 : 21:59 MDT' (Mountain time, as the account saw them), and every
    reader of due_date parses that; the feed's UTC times are written the same way."""
    rec = records.build_record(FEED, URL, NOW)
    assert rec["due_date"] == "30 NOV 2026 : 21:59 MST"   # 04:59 UTC on 1 Dec
    assert rec["posted_date"] == "01 Nov 2026 : 22:00 MST"
    summer = {**FEED, "submissionEnd": "2026-10-22T03:59:00.000Z"}
    assert records.build_record(summer, URL, NOW)["due_date"] == "21 OCT 2026 : 21:59 MDT"


def test_the_extra_fields_come_from_the_feed() -> None:
    extra = records.build_record(FEED, URL, NOW)["extra"]
    assert extra["vulcan_closed"] is False and extra["vulcan_description_fallback"] is False
    assert extra["vulcan_objectives"] == ["OTA Prototype", "Tech Experimentation"]
    assert extra["vulcan_documents"] == ["AOI 99-X001", "Quad chart.pptx"]
    assert extra["vulcan_files_required"] == ["White paper", "Quad chart"]
    assert extra["vulcan_tags"] == ["Optics", "Communications"]
    assert extra["vulcan_instructions"] == "All submissions must be UNCLASSIFIED. Upload a white paper."


def test_a_call_past_its_deadline_is_closed() -> None:
    late = datetime(2026, 12, 2, tzinfo=timezone.utc)
    assert records.build_record(FEED, URL, late)["extra"]["vulcan_closed"] is True


def test_every_objective_reads_as_vulcan_names_it() -> None:
    assert [records.objective_name(o) for o in (
        "OTA_PROTOTYPE", "FAR_ACQUISITION", "TECH_EXPERIMENTATION", "CAPABILITY_DEMONSTRATION", "SBIR_STTR", "CRADA",
        "PRIZE_CHALLENGE", "MARKET_RESEARCH", "SOMETHING_NEW")] == [
        "OTA Prototype", "FAR Acquisition", "Tech Experimentation", "Capability Demonstration", "SBIR / STTR", "CRADA",
        "Prize Challenge", "Market Research", "Something New"]


def test_a_thin_feed_item_still_makes_a_record() -> None:
    thin = {"uuid": UUID, "name": "Bare call", "description": "Short.", "engagementObjectives": []}
    rec = records.build_record(thin, URL, NOW)
    assert rec["type"] == scrape.DEFAULT_TYPE and rec["due_date"] == "" and rec["posted_date"] == ""
    assert rec["extra"]["vulcan_description_fallback"] is True   # under 40 characters is not a real description
    assert rec["extra"]["vulcan_closed"] is False and rec["extra"]["vulcan_documents"] == []


def test_a_call_with_several_objectives_keeps_its_type_or_takes_the_most_binding_one() -> None:
    """The feed lists objectives alphabetically, not as the page did, so a call already in the ledger keeps the type it
    has while that is still one of its objectives (no churn in its tags and fit); a new call takes the most binding
    vehicle first. Vulcan's feed spells one code FAR_AQUISITION."""
    several = {**FEED, "engagementObjectives": ["CAPABILITY_DEMONSTRATION", "FAR_AQUISITION", "MARKET_RESEARCH"]}
    assert records.build_record(several, URL, NOW)["type"] == "FAR Acquisition"
    assert records.build_record(several, URL, NOW, known_type="Market Research")["type"] == "Market Research"
    assert records.build_record(several, URL, NOW, known_type="OTA Prototype")["type"] == "FAR Acquisition"   # no longer one
    research = {**FEED, "engagementObjectives": ["MARKET_RESEARCH", "TECH_EXPERIMENTATION"]}
    assert records.build_record(research, URL, NOW)["type"] == "Tech Experimentation"
    assert records.objective_name("FAR_AQUISITION") == "FAR Acquisition"
