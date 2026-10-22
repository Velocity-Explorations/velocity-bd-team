"""
Yukon — DIU portal adapter
Scrapes open solicitations from diu.mil/work-with-us/open-solicitations

DIU posts Commercial Solutions Openings (CSOs) via OT authority.
The page body contains full problem statements in raw HTML (partially JS-injected).
We fetch the page, extract all text, then segment by solicitation title.
"""

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

BASE_URL = "https://www.diu.mil"
SOLICITATIONS_URL = f"{BASE_URL}/work-with-us/open-solicitations"
REQUEST_TIMEOUT = 30

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

# Known section headers to stop at
STOP_PHRASES = [
    "pathways through",
    "open challenges",
    "open solicitations",
    "faqs",
    "find the right path",
    "how we work",
    "common questions",
    "sorry, there are no",
]


def fetch(profile_keywords: List[str] = None, **kwargs) -> List[Dict]:
    """Scrape open DIU solicitations. Returns normalized opportunity dicts."""
    try:
        log.info("DIU: fetching open solicitations page")
        resp = requests.get(SOLICITATIONS_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.error(f"DIU: fetch error: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    opps = _parse_solicitations(soup)
    log.info(f"DIU: found {len(opps)} open solicitations")
    return opps


def _parse_solicitations(soup: BeautifulSoup) -> List[Dict]:
    """
    Extract solicitations from the DIU open-solicitations page.
    Strategy: find h4 tags that are solicitation titles, then grab
    all the page text between them as the body.
    """
    results = []
    seen_ids = set()

    content = soup.find("main") or soup

    # Get full page text as one string for body extraction
    full_text = content.get_text(" ", strip=True)

    # Find solicitation h4 titles — these are the real entries
    # (not section headers like "Open Solicitations —" which are h5)
    solicitation_headers = []
    for tag in content.find_all("h4"):
        title = tag.get_text(strip=True)
        if not title or len(title) < 5:
            continue
        title_lower = title.lower()
        if any(phrase in title_lower for phrase in STOP_PHRASES):
            continue
        # Skip obvious subsection headers
        if title in ["Training Materials", "FAQs", "LOE 1", "LOE 2"]:
            continue
        solicitation_headers.append(title)

    if not solicitation_headers:
        log.warning("DIU: no solicitation headers found on page")
        return []

    # For each solicitation title, extract its body from full_text
    for i, title in enumerate(solicitation_headers):
        # Find where this title appears in the full text
        title_pos = full_text.find(title)
        if title_pos == -1:
            continue

        # Body starts after the title
        body_start = title_pos + len(title)

        # Body ends at the next solicitation title or end of text
        if i + 1 < len(solicitation_headers):
            next_title = solicitation_headers[i + 1]
            next_pos = full_text.find(next_title, body_start)
            body_text = full_text[body_start:next_pos] if next_pos != -1 else full_text[body_start:]
        else:
            body_text = full_text[body_start:]

        body_text = " ".join(body_text.split())  # normalize whitespace

        if len(body_text) < 50:
            continue

        # Extract due date
        due_date = _extract_date(body_text)

        # Clean description — remove the due date header line
        description = re.sub(r'Responses? Due By\s+[\d\-:\s]+US/\w+ Time', '', body_text)
        description = " ".join(description.split())[:1000]

        opp_id = "diu-" + hashlib.md5(title.encode()).hexdigest()[:12]
        if opp_id in seen_ids:
            continue
        seen_ids.add(opp_id)

        results.append({
            "id": opp_id,
            "title": title,
            "url": SOLICITATIONS_URL,
            "portal": "DIU",
            "naics_code": "",
            "set_aside": "",
            "posted_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "due_date": due_date,
            "description": description,
            "type": "DIU Commercial Solutions Opening (CSO)",
            "department": "Defense Innovation Unit",
        })

    return results


def _extract_date(text: str) -> str:
    """Extract due date from DIU solicitation text."""
    # Format: "Responses Due By 2026-03-24 23:59:59 US/Eastern Time"
    match = re.search(r'[Rr]esponses?\s+[Dd]ue\s+[Bb]y\s+(\d{4}-\d{2}-\d{2})', text)
    if match:
        return match.group(1)
    # Fallback: any ISO date
    match = re.search(r'(\d{4}-\d{2}-\d{2})', text)
    if match:
        return match.group(1)
    return ""
