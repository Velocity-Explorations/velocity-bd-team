"""
Yukon — Space Force / SpaceWERX portal adapter

my.spaceforce.mil requires authentication (Keycloak SSO) and is not publicly
accessible. Instead we scrape SpaceWERX (spacewerx.us), the Space Force
innovation arm, which posts SBIR/STTR opportunities on their public site.

SpaceWERX solicitations are also included on the AFWERX get-funded page
(same SBIR/STTR program), so this adapter focuses on SpaceWERX-specific
content like the SSC Front Door and Space-focused STRATFI notices.
"""

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

SPACEWERX_URL = "https://spacewerx.us/"
REQUEST_TIMEOUT = 30

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

RELEVANT_KEYWORDS = [
    "sbir", "sttr", "stratfi", "tacfi", "solicitation", "opportunity",
    "funding", "challenge", "proposal", "award", "phase",
]


def fetch(**kwargs) -> List[Dict]:
    """Scrape SpaceWERX for Space Force opportunities."""
    try:
        log.info("Space Force/SpaceWERX: fetching main page")
        resp = requests.get(SPACEWERX_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.error(f"SpaceWERX: fetch error: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    opps = _parse_opportunities(soup)
    log.info(f"Space Force/SpaceWERX: found {len(opps)} opportunities")
    return opps


def _parse_opportunities(soup: BeautifulSoup) -> List[Dict]:
    """Extract opportunity-related content from SpaceWERX."""
    results = []
    seen_ids = set()

    # Find all links that reference opportunities, SBIR, challenges, etc.
    links = soup.find_all("a", href=True)
    for link in links:
        text = link.get_text(strip=True)
        href = link["href"]
        if not text or len(text) < 10:
            continue

        text_lower = text.lower()
        href_lower = href.lower()

        if not any(kw in text_lower or kw in href_lower for kw in RELEVANT_KEYWORDS):
            continue

        # Skip nav-only links, footers, etc.
        if text_lower in ["sbir/sttr phase iii", "equal opportunity", "no fear act"]:
            continue

        opp_id = "spacewerx-" + hashlib.md5(f"{text}-{href}".encode()).hexdigest()[:12]
        if opp_id in seen_ids:
            continue
        seen_ids.add(opp_id)

        full_url = href if href.startswith("http") else f"https://spacewerx.us{href}"

        # Try to get surrounding context for description
        parent = link.find_parent(["div", "section", "li"])
        description = parent.get_text(" ", strip=True)[:500] if parent else text

        results.append({
            "id": opp_id,
            "title": text[:200],
            "url": full_url,
            "portal": "Space Force",
            "naics_code": "",
            "set_aside": "",
            "posted_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "due_date": "",
            "description": description,
            "type": "SpaceWERX Opportunity",
            "department": "United States Space Force — SpaceWERX",
        })

    return results
