"""
Yukon — DOE Science SBIR portal adapter
Scrapes funding opportunities from science.osti.gov/sbir/Funding-Opportunities.

The page has structured HTML tables (class="funding_details") with Phase I and
Phase II timelines, including FOA document numbers, key dates, and PDF links.
"""

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

BASE_URL = "https://science.osti.gov"
FUNDING_URL = f"{BASE_URL}/sbir/Funding-Opportunities"
REQUEST_TIMEOUT = 30

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def fetch(**kwargs) -> List[Dict]:
    """Scrape DOE SBIR funding opportunities. Returns normalized opportunity dicts."""
    try:
        log.info("DOE SBIR: fetching funding opportunities page")
        resp = requests.get(FUNDING_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.error(f"DOE SBIR: fetch error: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    opps = _parse_funding_tables(soup)
    log.info(f"DOE SBIR: found {len(opps)} funding opportunities")
    return opps


def _parse_funding_tables(soup: BeautifulSoup) -> List[Dict]:
    """Parse the funding_details tables for FOA entries."""
    results = []
    seen_ids = set()

    tables = soup.find_all("table", class_="funding_details")
    for table in tables:
        prev_header = table.find_previous(["h2", "h3", "h4"])
        section_label = prev_header.get_text(strip=True) if prev_header else "DOE SBIR"

        rows = table.find_all("tr")
        current_phase = ""
        current_release = ""
        dates = {}

        for row in rows:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue

            row_text = " ".join(c.get_text(strip=True) for c in cells)

            # Detect phase from header rows
            if "phase i" in row_text.lower() and "release" not in row_text.lower():
                current_phase = "Phase I"
                continue
            if "phase ii" in row_text.lower() and "release" not in row_text.lower():
                current_phase = "Phase II"
                continue

            # Detect release columns from header
            header_cells = row.find_all("th")
            if header_cells and any("release" in c.get_text(strip=True).lower() for c in header_cells):
                continue

            # Look for FOA document links
            for cell in cells:
                foa_links = cell.find_all("a", href=re.compile(r"FOA|foa"))
                for link in foa_links:
                    foa_num = link.get_text(strip=True)
                    if foa_num.lower() in ("slides", "webinar", "video"):
                        continue
                    foa_url = link.get("href", "")
                    if foa_url and not foa_url.startswith("http"):
                        foa_url = urljoin(BASE_URL, foa_url)

                    if not foa_num or foa_num in seen_ids:
                        continue
                    seen_ids.add(foa_num)

                    # Extract dates from surrounding rows
                    due_date = _find_date_in_table(table, "application")
                    nofo_date = _find_date_in_table(table, "nofo issued")

                    opp_id = "doe-sbir-" + hashlib.md5(foa_num.encode()).hexdigest()[:12]

                    results.append({
                        "id": opp_id,
                        "title": f"DOE SBIR/STTR {current_phase}: {foa_num}",
                        "url": foa_url or FUNDING_URL,
                        "portal": "DOE Science SBIR",
                        "naics_code": "",
                        "set_aside": "SB",
                        "posted_date": nofo_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "due_date": due_date,
                        "description": f"DOE Office of Science SBIR/STTR {current_phase} funding opportunity. FOA: {foa_num}. Section: {section_label}.",
                        "type": f"DOE SBIR/STTR {current_phase}",
                        "department": "Department of Energy — Office of Science",
                    })

            # Also look for topic PDF links
            for cell in cells:
                topic_links = cell.find_all("a", href=re.compile(r"Topics.*\.pdf|topics.*\.pdf", re.IGNORECASE))
                for link in topic_links:
                    text = link.get_text(strip=True)
                    href = link.get("href", "")
                    if href and not href.startswith("http"):
                        href = urljoin(BASE_URL, href)
                    topic_id = "doe-topics-" + hashlib.md5(href.encode()).hexdigest()[:12]
                    if topic_id in seen_ids:
                        continue
                    seen_ids.add(topic_id)

                    results.append({
                        "id": topic_id,
                        "title": f"DOE SBIR/STTR {current_phase} Topic List: {text}",
                        "url": href or FUNDING_URL,
                        "portal": "DOE Science SBIR",
                        "naics_code": "",
                        "set_aside": "SB",
                        "posted_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "due_date": "",
                        "description": f"DOE SBIR/STTR topic list document for {current_phase}. Section: {section_label}.",
                        "type": f"DOE SBIR/STTR Topic List",
                        "department": "Department of Energy — Office of Science",
                    })

    return results


def _find_date_in_table(table, label: str) -> str:
    """Search a table for a row containing a label and extract a date from it."""
    for row in table.find_all("tr"):
        row_text = row.get_text(" ", strip=True).lower()
        if label in row_text:
            date_match = re.search(r"(\w+ \d{1,2},? \d{4})", row.get_text(" ", strip=True))
            if date_match:
                return _parse_date(date_match.group(1))
    return ""


def _parse_date(text: str) -> str:
    """Parse various date formats to YYYY-MM-DD."""
    text = text.strip().replace(",", "")
    for fmt in ["%B %d %Y", "%b %d %Y", "%m/%d/%Y", "%Y-%m-%d"]:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""
