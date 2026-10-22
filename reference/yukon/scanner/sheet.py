"""
Yukon — Google Sheets writer
Appends new opportunities to the BD Opportunity Tracker sheet.
Uses gog CLI for Sheets API access.

Important: Inbox writes use a single batch update against a contiguous range.
The older row-by-row exact-range approach was causing intermittent 400 badRequest
errors when the sheet had recent edits or row state drift.
"""

import json
import logging
import subprocess
from datetime import datetime, timezone
from typing import Dict, List

log = logging.getLogger(__name__)

SHEET_ID = "1loGmTp3jxfKqT9z5dfoYg9NAdliRXsccq7QtmdjYOw0"
SHEET_ACCOUNT = "david@velocityexplorations.com"
SHEET_RANGE = "📥 Inbox!A:O"


def append_opportunities(opps: List[Dict], dry_run: bool = False) -> int:
    """
    Append a list of opportunities to the Google Sheet.
    Returns number of rows written.
    """
    if not opps:
        return 0

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = [_build_row_values(opp, today) for opp in opps]

    if dry_run:
        for opp in opps:
            log.info(f"[DRY RUN] Would write to sheet: {opp.get('title','?')[:60]}")
        return len(rows)

    try:
        written = _write_rows(rows)
        log.info(f"Sheet: wrote {written}/{len(opps)} opportunities")
        return written
    except Exception as e:
        log.error(f"Sheet: batch write failed: {e}")
        return 0


def _build_row(opp: Dict, today: str) -> str:
    """Build a pipe-separated row string for gog sheets append."""
    return "|".join(_build_row_values(opp, today))


def _build_row_values(opp: Dict, today: str) -> List[str]:
    """Build a row as a list of cell values for batch writes."""
    score = opp.get("yukon_score", "")
    reasoning = opp.get("yukon_reasoning", "")

    cells = [
        today,                        # A: Date Found
        "",                           # B: Relevant — dpw fills in (Yes/No/Maybe), never touch
        opp.get("portal", ""),        # C: Portal
        opp.get("title", ""),         # D: Title
        opp.get("description", ""),   # E: Description
        opp.get("type", ""),          # F: Type
        opp.get("department", ""),    # G: Agency
        opp.get("posted_date", ""),   # H: Posted
        opp.get("due_date", ""),      # I: Due Date
        opp.get("naics_code", ""),    # J: NAICS
        opp.get("set_aside", ""),     # K: Set-Aside
        opp.get("url", ""),           # L: URL
        "",                           # M: Notes — dpw fills this in
        str(score),                   # N: Yukon Score
        reasoning,                    # O: Yukon Reasoning
    ]

    # Escape pipes within cell values
    return [str(c).replace("|", "/").replace("\n", " ") for c in cells]


def _write_row(row: str) -> bool:
    """Write a single row to the sheet using gog CLI update at the next empty row."""
    next_row = _get_next_inbox_row()
    if next_row is None:
        next_row = 2
    cmd = [
        "gog", "sheets", "update",
        SHEET_ID,
        f"📥 Inbox!A{next_row}:O{next_row}",
        row,
        "-a", SHEET_ACCOUNT,
        "--json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        log.error(f"Sheet gog error: {result.stderr[:200]}")
        return False
    try:
        data = json.loads(result.stdout)
        return data.get("updatedRows", 0) > 0 or data.get("updatedCells", 0) > 0
    except Exception:
        return result.returncode == 0


def _write_rows(rows: List[List[str]]) -> int:
    """Write multiple Inbox rows in one batch to the next contiguous range."""
    if not rows:
        return 0

    next_row = _get_next_inbox_row()
    end_row = next_row + len(rows) - 1
    range_str = f"'📥 Inbox'!A{next_row}:O{end_row}"
    cmd = [
        "gog", "sheets", "update",
        SHEET_ID, range_str,
        "--values-json", json.dumps(rows),
        "-a", SHEET_ACCOUNT,
        "--input", "USER_ENTERED",
        "--json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        log.error(f"Inbox sheet batch write error: {result.stderr[:200]}")
        return 0
    try:
        data = json.loads(result.stdout)
        return data.get("updatedRows", 0)
    except Exception:
        return len(rows)


FORECAST_RANGE = "📋 Forecasts!A:P"


def write_forecast(opp: Dict, today: str, dry_run: bool = False) -> bool:
    """Write a single forecast opp to the Forecasts tab. Returns True on success."""
    return write_forecasts([opp], today, dry_run) > 0


def write_forecasts(opps: List[Dict], today: str, dry_run: bool = False) -> int:
    """
    Write multiple forecast opps to the Forecasts tab in one batch call.
    Uses values-json to bypass table row-count bounds.
    Returns number of rows written.
    """
    if not opps:
        return 0
    if dry_run:
        for opp in opps:
            log.info(f"[DRY RUN] Would write forecast: {opp.get('title','?')[:60]}")
        return len(opps)

    rows = []
    for opp in opps:
        cells = [
            today,                                      # A: Date Found
            "",                                         # B: Relevant (dpw fills)
            opp.get("title", ""),                       # C: Title
            opp.get("portal", ""),                      # D: Portal
            opp.get("department", ""),                  # E: Agency
            opp.get("naics_code", ""),                  # F: NAICS
            opp.get("set_aside", ""),                   # G: Set-Aside
            opp.get("estimated_value", ""),             # H: Est. Value
            opp.get("sol_release_fy", ""),              # I: Sol. Release FY
            opp.get("sol_release_quarter", ""),         # J: Sol. Release Quarter
            opp.get("forecast_fy", ""),                 # K: Award FY
            opp.get("forecast_quarter", ""),            # L: Award Quarter
            opp.get("url", ""),                         # M: URL
            str(opp.get("description", "") or "")[:200],  # N: Description
            "Forecast",                                 # O: Status
            "",                                         # P: SAM.gov Match
        ]
        rows.append([str(c).replace("\n", " ") for c in cells])

    next_row = _get_next_forecast_row()
    end_row = next_row + len(rows) - 1
    range_str = f"'📋 Forecasts'!A{next_row}:P{end_row}"
    cmd = [
        "gog", "sheets", "update",
        SHEET_ID, range_str,
        "--values-json", json.dumps(rows),
        "-a", SHEET_ACCOUNT,
        "--input", "USER_ENTERED",
        "--json",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            log.error(f"Forecast sheet batch write error: {result.stderr[:200]}")
            return 0
        data = json.loads(result.stdout)
        written = data.get("updatedRows", 0)
        log.info(f"Forecast sheet: wrote {written}/{len(rows)} rows")
        return written
    except Exception as e:
        log.error(f"Forecast sheet: batch write failed: {e}")
        return 0


def _get_next_forecast_row() -> int:
    """Find next empty data row in Forecasts tab — never row 1."""
    cmd = ["gog", "sheets", "read", SHEET_ID, "📋 Forecasts!A2:A600",
           "-a", SHEET_ACCOUNT, "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if result.returncode != 0:
        return 2
    try:
        rows = json.loads(result.stdout).get("values", []) or []
    except Exception:
        return 2
    if not rows:
        return 2
    for i, row in enumerate(rows):
        if not row or not str(row[0]).strip():
            return i + 2
    return len(rows) + 2


def _get_next_inbox_row() -> int:
    """Find next empty data row in Inbox tab — never row 1."""
    cmd = ["gog", "sheets", "read", SHEET_ID, "📥 Inbox!A2:A600",
           "-a", SHEET_ACCOUNT, "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if result.returncode != 0:
        return 2
    try:
        rows = json.loads(result.stdout).get("values", []) or []
    except Exception:
        return 2
    if not rows:
        return 2
    for i, row in enumerate(rows):
        if not row or not str(row[0]).strip():
            return i + 2
    return len(rows) + 2
