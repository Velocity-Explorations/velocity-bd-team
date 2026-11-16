"""SBIR.gov's copy of the Defense Department's open topics: the topic list, then each topic's page.

    fetcher = Fetcher()
    links = topic_links(fetcher)        # every open DoD topic's page, ten to a list page
    page = fetcher.get(links[0])

DSIP, where the topics are published, forbids automated access in its robots.txt (Disallow: / for every agent), so the
scanner never fetches it. SBIR.gov copies the agencies' topics and its robots.txt allows /topics; its list filters by
status and agency in the query (status=Open, agency[DOD]=DOD). One request a second, the list's pages first. No browser
and no login. Docs: portals/dsip/NOTES.md.
"""
from __future__ import annotations

import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

BASE = "https://www.sbir.gov"
LIST = f"{BASE}/topics"
MAX_PAGES = 30          # 82 open DoD topics filled 9 pages on 16 Nov 2026
TIMEOUT_S = 30
DELAY_S = 1.0           # between requests
USER_AGENT = "velocity-bd-team scanner (Velocity Explorations)"
LINK = re.compile(r'href="(/topics/\d+)"')

Opener = Callable[..., Any]   # urllib.request.urlopen, or a test's stand-in


class SbirGovError(RuntimeError):
    """SBIR.gov did not answer as expected. On the list the pipeline records it and alerts; on one topic it counts as failed."""


class Fetcher:
    """GETs from SBIR.gov, one at a time and DELAY_S apart, each retried once."""

    def __init__(self, opener: Opener | None = None, delay: float = DELAY_S) -> None:
        self.opener = opener or urllib.request.urlopen
        self.delay = delay
        self.asked = False

    def get(self, url: str) -> str:
        problem = ""
        for _ in range(2):
            if self.asked and self.delay:
                time.sleep(self.delay)
            self.asked = True
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
            try:
                with self.opener(request, timeout=TIMEOUT_S) as reply:
                    return reply.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as exc:
                problem = f"HTTP {exc.code}"
            except (urllib.error.URLError, OSError, ValueError) as exc:
                problem = type(exc).__name__
        raise SbirGovError(f"SBIR.gov did not answer ({problem}): {url}")


def list_url(page: int) -> str:
    return f"{LIST}?{urllib.parse.urlencode({'status': 'Open', 'agency[DOD]': 'DOD', 'page': page})}"


def topic_links(fetcher: Fetcher) -> list[str]:
    """Every open DoD topic's page on SBIR.gov, in the list's order: list pages until one adds nothing."""
    links: list[str] = []
    for page in range(MAX_PAGES):
        found = [f"{BASE}{path}" for path in dict.fromkeys(LINK.findall(fetcher.get(list_url(page))))]
        fresh = [link for link in found if link not in links]
        if not fresh:
            return links
        links += fresh
    raise SbirGovError(f"SBIR.gov's topic list ran past {MAX_PAGES} pages")
