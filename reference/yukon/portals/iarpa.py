"""
Yukon — IARPA portal adapter
Scrapes open opportunities from iarpa.gov across 4 pages:
  - Open R&D Opportunities (BAAs/CSOs)
  - Requests for Information (RFIs)
  - Proposers Days
  - Seedlings

IARPA uses Akamai CDN which blocks plain HTTP requests (403), so we use
Playwright (headless Chromium) to render the pages. All 4 pages are
server-rendered Joomla with <table class="iarpa-table"> structures.
"""

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urljoin

log = logging.getLogger(__name__)

BASE_URL = "https://www.iarpa.gov"

PAGES = [
    {
        "path": "/engage-with-us/open-r-d-opportunities",
        "type": "Open R&D Opportunity (BAA)",
        "open_table": "rs",
        "closed_table": None,
    },
    {
        "path": "/engage-with-us/rfi",
        "type": "Request for Information (RFI)",
        "open_table": "rs",
        "closed_table": "rfis_closed",
    },
    {
        "path": "/engage-with-us/proposers-days",
        "type": "Proposers Day",
        "open_table": "pds_open",
        "closed_table": "pds_closed",
    },
    {
        "path": "/engage-with-us/seedlings",
        "type": "Seedling",
        "open_table": "rs",
        "closed_table": None,
    },
]

NO_RESULTS_PHRASES = [
    "sorry, there are no",
    "no open r&d",
    "no open solicitations",
    "no open challenges",
    "no results",
    "your search provided no results",
]


def fetch(**kwargs) -> List[Dict]:
    """Scrape all 4 IARPA engagement pages. Returns normalized opportunity dicts."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.error("playwright not installed — run: pip install playwright && playwright install chromium")
        return []

    all_opps = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for page_config in PAGES:
            url = BASE_URL + page_config["path"]
            opp_type = page_config["type"]
            log.info(f"IARPA: fetching {opp_type} from {url}")

            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                opps = _parse_table(page, page_config)
                log.info(f"IARPA: found {len(opps)} open {opp_type} items")
                all_opps.extend(opps)

            except Exception as e:
                log.error(f"IARPA: error fetching {opp_type}: {e}")
                continue

        browser.close()

    log.info(f"IARPA: total {len(all_opps)} open opportunities across all pages")
    return all_opps


def _parse_table(page, page_config: Dict) -> List[Dict]:
    """Parse the open-items table from an IARPA page."""
    results = []
    table_id = page_config["open_table"]
    opp_type = page_config["type"]

    table = page.query_selector(f"table#{table_id}")
    if not table:
        log.debug(f"IARPA: no table#{table_id} found on {page_config['path']}")
        return []

    caption = table.query_selector("caption")
    if caption:
        caption_text = caption.inner_text().lower()
        if any(phrase in caption_text for phrase in NO_RESULTS_PHRASES):
            log.debug(f"IARPA: {opp_type} table is empty (caption: {caption_text.strip()[:60]})")
            return []

    rows = table.query_selector_all("tbody tr")
    for row in rows:
        cells = row.query_selector_all("td")
        if not cells:
            continue

        opp = _parse_row(cells, opp_type, page_config)
        if opp:
            results.append(opp)

    return results


def _parse_row(cells, opp_type: str, page_config: Dict) -> Optional[Dict]:
    """Parse a single table row into an opportunity dict."""
    if len(cells) < 1:
        return None

    name_cell = cells[0]
    title = name_cell.inner_text().strip()
    if not title or len(title) < 3:
        return None

    # Check for "no results" text in the row itself
    if any(phrase in title.lower() for phrase in NO_RESULTS_PHRASES):
        return None

    # Extract link (usually to SAM.gov or detail page)
    link_el = None
    for cell in cells:
        link_el = cell.query_selector("a[href]")
        if link_el:
            break

    url = ""
    ref_number = ""
    due_date = ""
    if link_el:
        url = link_el.get_attribute("href") or ""
        link_text = link_el.inner_text().strip()
        if link_text != title:
            ref_number = link_text

    # Second cell is usually the reference number or date
    if len(cells) >= 2:
        second_text = cells[1].inner_text().strip()
        if not ref_number and re.match(r"IARPA[-\s]", second_text):
            ref_number = second_text
        elif re.match(r"\d{4}-\d{2}-\d{2}", second_text):
            due_date = second_text
        else:
            if not ref_number:
                ref_number = second_text

    # For seedlings, cells may include: Name, Description, Performer(s), Publications
    description = ""
    if page_config["path"] == "/engage-with-us/seedlings" and len(cells) >= 2:
        description = cells[1].inner_text().strip()[:1000]

    opp_id = "iarpa-" + hashlib.md5(f"{title}-{ref_number}".encode()).hexdigest()[:12]

    return {
        "id": opp_id,
        "title": f"{title}" + (f" ({ref_number})" if ref_number and ref_number != title else ""),
        "url": url or f"{BASE_URL}{page_config['path']}",
        "portal": "IARPA",
        "naics_code": "",
        "set_aside": "",
        "posted_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "due_date": due_date,
        "description": description or f"IARPA {opp_type}: {title}",
        "type": opp_type,
        "department": "Office of the Director of National Intelligence (ODNI) — IARPA",
    }
