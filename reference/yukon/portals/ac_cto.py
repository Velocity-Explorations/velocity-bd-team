"""
Yukon — AC CTO / APFIT portal adapter
Scrapes APFIT (Army Prize for Innovation in Technology) cycle status from ac.cto.mil.

The site uses WordPress with Beaver Builder. Posts are in a fl-post-grid.
Each post represents an APFIT selection cycle (e.g. FY27-1, FY26-2).
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

BASE_URL = "https://ac.cto.mil"
APFIT_URL = f"{BASE_URL}/apfit/"
WP_API_URL = f"{BASE_URL}/wp-json/wp/v2/posts"
REQUEST_TIMEOUT = 30

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def fetch(**kwargs) -> List[Dict]:
    """Scrape APFIT cycle status posts. Returns normalized opportunity dicts."""
    opps = _fetch_via_html()
    if not opps:
        opps = _fetch_via_api()
    log.info(f"AC CTO/APFIT: found {len(opps)} cycle posts")
    return opps


def _fetch_via_html() -> List[Dict]:
    """Primary: scrape the APFIT page HTML."""
    try:
        log.info("AC CTO/APFIT: fetching APFIT page")
        resp = requests.get(APFIT_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.error(f"AC CTO/APFIT: fetch error: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    grid = soup.find("div", class_="fl-post-grid")
    if not grid:
        log.warning("AC CTO/APFIT: no fl-post-grid found on page")
        return []

    posts = grid.find_all("div", class_="fl-post-grid-post")
    for post in posts:
        title_el = post.find("h3", class_="fl-post-grid-title")
        if not title_el:
            continue
        link = title_el.find("a")
        title = title_el.get_text(strip=True)
        url = link["href"] if link and link.get("href") else APFIT_URL

        date_el = post.find("span", class_="fl-post-grid-date")
        posted_date = ""
        if date_el:
            posted_date = _parse_date(date_el.get_text(strip=True))

        content_el = post.find("div", class_="fl-post-grid-content")
        description = content_el.get_text(strip=True)[:1000] if content_el else ""

        is_open = any(kw in description.lower() for kw in ["open", "anticipated to open", "accepting"])
        is_closed = any(kw in description.lower() for kw in ["closed", "evaluation"])

        opp_id = "apfit-" + hashlib.md5(title.encode()).hexdigest()[:12]

        results.append({
            "id": opp_id,
            "title": f"APFIT: {title}",
            "url": url,
            "portal": "AC CTO / APFIT",
            "naics_code": "",
            "set_aside": "",
            "posted_date": posted_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "due_date": "",
            "description": description,
            "type": "APFIT Selection Cycle" + (" (Open)" if is_open else " (Closed)" if is_closed else ""),
            "department": "Army Contracting Command — CTO",
        })

    return results


def _fetch_via_api() -> List[Dict]:
    """Fallback: use WordPress REST API."""
    try:
        log.info("AC CTO/APFIT: trying WP REST API fallback")
        resp = requests.get(
            WP_API_URL,
            params={"per_page": 20, "search": "APFIT"},
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        posts = resp.json()
    except Exception as e:
        log.error(f"AC CTO/APFIT: API fallback failed: {e}")
        return []

    results = []
    for post in posts:
        title = BeautifulSoup(post.get("title", {}).get("rendered", ""), "html.parser").get_text(strip=True)
        if not title:
            continue

        excerpt = BeautifulSoup(post.get("excerpt", {}).get("rendered", ""), "html.parser").get_text(strip=True)
        posted_date = post.get("date", "")[:10]

        opp_id = f"apfit-wp-{post['id']}"

        results.append({
            "id": opp_id,
            "title": f"APFIT: {title}",
            "url": post.get("link", APFIT_URL),
            "portal": "AC CTO / APFIT",
            "naics_code": "",
            "set_aside": "",
            "posted_date": posted_date,
            "due_date": "",
            "description": excerpt[:1000],
            "type": "APFIT Selection Cycle",
            "department": "Army Contracting Command — CTO",
        })

    return results


def _parse_date(text: str) -> str:
    """Parse dates like 'March 20, 2026' to 'YYYY-MM-DD'."""
    for fmt in ["%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"]:
        try:
            return datetime.strptime(text.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""
