"""
Yukon — NASA Acquisition Forecast portal adapter
Downloads and parses the NASA Acquisition Forecast Excel spreadsheet.
Filters by profile NAICS codes and scrape_keywords.
"""

import logging
import tempfile
from datetime import datetime, timezone
from typing import Dict, List

import requests

log = logging.getLogger(__name__)

FORECAST_URL = "https://www.hq.nasa.gov/office/procurement/forecast/AcqForecastNew.xlsx"
FORECAST_PAGE = "https://www.hq.nasa.gov/office/procurement/forecast/NAF.html"

# Column indices (0-based) in the Excel sheet
COL_BUYING_OFFICE = 0
COL_ACQUISITION_STATUS = 3
COL_AWARDED_OR_WITHDRAWN = 4
COL_SOURCE_ID = 6
COL_TITLE = 7
COL_NAICS = 12
COL_ANTICIPATED_FY_AWARD = 20
COL_ANTICIPATED_QTR_AWARD = 21
COL_ESTIMATED_VALUE = 23
COL_SET_ASIDE = 25
COL_SUMMARY = 29
COL_QTR_SOL_RELEASE = 34
COL_FY_SOL_RELEASE = 35
COL_TYPE_OF_REQUIREMENT = 38
COL_DESCRIPTION = 43


def fetch(
    profile_naics: List[str] = None,
    profile_scrape_keywords: List[str] = None,
    api_key: str = None,
    **kwargs,
) -> List[Dict]:
    """
    Download NASA Acquisition Forecast spreadsheet and return matching opps.

    Args:
        profile_naics: NAICS codes to filter on
        profile_scrape_keywords: Keywords to match in title/summary/description
        api_key: unused, kept for adapter interface consistency

    Returns:
        List of normalized opportunity dicts with source_type="forecast"
    """
    import openpyxl

    log.info("NASA Forecast: downloading spreadsheet...")

    try:
        resp = requests.get(FORECAST_URL, timeout=60)
        resp.raise_for_status()
    except Exception as e:
        log.error(f"NASA Forecast: download failed: {e}")
        return []

    # Write to temp file and parse with openpyxl
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=True) as tmp:
        tmp.write(resp.content)
        tmp.flush()

        try:
            wb = openpyxl.load_workbook(tmp.name, read_only=True, data_only=True)
            ws = wb.active
        except Exception as e:
            log.error(f"NASA Forecast: failed to parse Excel: {e}")
            return []

        rows = list(ws.iter_rows(min_row=2, values_only=True))  # skip header
        wb.close()

    log.info(f"NASA Forecast: {len(rows)} data rows loaded")

    naics_set = set(str(n).strip() for n in (profile_naics or []))
    keywords_lower = [kw.lower() for kw in (profile_scrape_keywords or [])]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    opps = []
    skipped_status = 0
    skipped_filter = 0

    for row in rows:
        # Safely get cell value with bounds checking
        def cell(idx):
            if idx < len(row) and row[idx] is not None:
                return str(row[idx]).strip()
            return ""

        # Skip awarded/withdrawn rows
        acq_status = cell(COL_ACQUISITION_STATUS).lower()
        if acq_status in ("awarded", "withdrawn"):
            skipped_status += 1
            continue

        awarded_withdrawn = cell(COL_AWARDED_OR_WITHDRAWN)
        if awarded_withdrawn and awarded_withdrawn.lower() != "n/a":
            skipped_status += 1
            continue

        source_id = cell(COL_SOURCE_ID)
        if not source_id:
            continue

        title = cell(COL_TITLE)
        naics = cell(COL_NAICS)
        summary = cell(COL_SUMMARY)
        description = cell(COL_DESCRIPTION)
        set_aside = cell(COL_SET_ASIDE)
        buying_office = cell(COL_BUYING_OFFICE)
        est_value = cell(COL_ESTIMATED_VALUE)
        fy_award = cell(COL_ANTICIPATED_FY_AWARD)
        qtr_award = cell(COL_ANTICIPATED_QTR_AWARD)
        fy_sol = cell(COL_FY_SOL_RELEASE)
        qtr_sol = cell(COL_QTR_SOL_RELEASE)
        req_type = cell(COL_TYPE_OF_REQUIREMENT) or "Forecast"

        # Filter by NAICS
        naics_match = not naics_set or naics in naics_set
        # Filter by keywords in title + summary + description
        searchable = f"{title} {summary} {description}".lower()
        keyword_match = not keywords_lower or any(kw in searchable for kw in keywords_lower)

        if not naics_match and not keyword_match:
            skipped_filter += 1
            continue

        opps.append({
            "id": f"nasa-forecast-{source_id}",
            "title": title,
            "portal": "NASA Forecast",
            "type": req_type,
            "department": buying_office,
            "naics_code": naics,
            "set_aside": set_aside,
            "description": summary or description,
            "posted_date": today,
            "due_date": "",
            "url": FORECAST_PAGE,
            "source_type": "forecast",
            "forecast_fy": fy_award,
            "forecast_quarter": qtr_award,
            "sol_release_fy": fy_sol,
            "sol_release_quarter": qtr_sol,
            "estimated_value": est_value,
        })

    log.info(
        f"NASA Forecast: {len(opps)} matching opps "
        f"(skipped {skipped_status} awarded/withdrawn, {skipped_filter} filtered out)"
    )
    return opps
