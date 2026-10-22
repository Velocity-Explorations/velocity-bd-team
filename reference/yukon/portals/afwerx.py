"""
Yukon — AFWERX / STRIKEWERX / SpaceWERX portal adapter
Scrapes open SBIR/STTR solicitations from the AFWERX "Get Funded" page.

STRIKEWERX (strikewerx.com) has no solicitations page — their /opportunities URL
is a 404. AFWERX is the parent innovation hub and posts all AF SBIR/STTR
solicitations at afwerx.com/get-funded/. SpaceWERX solicitations are included
on the same page.

The page uses structured HTML with timeline/card sections for each solicitation
type (Specific Topic, Open Topic, STRATFI/TACFI, etc.) with open/close dates.
"""

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

AFWERX_URL = "https://afwerx.com/get-funded/"
REQUEST_TIMEOUT = 30

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def fetch(**kwargs) -> List[Dict]:
    """Scrape AFWERX open solicitations. Returns normalized opportunity dicts."""
    try:
        log.info("AFWERX: fetching get-funded page")
        resp = requests.get(AFWERX_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.error(f"AFWERX: fetch error: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    opps = _parse_solicitations(soup)
    log.info(f"AFWERX: found {len(opps)} solicitations")
    return opps


def _parse_solicitations(soup: BeautifulSoup) -> List[Dict]:
    """Extract solicitation entries from the get-funded page.

    The page text has repeated blocks like:
      SOLICITATION : DoD SBIR Specific Topic 26.BZ Release 1
      PRE-RELEASE : 13 APRIL 26
      OPEN : 6 MAY 26
      CLOSE : 6 JUN 26
    All on one line when extracted as text, so we regex the full text.
    """
    results = []
    seen_ids = set()
    full_text = soup.get_text(" ", strip=True)

    # Match: SOLICITATION : <title> PRE-RELEASE : <date|N/A> OPEN : <date> CLOSE : <date>
    pattern = re.compile(
        r"SOLICITATION\s*:\s*(.+?)\s+"
        r"PRE-RELEASE\s*:\s*(?:[\w\d/ ]+?)\s+"
        r"OPEN\s*:\s*([\d]+\s+\w+\s+\d{2,4})\s+"
        r"CLOSE\s*:\s*([\d]+\s+\w+\s+\d{2,4})",
        re.IGNORECASE,
    )

    for m in pattern.finditer(full_text):
        title = m.group(1).strip()
        open_date = _parse_mil_date(m.group(2))
        close_date = _parse_mil_date(m.group(3))

        if not title or len(title) < 5:
            continue

        opp_id = "afwerx-" + hashlib.md5(title.encode()).hexdigest()[:12]
        if opp_id in seen_ids:
            continue
        seen_ids.add(opp_id)

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        is_open = open_date and open_date <= now and (not close_date or close_date >= now)
        is_upcoming = open_date and open_date > now

        sol_type = "SBIR/STTR"
        if "stratfi" in title.lower() or "tacfi" in title.lower():
            sol_type = "STRATFI/TACFI"
        elif "open topic" in title.lower():
            sol_type = "SBIR/STTR Open Topic"
        elif "specific" in title.lower():
            sol_type = "SBIR/STTR Specific Topic"

        status = "Open" if is_open else "Upcoming" if is_upcoming else "Closed"

        results.append({
            "id": opp_id,
            "title": f"AFWERX {sol_type}: {title}" if "AFWERX" not in title else title,
            "url": AFWERX_URL,
            "portal": "AFWERX / STRIKEWERX",
            "naics_code": "",
            "set_aside": "SB",
            "posted_date": open_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "due_date": close_date,
            "description": f"Air Force {sol_type} solicitation via AFWERX. Opens: {open_date or 'TBD'}. Closes: {close_date or 'TBD'}. Status: {status}.",
            "type": f"AFWERX {sol_type} ({status})",
            "department": "Department of the Air Force — AFWERX",
        })

    return results


def _parse_mil_date(text: str) -> str:
    """Parse military-style dates like '14 APRIL 26' or '6 MAY 26' to YYYY-MM-DD."""
    text = text.strip()
    # Try various formats
    for fmt in ["%d %B %y", "%d %b %y", "%d %B %Y", "%d %b %Y", "%B %d %Y", "%B %d %y"]:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""
