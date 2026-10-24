"""DOE's SBIR and STTR solicitations, read from its Application Hub's public WordPress REST API.

    items = fetch_items()   # every portfolio item, all pages, open or closed

DOE's SBIR/STTR programs moved from the Office of Science to the Office of Technology
Commercialization in 2026, and the Office of Science page now says all its opportunities are
closed. The hub, run for DOE by ConnectWerx, posts each solicitation as an Avada portfolio item
whose classes carry its category: Active, Upcoming or Closed Solicitation. No browser and no
login. Docs: portals/doe_sbir/NOTES.md.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

BASE = "https://sbir-sttr.connectwerx.org/wp-json/wp/v2"
PER_PAGE = 100
MAX_PAGES = 10
TIMEOUT_S = 30
USER_AGENT = "velocity-bd-team scanner (Velocity Explorations)"
FIELDS = "id,date,modified,link,title,content,excerpt,class_list"   # leaves out the large SEO block

Opener = Callable[..., Any]   # urllib.request.urlopen, or a test's stand-in


class DoeError(RuntimeError):
    """The hub did not answer as expected. The pipeline records it and alerts."""


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
    raise DoeError(f"DOE's Application Hub did not answer ({problem})")


def fetch_items(opener: Opener | None = None) -> list[dict[str, Any]]:
    """Every solicitation item, open or not: closed ones refresh stored calls."""
    opener = opener or urllib.request.urlopen
    found: list[dict[str, Any]] = []
    for page in range(1, MAX_PAGES + 1):
        query = urllib.parse.urlencode({"_fields": FIELDS, "per_page": PER_PAGE, "page": page})
        body, pages = _get(opener, f"{BASE}/avada_portfolio?{query}")
        if not isinstance(body, list):
            raise DoeError("the hub's solicitation list came back in an unexpected shape")
        found += [entry for entry in body if isinstance(entry, dict)]
        if page >= pages:
            return found
    raise DoeError(f"the hub's solicitation list ran past {MAX_PAGES} pages")
