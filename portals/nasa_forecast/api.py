"""NASA's acquisition forecast: one spreadsheet of planned buys, read with the standard library.

    data = fetch_workbook()   # one download a run, about 83 KB
    found = read_rows(data)   # one dict per row, keyed by the header row's column names

An .xlsx file is a zip of XML parts; the forecast is one sheet whose text sits in the shared
strings part, so reading it needs no spreadsheet library. The download is limited to
MAX_BYTES and checked before it is parsed. NASA's server has no robots.txt (it answers 403,
which the robots standard reads as no rules). Docs: portals/nasa_forecast/NOTES.md.
"""
from __future__ import annotations

import io
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Callable
from typing import Any

FORECAST_URL = "https://www.hq.nasa.gov/office/procurement/forecast/AcqForecastNew.xlsx"
TIMEOUT_S = 60
MAX_BYTES = 20_000_000   # the download, and each part unpacked from it
USER_AGENT = "velocity-bd-team scanner (Velocity Explorations)"
SHEET = "xl/worksheets/sheet1.xml"
STRINGS = "xl/sharedStrings.xml"
NEEDED = ("SourceID", "TitleOfRequirement")
MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
COLUMN = re.compile(r"[A-Z]+")
WHOLE = re.compile(r"^(\d+)\.0+$")

Opener = Callable[..., Any]   # urllib.request.urlopen, or a test's stand-in


class NasaError(RuntimeError):
    """The forecast did not download or read as expected. The pipeline records it and alerts."""


def fetch_workbook(opener: Opener | None = None) -> bytes:
    """The forecast spreadsheet, retried once."""
    opener = opener or urllib.request.urlopen
    problem = ""
    for _ in range(2):
        request = urllib.request.Request(FORECAST_URL, headers={"User-Agent": USER_AGENT})
        try:
            with opener(request, timeout=TIMEOUT_S) as reply:
                data = reply.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise NasaError(f"the forecast download is larger than {MAX_BYTES:,} bytes")
            return data
        except urllib.error.HTTPError as exc:
            problem = f"HTTP {exc.code}"
        except (urllib.error.URLError, OSError, ValueError) as exc:
            problem = type(exc).__name__
    raise NasaError(f"NASA's forecast did not answer ({problem})")


def _part(book: zipfile.ZipFile, name: str) -> bytes:
    if book.getinfo(name).file_size > MAX_BYTES:
        raise NasaError(f"the forecast's {name} unpacks larger than {MAX_BYTES:,} bytes")
    return book.read(name)


def _texts(node: ET.Element) -> str:
    return "".join(t.text or "" for t in node.iter(f"{MAIN}t"))


def _value(cell: ET.Element, shared: list[str]) -> str:
    kind, value = cell.get("t"), cell.find(f"{MAIN}v")
    if kind == "inlineStr":
        return _texts(cell)
    if value is None or value.text is None:
        return ""
    if kind == "s":
        index = int(value.text)
        return shared[index] if index < len(shared) else ""
    whole = WHOLE.match(value.text)
    return whole.group(1) if whole else value.text


def read_rows(data: bytes) -> list[dict[str, str]]:
    """Every row under the header, as {column name: text}; empty cells and empty rows left out."""
    try:
        book = zipfile.ZipFile(io.BytesIO(data))
        names = set(book.namelist())
    except zipfile.BadZipFile:
        raise NasaError("the forecast download is not a spreadsheet") from None
    if SHEET not in names:
        raise NasaError("the forecast spreadsheet has no first sheet")
    try:
        shared = [_texts(si) for si in ET.fromstring(_part(book, STRINGS)).iter(f"{MAIN}si")] if STRINGS in names else []
        sheet = ET.fromstring(_part(book, SHEET))
    except ET.ParseError as exc:
        raise NasaError(f"the forecast spreadsheet could not be read ({exc})") from None
    table: list[dict[str, str]] = []
    for row in sheet.iter(f"{MAIN}row"):
        cells: dict[str, str] = {}
        for cell in row.iter(f"{MAIN}c"):
            where = COLUMN.match(cell.get("r") or "")
            text = " ".join(_value(cell, shared).split())
            if where and text:
                cells[where.group(0)] = text
        table.append(cells)
    header = table[0] if table else {}
    if not all(name in header.values() for name in NEEDED):
        raise NasaError(f"the forecast's columns changed: no {' or '.join(NEEDED)} in its header row")
    return [record for record in ({header[col]: text for col, text in cells.items() if col in header}
                                  for cells in table[1:]) if record]
