"""NASA Forecast: the planned buys in NASA's acquisition forecast spreadsheet (PRO-545).

The workbook below is built in memory, made up but shaped like NASA's: one sheet, a header row of
named columns, shared strings for text and a number for each row's SourceID.
"""
from __future__ import annotations

import io
import json
import urllib.error
import zipfile
from datetime import datetime, timezone
from typing import Any
from xml.sax.saxutils import escape

import pytest

from ledger import queries as lq
from portals import registry
from portals.nasa_forecast import api, records, scrape

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)
MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
HEADER = ["BuyingOffice", "AcquisitionStatus", "AwardedOrWithdrawn", "AcquisitionPhase", "SourceID",
          "TitleOfRequirement", "TechnicalPOC", "Tech POC Name", "NAICS", "NAICS Description",
          "SmallBusinessSpecialistPOC", "SmallBusinessSpecialistEmail", "AnticipatedFYAward",
          "Anticipated Qtr of Award", "NewOrRecompete", "EstimatedContractValue", "SetAsideType", "ContractType",
          "Summary", "QtrSolOrNOFORelease", "FYofSolOrNOFORelease", "TypeOfRequirement", "ExtentCompeted",
          "Description"]
AUTONOMY = ["MSFC", "Revised", "N/A", "Acquisition Planning", 10094, "Autonomy Software for Lunar Surface Operations",
            "pat.example@nasa.gov", "Example, Pat", "541512", "Computer Systems Design Services ", "Lee, Sam",
            "msfc-smallbusiness@example.gov", "2027", "Q2", "New", "$5M - $10M", "Small Business Set Aside - Total",
            "Firm Fixed Price", "Software for autonomous rover operations.", "Q3", "2026", "Services",
            "Full and Open Competition after exclusion of sources",
            "Develop and test autonomy software for lunar rovers &amp; landers."]
LIGHTING = ["KSC", "New", "N/A", "Acquisition Planning", 10200, "Launch Pad Lighting Replacement", "", "", "238210",
            "Electrical Contractors", "", "", "2027", "Q1", "New", "$1M - $5M", "To Be Determined", "Firm Fixed Price",
            "Replace lighting at pad 39B.", "Q4", "2026", "Construction (Incl. A&amp;E)", "Full and Open Competition", ""]
AWARDED = ["MSFC", "Awarded", "Awarded", "Awarded", 929, "Program Support Services II", "", "", "541715", "", "", "",
           "2026", "Q3", "Re-compete", "$250M - $500M", "", "", "Program planning and control.", "Q3", "2025", "Services",
           "", ""]
CANCELLED = ["GSFC", "Revised", "N/A", "Cancelled", 10300, "Ground Data System Sustainment", "", "", "541519", "", "",
             "", "2027", "Q4", "New", "$10M - $25M", "", "", "Ground system software sustainment.", "Q1", "2027",
             "Services", "", ""]


def column(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


def workbook(*rows: list[Any], blank_row: bool = True) -> bytes:
    strings: list[str] = []
    xml_rows = []
    for number, values in enumerate(rows, 1):
        cells = []
        for index, value in enumerate(values):
            where = f"{column(index)}{number}"
            if isinstance(value, int):
                cells.append(f'<c r="{where}" s="2"><v>{value}</v></c>')
            elif value:
                strings.append(value)
                cells.append(f'<c r="{where}" t="s"><v>{len(strings) - 1}</v></c>')
        xml_rows.append(f'<row r="{number}">{"".join(cells)}</row>')
    if blank_row:
        xml_rows.append(f'<row r="{len(rows) + 1}"></row>')
    shared = (f'<?xml version="1.0" encoding="UTF-8"?><sst xmlns="{MAIN}">'
              + "".join(f"<si><t>{s if '&amp;' in s else escape(s)}</t></si>" for s in strings) + "</sst>")
    sheet = f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="{MAIN}"><sheetData>{"".join(xml_rows)}</sheetData></worksheet>'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as book:
        book.writestr("xl/sharedStrings.xml", shared)
        book.writestr("xl/worksheets/sheet1.xml", sheet)
    return buffer.getvalue()


BOOK = workbook(HEADER, AUTONOMY, LIGHTING, AWARDED, CANCELLED)


class Reply:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> "Reply":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def read(self, size: int = -1) -> bytes:
        return self.body if size < 0 else self.body[:size]


class FakeNasa:
    def __init__(self, body: bytes = BOOK, failures: int = 0) -> None:
        self.body = body
        self.failures = failures
        self.requests: list[str] = []

    def __call__(self, request: Any, timeout: float) -> Reply:
        assert timeout >= 10 and "velocity-bd-team" in request.get_header("User-agent")
        self.requests.append(request.full_url)
        if len(self.requests) <= self.failures:
            raise urllib.error.URLError("timed out")
        return Reply(self.body)


def rows() -> list[dict[str, str]]:
    return api.read_rows(BOOK)


# ------------------------------------------------------------------------------ the spreadsheet

def test_rows_are_read_by_column_name_without_a_spreadsheet_library() -> None:
    found = rows()
    assert len(found) == 4   # the blank row is skipped
    first = found[0]
    assert (first["SourceID"], first["TitleOfRequirement"], first["NAICS"]) == (
        "10094", "Autonomy Software for Lunar Surface Operations", "541512")
    assert first["Description"] == "Develop and test autonomy software for lunar rovers & landers."
    assert "TechnicalPOC" not in found[1]   # empty cells are left out


def test_a_download_that_is_not_the_forecast_is_an_error() -> None:
    with pytest.raises(api.NasaError, match="not a spreadsheet"):
        api.read_rows(b"<html>Maintenance</html>")
    renamed = workbook(["Office", "Title"], ["MSFC", "Something"])
    with pytest.raises(api.NasaError, match="columns"):
        api.read_rows(renamed)


def test_the_forecast_is_downloaded_with_one_retry() -> None:
    site = FakeNasa(failures=1)
    assert api.fetch_workbook(site) == BOOK and site.requests == [api.FORECAST_URL] * 2
    with pytest.raises(api.NasaError, match="did not answer"):
        api.fetch_workbook(FakeNasa(failures=2))


# ------------------------------------------------------------------------------ records

def test_a_forecast_row_becomes_a_calls_row() -> None:
    assert records.build_record(rows()[0], NOW) == {
        "id": "nasa-10094",
        "portal": "NASA Forecast",
        "title": "Autonomy Software for Lunar Surface Operations",
        "type": "Forecast",
        "department": "NASA MSFC",
        "naics_code": "541512",
        "set_aside": "Small Business Set Aside - Total",
        "posted_date": "",
        "due_date": "",
        "description": ("A NASA acquisition forecast from MSFC: solicitation expected Q3 FY2026, award expected Q2 "
                        "FY2027. New, estimated value $5M - $10M, Firm Fixed Price, Full and Open Competition after "
                        "exclusion of sources. NAICS 541512 (Computer Systems Design Services).\n\n"
                        "Software for autonomous rover operations.\n\n"
                        "Develop and test autonomy software for lunar rovers & landers."),
        "url": "https://www.hq.nasa.gov/office/procurement/forecast/NAF.html",
        "source_type": "forecast",
        "extra": {"nasa_source_id": "10094", "nasa_status": "Revised", "nasa_phase": "Acquisition Planning",
                  "nasa_solicitation_expected": "Q3 FY2026", "nasa_award_expected": "Q2 FY2027",
                  "nasa_estimated_value": "$5M - $10M", "nasa_requirement": "Services",
                  "nasa_contacts": [{"name": "Example, Pat", "email": "pat.example@nasa.gov", "role": "technical"},
                                    {"name": "Lee, Sam", "email": "msfc-smallbusiness@example.gov", "role": "small business"}],
                  "nasa_no_deadline": True, "nasa_closed": False},
    }


def test_awarded_withdrawn_and_cancelled_rows_are_closed() -> None:
    autonomy, lighting, awarded, cancelled = (records.build_record(r, NOW) for r in rows())
    assert [r["extra"]["nasa_closed"] for r in (autonomy, lighting, awarded, cancelled)] == [False, False, True, True]
    assert lighting["extra"]["nasa_contacts"] is None and lighting["description"].endswith("Replace lighting at pad 39B.")
    withdrawn = records.build_record({**rows()[0], "AwardedOrWithdrawn": "Withdrawn"}, NOW)
    assert withdrawn["extra"]["nasa_closed"] is True


# ------------------------------------------------------------------------------ a run

def test_fetch_all_stores_the_live_forecast_rows(ledger_db: str) -> None:
    counts = scrape.fetch_all(lq.start_run("NASA Forecast", component="nasa_forecast"), now=NOW, opener=FakeNasa())
    assert {row["id"] for row in lq.calls_where(portal="NASA Forecast")} == {"nasa-10094", "nasa-10200"}
    assert counts == {"found": 4, "scraped": 2, "new": 2, "failed": 0}


def test_a_stored_row_that_nasa_awards_is_refreshed_as_closed(ledger_db: str) -> None:
    scrape.fetch_all(lq.start_run("NASA Forecast", component="nasa_forecast"), now=NOW, opener=FakeNasa())
    awarded_now = AUTONOMY[:1] + ["Awarded", "Awarded"] + AUTONOMY[3:]
    later = workbook(HEADER, awarded_now, LIGHTING, AWARDED, CANCELLED)
    counts = scrape.fetch_all(lq.start_run("NASA Forecast", component="nasa_forecast"), now=NOW, opener=FakeNasa(later))
    assert counts == {"found": 4, "scraped": 2, "new": 0, "failed": 0}
    assert json.loads(lq.get_call("nasa-10094")["extra"])["nasa_closed"] is True   # type: ignore[index]


def test_fetch_all_honours_the_limit(ledger_db: str) -> None:
    counts = scrape.fetch_all(lq.start_run("NASA Forecast", component="nasa_forecast"), limit=1, now=NOW, opener=FakeNasa())
    assert counts["scraped"] == 1 and len(lq.calls_where(portal="NASA Forecast")) == 1


def test_the_keyword_filter_keeps_velocitys_naics_codes_and_topics(ledger_db: str) -> None:
    scrape.fetch_all(lq.start_run("NASA Forecast", component="nasa_forecast"), now=NOW, opener=FakeNasa())
    kept, rejected = registry.get("nasa_forecast").filter(lq.calls_where(portal="NASA Forecast"))
    assert [d.id for d in kept] == ["nasa-10094"] and "541512" in kept[0].keywords
    assert [(d.id, d.reason) for d in rejected] == [("nasa-10200", "no keyword match")]


def test_the_registry_finds_the_nasa_forecast() -> None:
    found = registry.get("nasa_forecast")
    assert found.name == "NASA Forecast" and not found.needs_browser and found.fetch_timeout == 120
    assert found.keywords and found.keywords.exists() and found.notes and found.notes.exists()
    assert "forecast" in found.how_to_submit
