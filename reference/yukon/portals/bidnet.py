"""
Yukon — BidNet Direct portal adapter
Scrapes open solicitations from bidnetdirect.com for Colorado and Florida.

BidNet Direct is a state/local government bid aggregator covering city,
county, and state agencies. The public listing pages show title, published
date, closing date, and a direct URL for each open solicitation — no login
required to view the listing.

Individual bid detail pages require registration, so we use listing data only.
One adapter instance per state, configured via the portal URL in profile.yaml.

Colorado: https://www.bidnetdirect.com/colorado/solicitations/open-bids
Florida:  https://www.bidnetdirect.com/florida/solicitations/open-bids
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

BASE_URL = "https://www.bidnetdirect.com"
REQUEST_TIMEOUT = 30

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

# State configs
STATE_CONFIGS = {
    "colorado": {
        "url": f"{BASE_URL}/colorado/solicitations/open-bids",
        "label": "Colorado",
        "department": "Colorado State/Local Government",
        "purchasing_group_id": "8409951",
    },
    "florida": {
        "url": f"{BASE_URL}/florida/solicitations/open-bids",
        "label": "Florida",
        "department": "Florida State/Local Government",
        "purchasing_group_id": "8408751",
    },
}


def fetch_state(state: str, **kwargs) -> List[Dict]:
    """
    Fetch open solicitations for a specific state.
    state: 'colorado' or 'florida'
    """
    config = STATE_CONFIGS.get(state.lower())
    if not config:
        log.error(f"BidNet: unknown state '{state}' — supported: {list(STATE_CONFIGS.keys())}")
        return []

    return _fetch(config)


def fetch(url: str = None, **kwargs) -> List[Dict]:
    """
    Fetch open solicitations from a BidNet Direct listing URL.
    Auto-detects state from URL.
    """
    if not url:
        log.error("BidNet: no URL provided")
        return []

    # Detect state from URL
    state = None
    for s in STATE_CONFIGS:
        if s in url.lower():
            state = s
            break

    if state:
        config = STATE_CONFIGS[state]
    else:
        # Generic config from URL
        config = {
            "url": url,
            "label": "State/Local",
            "department": "State/Local Government",
            "purchasing_group_id": "",
        }

    return _fetch(config)


def _fetch(config: Dict) -> List[Dict]:
    """Fetch and parse a BidNet Direct listing page."""
    url = config["url"]
    label = config["label"]

    try:
        log.info(f"BidNet [{label}]: fetching open solicitations")
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.error(f"BidNet [{label}]: fetch error: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    opps = _parse_listings(soup, config)
    log.info(f"BidNet [{label}]: found {len(opps)} open solicitations")
    return opps


def _parse_listings(soup: BeautifulSoup, config: Dict) -> List[Dict]:
    """
    Parse BidNet listing page. Structure:
    - Title as anchor text
    - State label
    - Published date
    - Closing date
    All in the readability-extracted text flow.
    """
    results = []
    seen_ids = set()
    label = config["label"]
    base_listing_url = config["url"]

    # Get all anchor tags that link to individual solicitations
    # BidNet URL pattern: /{state}/solicitations/open-bids/{slug}/{id}
    sol_links = soup.find_all("a", href=re.compile(r"/solicitations/open-bids/[^/]+/\d+"))

    for link in sol_links:
        title = link.get_text(strip=True)
        if not title or len(title) < 5:
            continue

        href = link.get("href", "")
        full_url = href if href.startswith("http") else BASE_URL + href

        # Extract bid ID from URL for stable dedup
        bid_id_match = re.search(r"/(\d+)(?:\?|$)", href)
        bid_id = bid_id_match.group(1) if bid_id_match else hashlib.md5(title.encode()).hexdigest()[:10]
        opp_id = f"bidnet-{label.lower()}-{bid_id}"

        if opp_id in seen_ids:
            continue
        seen_ids.add(opp_id)

        # Extract dates from surrounding context
        # Walk up to the parent container and look for date text
        parent = link.find_parent()
        container_text = ""
        for _ in range(5):  # walk up max 5 levels
            if parent:
                container_text = parent.get_text(" ", strip=True)
                if "Published" in container_text and "Closing" in container_text:
                    break
                parent = parent.find_parent()

        published_date = _extract_labeled_date(container_text, "Published")
        closing_date = _extract_labeled_date(container_text, "Closing")

        results.append({
            "id": opp_id,
            "title": title,
            "url": full_url,
            "portal": f"BidNet {label}",
            "naics_code": "",   # BidNet doesn't publish NAICS — keyword filter applies
            "set_aside": "",
            "posted_date": published_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "due_date": closing_date,
            "description": f"{label} government solicitation: {title}",
            "type": _infer_type(title),
            "department": config["department"],
        })

    # Fallback: if no anchor links found, parse from text blocks
    if not results:
        results = _parse_from_text(soup, config)

    return results


def _parse_from_text(soup: BeautifulSoup, config: Dict) -> List[Dict]:
    """
    Fallback parser: extract listings from plain text flow.
    Used when anchor tags aren't present in the HTML.
    """
    results = []
    seen = set()
    label = config["label"]

    content = soup.find("main") or soup
    full_text = content.get_text("\n", strip=True)

    # Pattern: title line followed by "Published MM/DD/YYYY" and "Closing MM/DD/YYYY"
    # Each listing block looks like:
    #   Title Text
    #   Colorado/Florida
    #   Published 03/20/2026
    #   Closing 04/21/2026
    lines = [l.strip() for l in full_text.split("\n") if l.strip()]

    i = 0
    while i < len(lines):
        line = lines[i]

        # Skip short lines, state labels, headers
        if len(line) < 10 or line in [label, "Colorado", "Florida", "Wyoming"]:
            i += 1
            continue
        if any(skip in line for skip in ["Published", "Closing", "Open Solicitations", "Register", "Filters", "Order By", "Welcome", "Group Bids"]):
            i += 1
            continue

        # Check if next lines look like a date block
        published = ""
        closing = ""
        if i + 1 < len(lines) and lines[i + 1] in [label, "Colorado", "Florida", "Wyoming"]:
            for j in range(i + 2, min(i + 6, len(lines))):
                if lines[j].startswith("Published") or "Published" in lines[j]:
                    published = re.sub(r"[^\d/\-]", "", lines[j].replace("Published", "")).strip()
                elif lines[j].startswith("Closing") or "Closing" in lines[j]:
                    closing = re.sub(r"[^\d/\-]", "", lines[j].replace("Closing", "")).strip()

            if closing:  # Only add if we found a date — confirms it's a listing
                opp_id = "bidnet-" + label.lower() + "-" + hashlib.md5(line.encode()).hexdigest()[:10]
                if opp_id not in seen:
                    seen.add(opp_id)
                    results.append({
                        "id": opp_id,
                        "title": line,
                        "url": config["url"],
                        "portal": f"BidNet {label}",
                        "naics_code": "",
                        "set_aside": "",
                        "posted_date": published or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "due_date": closing,
                        "description": f"{label} government solicitation: {line}",
                        "type": _infer_type(line),
                        "department": config["department"],
                    })
        i += 1

    return results


def _extract_labeled_date(text: str, label: str) -> str:
    """Extract a date following a label like 'Published' or 'Closing'."""
    pattern = rf"{label}\s+(\d{{1,2}}/\d{{1,2}}/\d{{4}})"
    match = re.search(pattern, text)
    if match:
        # Normalize to YYYY-MM-DD
        try:
            dt = datetime.strptime(match.group(1), "%m/%d/%Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return match.group(1)
    return ""


def _infer_type(title: str) -> str:
    """Infer solicitation type from title."""
    title_upper = title.upper()
    if "RFP" in title_upper:
        return "RFP"
    if "RFQ" in title_upper or "QUOTE" in title_upper:
        return "RFQ"
    if "ITB" in title_upper or "IFB" in title_upper or "BID" in title_upper:
        return "ITB/IFB"
    if "RFI" in title_upper:
        return "RFI"
    if "SOLE SOURCE" in title_upper:
        return "Sole Source"
    return "Solicitation"
