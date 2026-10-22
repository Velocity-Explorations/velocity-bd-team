"""
Yukon — Space Florida portal adapter
Scrapes active RFPs from spaceflorida.gov/solicitations

Space Florida is Florida's Aerospace Finance and Development Authority.
Their solicitations page is publicly accessible clean HTML — no login required.
Covers KSC/Cape Canaveral area aerospace, spaceport, and tech opportunities.
"""

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

BASE_URL = "https://www.spaceflorida.gov"
SOLICITATIONS_URL = f"{BASE_URL}/solicitations"
REQUEST_TIMEOUT = 30

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

SKIP_PHRASES = [
    "awarded rfp",
    "awarded rfq",
    "awarded rfb",
    "awarded to",
]

# Addenda, notices, and attachments — not standalone opportunities
ATTACHMENT_PHRASES = [
    "addendum",
    "notice of intent",
    "presentation agenda",
    "questions and responses",
    "q&a",
    "amendment",
    "modification",
]


def fetch(profile_keywords: List[str] = None, **kwargs) -> List[Dict]:
    """
    Scrape active RFPs from Space Florida.
    Returns list of normalized opportunity dicts.
    """
    try:
        log.info("Space Florida: fetching solicitations page")
        resp = requests.get(SOLICITATIONS_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.error(f"Space Florida: fetch error: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    opps = _parse_solicitations(soup)
    # Filter out addenda, notices, and attachments — not standalone opportunities
    opps = [o for o in opps if not any(p in o["title"].lower() for p in ATTACHMENT_PHRASES)]
    log.info(f"Space Florida: found {len(opps)} active solicitations (after filtering attachments)")
    return opps


def _parse_solicitations(soup: BeautifulSoup) -> List[Dict]:
    """Parse Space Florida solicitations page."""
    results = []
    seen_ids = set()

    content = soup.find("main") or soup.find("div", class_=re.compile(r"content|entry|post")) or soup

    # Find the "Active RFPs" section
    # Structure: h3 "Active RFPs" → table or list of RFPs with title, published, due date
    active_section = None
    for heading in content.find_all(["h2", "h3", "h4"]):
        if "active" in heading.get_text(strip=True).lower():
            active_section = heading
            break

    if not active_section:
        log.warning("Space Florida: could not find Active RFPs section")
        # Fall back to parsing full page text
        return _parse_from_text(soup)

    # Collect all content after "Active RFPs" until "Awarded RFPs"
    entries = []
    node = active_section.find_next_sibling()
    while node:
        text = node.get_text(" ", strip=True)
        text_lower = text.lower()

        # Stop when we hit the awarded section
        if any(phrase in text_lower for phrase in SKIP_PHRASES):
            break

        if text and len(text) > 10:
            entries.append((node, text))
        node = node.find_next_sibling()

    # Extract individual RFPs from entries
    # The page has a table structure: Proposal Title | Notes | Published | Due By
    for node, text in entries:
        # Try table rows first
        rows = node.find_all("tr") if node.name == "table" else []
        if not rows and node.name != "table":
            rows_parent = node.find("table")
            if rows_parent:
                rows = rows_parent.find_all("tr")

        if rows:
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue
                title = cells[0].get_text(strip=True)
                if not title or len(title) < 10:
                    continue
                if any(p in title.lower() for p in ["proposal title", "additional notes"]):
                    continue

                published = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                due = cells[3].get_text(strip=True) if len(cells) > 3 else ""

                opp_id = "spaceflorida-" + hashlib.md5(title.encode()).hexdigest()[:12]
                if opp_id in seen_ids:
                    continue
                seen_ids.add(opp_id)

                # Find link if any
                link = cells[0].find("a", href=True)
                url = (BASE_URL + link["href"]) if link and not link["href"].startswith("http") else (link["href"] if link else SOLICITATIONS_URL)

                results.append(_build_opp(opp_id, title, url, published, due))
        else:
            # No table — try to extract from text directly
            pass

    # If table parsing got nothing, fall back to text parsing
    if not results:
        results = _parse_from_text(soup)

    return results


def _parse_from_text(soup: BeautifulSoup) -> List[Dict]:
    """Fallback: parse solicitations from raw page text."""
    results = []
    seen_ids = set()

    content = soup.find("main") or soup
    full_text = content.get_text("\n", strip=True)
    lines = [l.strip() for l in full_text.split("\n") if l.strip()]

    in_active = False
    i = 0
    while i < len(lines):
        line = lines[i]

        # Start capturing after "Active RFPs"
        if "active rfp" in line.lower() or "active rfq" in line.lower():
            in_active = True
            i += 1
            continue

        # Stop at awarded section
        if in_active and ("awarded rfp" in line.lower() or "awarded rfq" in line.lower() or "awarded rfb" in line.lower()):
            break

        if not in_active:
            i += 1
            continue

        # Skip header rows and short lines
        if len(line) < 15 or line in ["Proposal Title", "Additional Notes", "Published", "Due By", "Awarded To"]:
            i += 1
            continue

        # Looks like a title — check if next lines have dates
        published = ""
        due = ""
        for j in range(i + 1, min(i + 5, len(lines))):
            l = lines[j]
            if re.match(r'\w+ \d+, \d{4}', l) or re.match(r'\w+ \d{4}', l):
                if not published:
                    published = l
                elif not due:
                    due = l
                    break

        if len(line) > 15:
            opp_id = "spaceflorida-" + hashlib.md5(line.encode()).hexdigest()[:12]
            if opp_id not in seen_ids:
                seen_ids.add(opp_id)
                results.append(_build_opp(opp_id, line, SOLICITATIONS_URL, published, due))

        i += 1

    return results


def _build_opp(opp_id: str, title: str, url: str, published: str, due: str) -> Dict:
    """Build a normalized opportunity dict."""
    return {
        "id": opp_id,
        "title": title,
        "url": url,
        "portal": "Space Florida",
        "naics_code": "",
        "set_aside": "",
        "posted_date": _normalize_date(published) or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "due_date": _normalize_date(due),
        "description": f"Space Florida solicitation: {title}. Cape Canaveral/KSC area aerospace and spaceport opportunity.",
        "type": _infer_type(title),
        "department": "Space Florida — Florida Aerospace Finance and Development Authority",
    }


def _normalize_date(date_str: str) -> str:
    """Normalize various date formats to YYYY-MM-DD."""
    if not date_str:
        return ""
    formats = [
        "%B %d, %Y",   # July 10, 2025
        "%B %Y",       # July 2025
        "%m/%d/%Y",    # 07/10/2025
        "%Y-%m-%d",    # 2025-07-10
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str[:20]


def _infer_type(title: str) -> str:
    """Infer solicitation type from title prefix."""
    title_upper = title.upper()
    if title_upper.startswith("RFP") or "REQUEST FOR PROPOSAL" in title_upper:
        return "RFP"
    if title_upper.startswith("RFQ") or "REQUEST FOR QUALIF" in title_upper:
        return "RFQ"
    if title_upper.startswith("RFB") or "REQUEST FOR BID" in title_upper:
        return "RFB"
    if title_upper.startswith("RFI") or "REQUEST FOR INFORMATION" in title_upper:
        return "RFI"
    return "Solicitation"
