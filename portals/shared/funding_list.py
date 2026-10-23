"""The "Open Funding Opportunities" list on AFWERX's and SpaceWERX's Get Funded pages.

    found = solicitations(fetch_page(site))   # one request; one dict per listing
    rec = build_record(found[0], now, site)   # one `calls` row
    counts = fetch_all(run_id, site)          # both, into the ledger

Both sites run one WordPress template. It lists each solicitation twice: as a grid row (badges,
title, then three unlabelled dates) and as a labelled block for small screens, which as text
reads

    AF
    SOLICITATION : DOW SBIR SPECIFIC TOPIC 27.BZ & 27.BX Release 1
    PRE-RELEASE : 7 Oct 26
    OPEN : 28 Oct 26
    CLOSE : 25 Nov 26

solicitations() reads the labelled blocks, which name each date, the badges just above each one
(AF: the solicitation includes Air Force topics; SF: Space Force topics) and each block's link.
Dates come as "7 Oct 26" or "13 APRIL 26", with no time of day; a listing counts as closed from
the day after its close date, in Eastern time. Docs: portals/afwerx/NOTES.md, portals/spacewerx/NOTES.md.
"""
from __future__ import annotations

import html as markup
import logging
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

from ledger.queries import get_call, upsert_call

TIMEOUT_S = 30
USER_AGENT = "velocity-bd-team scanner (Velocity Explorations)"
HEADING = "open funding opportunities"
LIST_END = "dates subject to change"   # the note under the list
BRANCHES = {"AF": "Air Force", "SF": "Space Force"}   # the pages' legend for their badges
DATE_LABELS = {"PRE-RELEASE": "pre_release", "OPEN": "open", "CLOSE": "close"}
TOPICS_URL = "https://www.dodsbirsttr.mil/topics-app/"   # DSIP's topic search: linked for people, never fetched
DSIP_HOST = "dodsbirsttr.mil"
EASTERN = ZoneInfo("America/New_York")
MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september",
          "october", "november", "december")

Opener = Callable[..., Any]   # urllib.request.urlopen, or a test's stand-in

HIDDEN = re.compile(r"(?is)<(script|style)\b[^>]*>.*?</\1\s*>")
BREAKS = re.compile(r"(?i)<br\s*/?>|</(?:p|div|li|a|h[1-6]|tr|td)>")
TAGS = re.compile(r"<[^>]+>")
LABELLED = re.compile(r"(?i)^(SOLICITATION|PRE-RELEASE|OPEN|CLOSE)\s*:\s*(.*)$")
LINKED = re.compile(r'(?is)<a\b[^>]*?\bhref="([^"]*)"[^>]*>\s*(?:<strong>\s*)?SOLICITATION\s*(?:</strong>)?\s*:(.*?)</a>')
WORDS = re.compile(r"[A-Za-z]+")
DAY_MONTH_YEAR = re.compile(r"(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4}|\d{2})")
CONTINUOUS = re.compile(r"(?i)\b(?:continuous|rolling)\b")
NOT_SET = re.compile(r"(?i)n/?a|tb[ad]|to be (?:announced|determined)")   # the page has no date yet

KINDS = {"SBIR/STTR cycle": "An SBIR/STTR solicitation cycle", "STTR cycle": "An STTR solicitation cycle",
         "SBIR cycle": "An SBIR solicitation cycle", "STRATFI/TACFI": "A STRATFI/TACFI solicitation",
         "STRATFI": "A STRATFI solicitation", "TACFI": "A TACFI solicitation", "Solicitation": "A solicitation"}
CYCLES = {"SBIR/STTR cycle", "STTR cycle", "SBIR cycle"}       # their topics are on DSIP
SEQUENTIAL = {"STRATFI/TACFI", "STRATFI", "TACFI"}             # for Phase II holders
# Neither note says SBIR or STTR, so the keyword filter matches only the title's own words.
DSIP_NOTE = ("{name} lists solicitations, not their topics. The topics are on DSIP, the Defense Department's "
             "portal for these solicitations, which the scanner does not read.")
PHASE_II_NOTE = ("STRATFI and TACFI are only for companies with a current or recent Phase II award, and not "
                 "twice for the same technology.")

log = logging.getLogger("funding_list")


class FundingListError(RuntimeError):
    """The page did not answer as expected. The pipeline records it and alerts."""


@dataclass(frozen=True)
class Site:
    portal: str        # calls.portal, and the name in descriptions: "AFWERX"
    prefix: str        # of ids and extra keys: "afwerx"
    page_url: str      # its Get Funded page
    department: str    # calls.department


# ------------------------------------------------------------------------------ the page

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


def _links(html: str) -> dict[str, str]:
    """Each labelled block's link, by its title."""
    links: dict[str, str] = {}
    for href, title in LINKED.findall(HIDDEN.sub(" ", html)):
        links.setdefault(" ".join(markup.unescape(TAGS.sub(" ", title)).split()), markup.unescape(href).strip())
    return links


def solicitations(html: str) -> list[dict[str, Any]]:
    """Each listing once, in page order: title, branches, the page's wording of its three dates, and its link."""
    lines = page_lines(html)
    start = next((i for i, line in enumerate(lines) if line.lower() == HEADING), None)
    if start is None:
        raise FundingListError("the page has no Open Funding Opportunities list")
    section = lines[start + 1:]
    section = section[:next((i for i, line in enumerate(section) if line.lower().startswith(LIST_END)), len(section))]
    links = _links(html)
    found: dict[str, dict[str, Any]] = {}
    for i, line in enumerate(section):
        label, title = _label(line)
        if label != "SOLICITATION":
            continue
        listing: dict[str, Any] = {"title": title, "branches": [], "pre_release": "", "open": "", "close": "",
                                   "link": links.get(title, "")}
        for later in section[i + 1:i + 1 + len(DATE_LABELS)]:
            date_label, value = _label(later)
            if date_label not in DATE_LABELS:
                break
            listing[DATE_LABELS[date_label]] = value
        branches: list[str] = []
        for earlier in reversed(section[:i]):
            named = _badges(earlier)
            if named is None:
                break
            branches = named + branches
        listing["branches"] = list(dict.fromkeys(branches))
        found.setdefault(title, listing)
    if not found and any(_badges(line) or parse_date(line) for line in section):
        raise FundingListError("the list has entries the scanner could not read (no labelled SOLICITATION blocks)")
    return list(found.values())


def fetch_page(site: Site, opener: Opener | None = None) -> str:
    """The site's Get Funded page, retried once."""
    opener = opener or urllib.request.urlopen
    problem = ""
    for _ in range(2):
        request = urllib.request.Request(site.page_url, headers={"User-Agent": USER_AGENT})
        try:
            with opener(request, timeout=TIMEOUT_S) as reply:
                return reply.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            problem = f"HTTP {exc.code}"
        except (urllib.error.URLError, OSError, ValueError) as exc:
            problem = type(exc).__name__
    raise FundingListError(f"{site.portal} did not answer ({problem})")


# ------------------------------------------------------------------------------ records

def parse_date(text: Any) -> date | None:
    """ "7 Oct 26", "13 APRIL 26" or "6 Sept. 2027" as a date; None for TBD, N/A or anything else."""
    found = DAY_MONTH_YEAR.fullmatch(" ".join(str(text or "").split()))
    if not found:
        return None
    day, word, year = found.groups()
    month = next((n for n, name in enumerate(MONTHS, 1) if name.startswith(word.lower())), None)
    if month is None:
        return None
    try:
        return date(int(year) + (2000 if len(year) == 2 else 0), month, int(day))
    except ValueError:
        return None


def derive_type(title: str) -> str:
    words = title.lower()
    stratfi, tacfi = "stratfi" in words, "tacfi" in words
    if stratfi or tacfi:
        return "STRATFI/TACFI" if stratfi and tacfi else "STRATFI" if stratfi else "TACFI"
    sbir, sttr = "sbir" in words, "sttr" in words
    if sbir and sttr:
        return "SBIR/STTR cycle"
    if sttr:
        return "STTR cycle"
    return "SBIR cycle" if sbir else "Solicitation"


def _shown(text: str) -> str:
    """A date as "7 Oct 2026", or the page's own wording when it is not a date."""
    parsed = parse_date(text)
    return f"{parsed.day} {MONTHS[parsed.month - 1][:3].title()} {parsed.year}" if parsed else text


def dates_sentence(listing: dict[str, Any]) -> str:
    parts = [f"{name} {_shown(text)}" for name, text in
             (("pre-release", str(listing.get("pre_release") or "").strip()), ("opens", str(listing.get("open") or "").strip()))
             if text]
    close = str(listing.get("close") or "").strip()
    if close:
        continuous = CONTINUOUS.search(close) and not parse_date(close)
        parts.append("takes submissions on a continuous basis" if continuous else f"closes {_shown(close)}")
    sentence = ", ".join(parts)
    return f"{sentence[:1].upper()}{sentence[1:]}." if sentence else ""


def call_url(link: Any, site: Site) -> str:
    """The listing's own link, made absolute: DSIP's topic search in place of DSIP's sign-in page, and
    the Get Funded page when the listing has no link."""
    link = str(link or "").strip()
    if not link or link.startswith("#"):
        return site.page_url
    absolute = urljoin(site.page_url, link)
    return TOPICS_URL if urlsplit(absolute).netloc.lower().endswith(DSIP_HOST) else absolute


def describe(listing: dict[str, Any], kind: str, site: Site, url: str) -> str:
    branches = listing.get("branches") or []
    topics = f", with U.S. {' and '.join(branches)} topics" if branches else ""
    parts = [f"{KINDS[kind]} listed on {site.portal}'s Get Funded page{topics}.", dates_sentence(listing)]
    if kind in CYCLES:
        parts.append(DSIP_NOTE.format(name=site.portal))
    if kind in SEQUENTIAL:
        parts.append(PHASE_II_NOTE)
    if url == TOPICS_URL:
        parts.append("The call's link opens DSIP's topic search.")
    elif url == site.page_url:
        parts.append(f"The call's link opens {site.portal}'s Get Funded page.")
    else:
        parts.append("The call's link opens the solicitation's own page.")
    return " ".join(part for part in parts if part)


def build_record(listing: dict[str, Any], now: datetime, site: Site) -> dict[str, Any]:
    title = " ".join(str(listing.get("title") or "").split())
    if not title:
        raise ValueError("the listing has no title")
    pre_release, opens, closes = (parse_date(listing.get(key)) for key in ("pre_release", "open", "close"))
    posted = pre_release or opens
    kind = derive_type(title)
    url = call_url(listing.get("link"), site)
    close_text = str(listing.get("close") or "").strip()
    key = site.prefix
    return {
        "id": f"{key}-" + re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-"),
        "portal": site.portal,
        "title": title,
        "type": kind,
        "department": site.department,
        "naics_code": "",
        "set_aside": "",
        "posted_date": posted.isoformat() if posted else "",
        "due_date": closes.isoformat() if closes else "",
        "description": describe(listing, kind, site, url),
        "url": url,
        "source_type": "scrape",
        "extra": {
            f"{key}_branches": list(listing.get("branches") or []),
            f"{key}_pre_release": pre_release.isoformat() if pre_release else None,
            f"{key}_open": opens.isoformat() if opens else None,
            # TBD, N/A or continuous: no deadline by design. A close date that cannot be read is not,
            # so the scan quality alert still counts it.
            f"{key}_no_deadline": bool(not closes and (NOT_SET.fullmatch(close_text) or CONTINUOUS.search(close_text))),
            f"{key}_closed": bool(closes and closes < now.astimezone(EASTERN).date()),
        },
    }


# ------------------------------------------------------------------------------ a run

def fetch_all(run_id: int, site: Site, limit: int | None = None, now: datetime | None = None,
              opener: Opener | None = None) -> dict[str, int]:
    """Store the site's listings. One whose close date has passed is skipped unless an earlier run
    stored it: that row is still refreshed, so it shows as closed."""
    now = now or datetime.now(timezone.utc)
    found = solicitations(fetch_page(site, opener))
    counts = {"found": len(found), "scraped": 0, "new": 0, "failed": 0}
    skipped = 0
    for listing in found:
        if limit is not None and counts["scraped"] >= limit:
            break
        try:
            record = build_record(listing, now, site)
        except (KeyError, TypeError, ValueError) as exc:
            counts["failed"] += 1
            log.warning("%s: could not read %r: %s: %s", site.portal, listing.get("title"), type(exc).__name__,
                        str(exc)[:120])
            continue
        if record["extra"][f"{site.prefix}_closed"] and get_call(record["id"]) is None:
            skipped += 1
            continue
        counts["scraped"] += 1
        if upsert_call(record, run_id):
            counts["new"] += 1
    log.info("%s: %d listings, %d stored (%d new), %d closed and never stored, %d unreadable",
             site.portal, counts["found"], counts["scraped"], counts["new"], skipped, counts["failed"])
    return counts
