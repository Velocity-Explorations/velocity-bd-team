"""Space Florida's active RFPs, read from its public solicitations page. No browser and no login.

    found = solicitations(fetch_page())   # one request a run; one dict per active RFP

The page (a Webflow site) lists Active RFPs, then Awarded RFPs, then a mobile copy of both. Each
active item has its title, links to its documents (plus empty hidden slots), optional notes, and
its published and due dates. Only the first Active RFPs list is read, up to the Awarded RFPs
heading. robots.txt allows everything. Docs: portals/space_florida/NOTES.md.
"""
from __future__ import annotations

import html
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

PAGE_URL = "https://www.spaceflorida.gov/solicitations"
TIMEOUT_S = 30
USER_AGENT = "velocity-bd-team scanner (Velocity Explorations)"

Opener = Callable[..., Any]   # urllib.request.urlopen, or a test's stand-in

HIDDEN = re.compile(r"(?is)<(script|style|svg)\b[^>]*>.*?</\1\s*>")
TAGS = re.compile(r"<[^>]+>")
ACTIVE = re.compile(r"(?is)<h[1-6][^>]*>\s*Active RFPs\s*</h[1-6]>")
AWARDED = re.compile(r"(?is)<h[1-6][^>]*>\s*Awarded RFPs\s*</h[1-6]>")
ITEM = re.compile(r'(?i)<div\b[^>]*\brole="listitem"')
TITLE = re.compile(r'(?is)class="proposal-title".*?<div class="paragraph[^"]*">(.*?)</div>')
DOCUMENT = re.compile(r'(?is)<a\b[^>]*\bhref="(?!#)([^"]+)"[^>]*>\s*<div class="paragraph[^"]*">(.*?)</div>')
NOTES = re.compile(r'(?is)<div class="rfps-rich-text(?![^"]*w-dyn-bind-empty)[^"]*"[^>]*>(.*?)</div>')
PUBLISHED = re.compile(r'(?is)class="published-rfps".*?<div class="paragraph[^"]*">(.*?)</div>')
DUE = re.compile(r'(?is)class="due-rfps".*?<div class="paragraph[^"]*">(.*?)</div>')


class SpaceFloridaError(RuntimeError):
    """The page did not answer as expected. The pipeline records it and alerts."""


def _text(markup: str) -> str:
    return " ".join(html.unescape(TAGS.sub(" ", markup)).split())


def _first(pattern: re.Pattern[str], chunk: str) -> str:
    found = pattern.search(chunk)
    return _text(found.group(1)) if found else ""


def solicitations(markup: str) -> list[dict[str, Any]]:
    """Each active RFP once, in page order: title, documents (name and link), notes and two dates."""
    markup = HIDDEN.sub(" ", markup)
    start = ACTIVE.search(markup)
    if start is None:
        raise SpaceFloridaError("the page has no Active RFPs list")
    end = AWARDED.search(markup, start.end())
    section = markup[start.end():end.start() if end else len(markup)]
    found: dict[str, dict[str, Any]] = {}
    for chunk in ITEM.split(section)[1:]:
        title = _first(TITLE, chunk)
        if not title:
            continue
        documents = [{"name": _text(name), "url": html.unescape(url).strip()}
                     for url, name in DOCUMENT.findall(chunk) if _text(name)]
        found.setdefault(title, {"title": title, "documents": documents, "notes": _first(NOTES, chunk),
                                 "published": _first(PUBLISHED, chunk), "due": _first(DUE, chunk)})
    return list(found.values())


def fetch_page(opener: Opener | None = None) -> str:
    """The solicitations page, retried once."""
    opener = opener or urllib.request.urlopen
    problem = ""
    for _ in range(2):
        request = urllib.request.Request(PAGE_URL, headers={"User-Agent": USER_AGENT})
        try:
            with opener(request, timeout=TIMEOUT_S) as reply:
                return reply.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            problem = f"HTTP {exc.code}"
        except (urllib.error.URLError, OSError, ValueError) as exc:
            problem = type(exc).__name__
    raise SpaceFloridaError(f"Space Florida did not answer ({problem})")
