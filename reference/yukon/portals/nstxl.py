"""
Yukon — NSTXL portal adapter
Scrapes open opportunities from nstxl.org/nstxl-opportunities/

NSTXL manages OTA vehicles: S2MARTS, SpEC, Microelectronics Commons.
The public listing page renders all opportunities in one request (JS-filtered
client-side). We parse the listing, then fetch individual /opportunity/ pages
in parallel for any entry that has a direct link — giving us richer data
(title, due date, full description). Entries with no direct link use the
listing blurb only.
"""

import hashlib
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

BASE_URL = "https://nstxl.org"
OPPORTUNITIES_URL = f"{BASE_URL}/nstxl-opportunities/"
REQUEST_TIMEOUT = 30
MAX_DETAIL_WORKERS = 8  # parallel fetches for individual opp pages

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

VEHICLE_KEYWORDS = {
    "s2marts": "S2MARTS OTA",
    "spec": "SpEC OTA",
    "microelectronics commons": "Microelectronics Commons OTA",
}

SKIP_PHRASES = [
    "has been canceled",
    "has been awarded",
    "award notice",
    "now closed",
    "no longer available",
    "is now closed",
]

AGENCIES = [
    "Defense Advanced Research Projects Agency",
    "Air Force Research Laboratory",
    "Army Research Laboratory",
    "Space Systems Command",
    "Naval Surface Warfare Center",
    "Joint Hypersonics Transition Office",
    "Department of War",
    "Office of the Under Secretary of War",
    "U.S. Special Operations Command",
    "Test Resource Management Center",
    "Microelectronics Commons",
    "Department of the Navy",
    "Department of the Army",
    "Department of the Air Force",
]


def fetch(profile_keywords: List[str] = None, **kwargs) -> List[Dict]:
    """
    Scrape NSTXL opportunities.
    1. Fetch the single listing page
    2. Parse all opportunity blurbs + extract any /opportunity/ links
    3. In parallel, fetch individual pages for linked opps (richer data)
    4. Return combined results
    """
    try:
        log.info("NSTXL: fetching opportunities listing page")
        resp = requests.get(OPPORTUNITIES_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.error(f"NSTXL: fetch error: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    blurbs = _parse_listing(soup)

    # Separate into linked (has individual page) and unlinked
    linked = [o for o in blurbs if o["url"] != OPPORTUNITIES_URL]
    unlinked = [o for o in blurbs if o["url"] == OPPORTUNITIES_URL]

    log.info(f"NSTXL: {len(blurbs)} blurbs parsed — {len(linked)} have direct links, {len(unlinked)} listing-only")

    # Fetch individual pages in parallel for linked opportunities
    enriched = []
    if linked:
        with ThreadPoolExecutor(max_workers=MAX_DETAIL_WORKERS) as executor:
            futures = {
                executor.submit(_fetch_detail_page, opp): opp
                for opp in linked
            }
            for future in as_completed(futures):
                original = futures[future]
                try:
                    result = future.result()
                    enriched.append(result if result else original)
                except Exception as e:
                    log.warning(f"NSTXL: detail fetch error for {original['url']}: {e}")
                    enriched.append(original)

    all_opps = enriched + unlinked
    log.info(f"NSTXL: {len(all_opps)} total opportunities")
    return all_opps


def _parse_listing(soup: BeautifulSoup) -> List[Dict]:
    """Parse all opportunity blurbs from the NSTXL listing page."""
    results = []
    seen_hashes = set()

    content = soup.find("main") or soup.find("div", class_=re.compile(r"entry|content|post-content"))
    if not content:
        content = soup

    for p in content.find_all("p"):
        text = p.get_text(" ", strip=True)

        if len(text) < 80:
            continue

        text_lower = text.lower()
        if any(phrase in text_lower for phrase in SKIP_PHRASES):
            continue
        if any(skip in text for skip in ["Log In", "Log Out", "Dashboard", "Skip to"]):
            continue

        content_hash = hashlib.md5(text[:150].encode()).hexdigest()[:12]
        if content_hash in seen_hashes:
            continue
        seen_hashes.add(content_hash)

        opp_id = "nstxl-" + content_hash

        # Title: first sentence up to 120 chars
        first_sentence = re.split(r'(?<=[.!?])\s', text)[0]
        title = first_sentence[:120] if len(first_sentence) <= 120 else text[:117] + "..."

        # Look for a direct /opportunity/ link on this paragraph or its parent
        url = OPPORTUNITIES_URL
        link = p.find("a", href=re.compile(r"/opportunity/"))
        if not link and p.parent:
            link = p.parent.find("a", href=re.compile(r"/opportunity/"))
        if link:
            href = link["href"]
            url = href if href.startswith("http") else BASE_URL + href

        results.append({
            "id": opp_id,
            "title": title,
            "url": url,
            "portal": "NSTXL",
            "naics_code": "",
            "set_aside": "",
            "posted_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "due_date": _extract_date(text),
            "description": text[:800],
            "type": _extract_vehicle(text),
            "department": _extract_agency(text),
        })

    return results


def _fetch_detail_page(opp: Dict) -> Optional[Dict]:
    """
    Fetch an individual NSTXL opportunity page and enrich the opp dict.
    Returns None if the opp is closed/canceled (should be filtered out).
    """
    url = opp["url"]
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.debug(f"NSTXL: detail page error {url}: {e}")
        return opp  # fall back to listing blurb

    soup = BeautifulSoup(resp.text, "html.parser")

    # Get full page text
    content_el = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile(r"entry|content"))
    body_text = content_el.get_text(" ", strip=True) if content_el else soup.get_text(" ", strip=True)
    body_lower = body_text.lower()

    # Skip if closed/canceled
    for phrase in SKIP_PHRASES:
        if phrase in body_lower:
            log.debug(f"NSTXL: skipping closed opp: {opp['title'][:50]}")
            return None

    # Richer title from h1
    title_el = soup.find("h1")
    title = title_el.get_text(strip=True) if title_el else opp["title"]

    # Better description — clean up whitespace
    description = " ".join(body_text.split())[:1000]

    # Better due date from full page text
    due_date = _extract_date(body_text) or opp["due_date"]

    # Better department
    department = _extract_agency(body_text) or opp["department"]

    return {
        **opp,
        "title": title,
        "description": description,
        "due_date": due_date,
        "department": department,
        "type": _extract_vehicle(body_text) or opp["type"],
    }


def _extract_date(text: str) -> str:
    patterns = [
        r"[Ss]olutions?\s+due\s+(?:by\s+)?(\d{1,2}\s+\w+\s+\d{4})",
        r"[Dd]ue\s+(?:by\s+)?(\d{1,2}\s+\w+\s+\d{4})",
        r"[Dd]ue\s*[:\-]\s*(\w+\s+\d{1,2},?\s+\d{4})",
        r"[Ss]ubmit.*?by\s+(\w+\s+\d{1,2},?\s+\d{4})",
        r"[Dd]eadline[:\s]+(\w+\s+\d{1,2},?\s+\d{4})",
        r"[Rr]esponses?\s+due[:\s]+(\w+\s+\d{1,2},?\s+\d{4})",
        r"[Pp]roposals?\s+due[:\s]+(\w+\s+\d{1,2},?\s+\d{4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _extract_vehicle(text: str) -> str:
    text_lower = text.lower()
    for keyword, label in VEHICLE_KEYWORDS.items():
        if keyword in text_lower:
            return label
    return "OTA Opportunity"


def _extract_agency(text: str) -> str:
    for agency in AGENCIES:
        if agency in text:
            return agency
    return "NSTXL"
