"""BidNet Direct's public lists of open bids, one per state. No browser and no login.

    gate = Throttle()                                     # 5 seconds between requests, as robots.txt asks
    bids = fetch_state("colorado", cutoff, opener, gate)  # newest first, back to the cutoff date

Each list page holds 25 bids, newest first: title and link, state, published and closing dates.
Pages go by path (/open-bids/page2): robots.txt forbids query-string paging and asks for a
5-second crawl delay. A bid's own page keeps its agency, description and documents for paying
members, so only the lists are read. Docs: portals/bidnet/NOTES.md.
"""
from __future__ import annotations

import html
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import date
from typing import Any
from urllib.parse import urljoin

BASE = "https://www.bidnetdirect.com"
STATES = {"colorado": "Colorado", "florida": "Florida"}
CRAWL_DELAY_S = 5
MAX_PAGES = 20
TIMEOUT_S = 30
USER_AGENT = "velocity-bd-team scanner (Velocity Explorations)"

Opener = Callable[..., Any]   # urllib.request.urlopen, or a test's stand-in

ROW = re.compile(r'(?is)<tr\s+data-index="\d+"[^>]*>(.*?)</tr>')
LINK = re.compile(r'(?is)<a\b[^>]*\bhref="([^"]*/solicitations/open-bids/[^"]*?/(\d+)(?:\?[^"]*)?)"[^>]*>(.*?)</a>')
REGION = re.compile(r'(?is)class="sol-region-item"[^>]*>(.*?)</span>')
PUBLISHED = re.compile(r'(?is)class="sol-publication-date[^"]*".*?class="date-value"[^>]*>(.*?)</span>')
CLOSING = re.compile(r'(?is)class="sol-closing-date[^"]*".*?class="date-value"[^>]*>(.*?)</span>')
HIDDEN = re.compile(r"(?is)<(script|style|svg)\b[^>]*>.*?</\1\s*>")
TAGS = re.compile(r"<[^>]+>")
US_DATE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


class BidNetError(RuntimeError):
    """A list did not answer as expected. The pipeline records it and alerts."""


class Throttle:
    """Waits the crawl delay before every request but the first, across a run's pages and states."""

    def __init__(self, delay: float = CRAWL_DELAY_S, sleep: Callable[[float], None] = time.sleep) -> None:
        self.delay = delay
        self.sleep = sleep
        self.started = False

    def wait(self) -> None:
        if self.started:
            self.sleep(self.delay)
        self.started = True


def _text(markup: str) -> str:
    return " ".join(html.unescape(TAGS.sub(" ", markup)).split())


def us_date(text: Any) -> date | None:
    """ "10/23/2026" as a date."""
    found = US_DATE.search(str(text or ""))
    if not found:
        return None
    month, day, year = (int(part) for part in found.groups())
    try:
        return date(year, month, day)
    except ValueError:
        return None


def page_url(state: str, number: int) -> str:
    path = f"/{state}/solicitations/open-bids"
    return BASE + (path if number == 1 else f"{path}/page{number}")


def parse_page(markup: str) -> list[dict[str, Any]]:
    """Each bid row: id, title, state, link, and the page's wording of its two dates."""
    bids: list[dict[str, Any]] = []
    for body in ROW.findall(markup):
        body = HIDDEN.sub(" ", body)
        link = LINK.search(body)
        if not link:
            continue
        href, bid_id, title = link.groups()
        region, published, closing = REGION.search(body), PUBLISHED.search(body), CLOSING.search(body)
        bids.append({
            "bid_id": bid_id,
            "title": _text(title),
            "state": _text(region.group(1)) if region else "",
            "link": urljoin(BASE, href.replace("&amp;", "&")),
            "published": _text(published.group(1)) if published else "",
            "closing": _text(closing.group(1)) if closing else "",
        })
    return bids


def fetch_page(url: str, opener: Opener, label: str, gate: Throttle) -> str:
    """One list page, retried once, each try after the crawl delay."""
    problem = ""
    for _ in range(2):
        gate.wait()
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with opener(request, timeout=TIMEOUT_S) as reply:
                body = reply.read().decode("utf-8", errors="replace")
                if getattr(reply, "status", 200) == 202 and not body.strip():
                    # AWS bot protection's challenge: only a browser that runs its script gets past it,
                    # and the scanner does not do that (portals/bidnet/NOTES.md).
                    raise BidNetError(f"BidNet's bot protection answered the {label} list with a challenge (HTTP 202)")
                return body
        except urllib.error.HTTPError as exc:
            problem = f"HTTP {exc.code}"
        except (urllib.error.URLError, OSError, ValueError) as exc:
            problem = type(exc).__name__
    raise BidNetError(f"BidNet's {label} list did not answer ({problem})")


def fetch_state(state: str, cutoff: date, opener: Opener | None = None, gate: Throttle | None = None) -> list[dict[str, Any]]:
    """The state's bids published on or after `cutoff`, reading pages until they are older."""
    opener = opener or urllib.request.urlopen
    gate = gate or Throttle()
    label = STATES[state]
    kept: list[dict[str, Any]] = []
    for number in range(1, MAX_PAGES + 1):
        bids = parse_page(fetch_page(page_url(state, number), opener, label, gate))
        if not bids:
            if number == 1:
                raise BidNetError(f"BidNet's {label} list has no bids the scanner can read")
            break
        for bid in bids:
            bid["state"] = bid["state"] or label
        kept += [bid for bid in bids if (us_date(bid["published"]) or date.max) >= cutoff]
        dates = [d for d in (us_date(bid["published"]) for bid in bids) if d]
        if dates and min(dates) < cutoff:
            break
    return kept
