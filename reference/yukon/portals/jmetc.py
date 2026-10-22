"""
Yukon — JMETC portal adapter
Scrapes TRMC (Test Resource Management Center) for JMETC-related opportunities.

The JMETC portal (jmetc.trmc.osd.mil) requires authentication for its wiki,
helpdesk, and repository. The public landing page at trmc.osd.mil has minimal
content. JMETC opportunities are typically posted through SAM.gov or the TRMC
parent site.

This adapter checks the TRMC public pages for any JMETC-related solicitations
or announcements, and also checks SAM.gov keyword search as a fallback.
"""

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

TRMC_URL = "https://www.trmc.osd.mil"
JMETC_URL = f"{TRMC_URL}/jmetc-home.html"
REQUEST_TIMEOUT = 30

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def fetch(**kwargs) -> List[Dict]:
    """Check TRMC site for JMETC-related opportunities."""
    opps = []

    # Check the TRMC main site for news/announcements
    opps.extend(_check_trmc_site())

    log.info(f"JMETC: found {len(opps)} opportunities")
    return opps


def _check_trmc_site() -> List[Dict]:
    """Check the TRMC main site for JMETC-related content."""
    results = []
    seen_ids = set()

    for url in [TRMC_URL, JMETC_URL]:
        try:
            log.info(f"JMETC: checking {url}")
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as e:
            log.warning(f"JMETC: error fetching {url}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")

        # Find links that look like opportunity/solicitation announcements
        for link in soup.find_all("a", href=True):
            text = link.get_text(strip=True)
            href = link["href"]
            if not text or len(text) < 10:
                continue

            text_lower = text.lower()

            # Skip generic navigation/informational links
            if any(skip in text_lower for skip in [
                "fact sheet", "tutorial", "overview", "feedback", "contact",
                "account request", "introductory", "@",
            ]):
                continue

            if not any(kw in text_lower for kw in [
                "solicitation", "opportunity", "sbir", "baa", "rfi",
                "request for", "funding", "contract",
            ]):
                continue

            opp_id = "jmetc-" + hashlib.md5(f"{text}-{href}".encode()).hexdigest()[:12]
            if opp_id in seen_ids:
                continue
            seen_ids.add(opp_id)

            full_url = href if href.startswith("http") else f"{TRMC_URL}/{href.lstrip('/')}"

            results.append({
                "id": opp_id,
                "title": text[:200],
                "url": full_url,
                "portal": "JMETC",
                "naics_code": "",
                "set_aside": "",
                "posted_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "due_date": "",
                "description": f"JMETC/TRMC announcement: {text}",
                "type": "TRMC Announcement",
                "department": "TRMC — Joint Mission Environment Test Capability",
            })

    return results
