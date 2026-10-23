"""The SBIR and STTR cycles listed on AFWERX's Get Funded page. No browser and no login.

    html = fetch_page()     # one request a run
    found = cycles(html)    # one dict per cycle under "Open Funding Opportunities"

The page lists each cycle twice: as a grid row (badges, title, then three unlabelled dates) and
as a labelled block for small screens, which as text reads

    AF
    SOLICITATION : DOW SBIR SPECIFIC TOPIC 27.BZ & 27.BX Release 1
    PRE-RELEASE : 7 Oct 26
    OPEN : 28 Oct 26
    CLOSE : 25 Nov 26

cycles() reads the labelled blocks, which name each date, and the badges just above each one
(AF: the cycle includes Air Force topics; SF: Space Force topics). Docs: portals/afwerx/NOTES.md.
"""
from __future__ import annotations

import html as markup
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

GET_FUNDED_URL = "https://afwerx.com/get-funded/"
TIMEOUT_S = 30
USER_AGENT = "velocity-bd-team scanner (Velocity Explorations)"
HEADING = "open funding opportunities"
BRANCHES = {"AF": "Air Force", "SF": "Space Force"}   # the page's legend for its badges
DATE_LABELS = {"PRE-RELEASE": "pre_release", "OPEN": "open", "CLOSE": "close"}

Opener = Callable[..., Any]   # urllib.request.urlopen, or a test's stand-in

HIDDEN = re.compile(r"(?is)<(script|style)\b[^>]*>.*?</\1\s*>")
BREAKS = re.compile(r"(?i)<br\s*/?>|</(?:p|div|li|a|h[1-6]|tr|td)>")
TAGS = re.compile(r"<[^>]+>")
LABELLED = re.compile(r"(?i)^(SOLICITATION|PRE-RELEASE|OPEN|CLOSE)\s*:\s*(.*)$")
WORDS = re.compile(r"[A-Za-z]+")


class AfwerxError(RuntimeError):
    """The page did not answer as expected. The pipeline records it and alerts."""


def page_lines(html: str) -> list[str]:
    """The page as text, one line per block: scripts and styles dropped, entities decoded, spaces collapsed."""
    text = markup.unescape(TAGS.sub(" ", BREAKS.sub("\n", HIDDEN.sub(" ", html))))
    return [" ".join(line.split()) for line in text.splitlines() if line.strip()]


def _badges(line: str) -> list[str] | None:
    """The services a badge line names ("AF", "SF", "AF / SF"), or None for any other line."""
    words = WORDS.findall(line)
    if not words or any(word not in BRANCHES for word in words):
        return None
    return [BRANCHES[word] for word in words]


def _label(line: str) -> tuple[str, str]:
    found = LABELLED.match(line)
    return (found.group(1).upper(), found.group(2).strip()) if found else ("", "")


def cycles(html: str) -> list[dict[str, Any]]:
    """Each cycle once, in page order: title, branches, and AFWERX's wording of its three dates."""
    lines = page_lines(html)
    start = next((i for i, line in enumerate(lines) if line.lower() == HEADING), None)
    if start is None:
        raise AfwerxError("the page has no Open Funding Opportunities list")
    section = lines[start + 1:]
    found: dict[str, dict[str, Any]] = {}
    for i, line in enumerate(section):
        label, title = _label(line)
        if label != "SOLICITATION":
            continue
        cycle: dict[str, Any] = {"title": title, "branches": [], "pre_release": "", "open": "", "close": ""}
        for later in section[i + 1:i + 1 + len(DATE_LABELS)]:
            date_label, value = _label(later)
            if date_label not in DATE_LABELS:
                break
            cycle[DATE_LABELS[date_label]] = value
        branches: list[str] = []
        for earlier in reversed(section[:i]):
            named = _badges(earlier)
            if named is None:
                break
            branches = named + branches
        cycle["branches"] = list(dict.fromkeys(branches))
        found.setdefault(title, cycle)
    if not found and any(_badges(line) for line in section):
        raise AfwerxError("the list has entries the scanner could not read (no labelled SOLICITATION blocks)")
    return list(found.values())


def fetch_page(opener: Opener | None = None) -> str:
    """The Get Funded page, retried once."""
    opener = opener or urllib.request.urlopen
    problem = ""
    for _ in range(2):
        request = urllib.request.Request(GET_FUNDED_URL, headers={"User-Agent": USER_AGENT})
        try:
            with opener(request, timeout=TIMEOUT_S) as reply:
                return reply.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            problem = f"HTTP {exc.code}"
        except (urllib.error.URLError, OSError, ValueError) as exc:
            problem = type(exc).__name__
    raise AfwerxError(f"AFWERX did not answer ({problem})")
