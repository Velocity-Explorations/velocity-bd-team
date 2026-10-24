"""The APFIT cycle-status posts, read from the APFIT page. No browser and no login.

    posts = cycle_posts(fetch_page())   # one request a run; one dict per cycle post

The page (WordPress with Beaver Builder) shows a post grid, one post per APFIT cycle, each with
schema.org publish and modify dates, a title linking to the post and a one-line status. The
site's REST API answers 401 to the public, so the page itself is read; robots.txt allows it.
Docs: portals/apfit/NOTES.md.
"""
from __future__ import annotations

import html
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

PAGE_URL = "https://ac.cto.mil/apfit/"
TIMEOUT_S = 30
USER_AGENT = "velocity-bd-team scanner (Velocity Explorations)"

Opener = Callable[..., Any]   # urllib.request.urlopen, or a test's stand-in

HIDDEN = re.compile(r"(?is)<(script|style|svg|noscript)\b[^>]*>.*?</\1\s*>")
TAGS = re.compile(r"<[^>]+>")
GRID = re.compile(r'class="fl-post-grid"')
POST = re.compile(r'(?=<div\b[^>]*\bclass="fl-post-grid-post\b)')
POST_ID = re.compile(r'class="fl-post-grid-post\b[^"]*\bpost-(\d+)\b')
TITLE = re.compile(r'(?is)class="fl-post-grid-title"[^>]*>\s*<a\b[^>]*\bhref="([^"]+)"[^>]*>(.*?)</a>')
PUBLISHED = re.compile(r'itemprop="datePublished"\s+content="(\d{4}-\d{2}-\d{2})')
MODIFIED = re.compile(r'itemprop="dateModified"\s+content="(\d{4}-\d{2}-\d{2})')
CONTENT = re.compile(r'(?is)class="fl-post-grid-content"[^>]*>(.*?)</div>')


class ApfitError(RuntimeError):
    """The page did not answer as expected. The pipeline records it and alerts."""


def _text(markup: str) -> str:
    return " ".join(html.unescape(TAGS.sub(" ", markup)).split())


def _first(pattern: re.Pattern[str], chunk: str) -> str:
    found = pattern.search(chunk)
    return found.group(1) if found else ""


def cycle_posts(markup: str) -> list[dict[str, str]]:
    """Each post in the grid: id, title, link, ISO publish and modify dates, and its status text."""
    markup = HIDDEN.sub(" ", markup)
    grid = GRID.search(markup)
    if grid is None:
        raise ApfitError("the APFIT page has no post grid of cycle statuses")
    posts: list[dict[str, str]] = []
    for chunk in POST.split(markup[grid.end():])[1:]:
        title = TITLE.search(chunk)
        if not title:
            continue
        content = CONTENT.search(chunk)
        posts.append({
            "post_id": _first(POST_ID, chunk),
            "title": _text(title.group(2)),
            "link": html.unescape(title.group(1)).strip(),
            "published": _first(PUBLISHED, chunk),
            "modified": _first(MODIFIED, chunk),
            "status": _text(content.group(1)) if content else "",
        })
    return posts


def fetch_page(opener: Opener | None = None) -> str:
    """The APFIT page, retried once."""
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
    raise ApfitError(f"the APFIT page did not answer ({problem})")
