"""NSTXL's opportunities, read from the site's public WordPress REST API. No browser and no login.

    statuses = fetch_terms("opp_status")    # {term id: "SpEC - Current", ...}
    otas = fetch_terms("ota")                # {term id: "S2MARTS", ...}
    items = fetch_opportunities()            # every opportunity post, all pages

The opportunity posts carry their status and consortium as term ids; a member-only post's
text is only NSTXL's "member only page" notice (docs: portals/nstxl/NOTES.md).
"""
from __future__ import annotations

import html
import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

BASE = "https://nstxl.org/wp-json/wp/v2"
PER_PAGE = 100
MAX_PAGES = 20
TIMEOUT_S = 30
USER_AGENT = "velocity-bd-team scanner (Velocity Explorations)"
FIELDS = "id,date,modified,link,title,content,opp_status,ota"   # leaves out the large SEO block

Opener = Callable[..., Any]   # urllib.request.urlopen, or a test's stand-in


class NstxlError(RuntimeError):
    """The site did not answer as expected. The pipeline records it and alerts."""


def _get(opener: Opener, url: str) -> tuple[Any, int]:
    """One GET, retried once: the JSON body and the number of pages WordPress reports."""
    problem = ""
    for _ in range(2):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with opener(request, timeout=TIMEOUT_S) as reply:
                body = json.loads(reply.read().decode("utf-8"))
                pages = (reply.headers or {}).get("X-WP-TotalPages") or 1
                return body, int(pages)
        except urllib.error.HTTPError as exc:
            problem = f"HTTP {exc.code}"
        except (urllib.error.URLError, OSError, ValueError) as exc:
            problem = type(exc).__name__
    raise NstxlError(f"NSTXL did not answer ({problem})")


def _all(opener: Opener, route: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for page in range(1, MAX_PAGES + 1):
        query = urllib.parse.urlencode({**params, "per_page": PER_PAGE, "page": page})
        body, pages = _get(opener, f"{BASE}/{route}?{query}")
        if not isinstance(body, list):
            raise NstxlError(f"NSTXL's {route} list came back in an unexpected shape")
        found += body
        if page >= pages:
            return found
    raise NstxlError(f"NSTXL's {route} list ran past {MAX_PAGES} pages")


def fetch_terms(name: str, opener: Opener | None = None) -> dict[int, str]:
    """A taxonomy's terms, id to name: opp_status or ota."""
    terms = _all(opener or urllib.request.urlopen, name, {"_fields": "id,name"})
    return {int(t["id"]): html.unescape(str(t.get("name") or "")).strip() for t in terms}


def fetch_opportunities(opener: Opener | None = None) -> list[dict[str, Any]]:
    """Every opportunity post, newest first, open or not: closed ones refresh stored calls."""
    return _all(opener or urllib.request.urlopen, "opportunity", {"_fields": FIELDS})
