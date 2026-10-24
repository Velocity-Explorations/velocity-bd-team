"""SAM.gov's public Opportunities API, read with one key under a request budget.

    budget = Budget(900)
    notices = search("541715", today, key, opener, budget)   # open notices for one NAICS code
    notices = search_office("INTELLIGENCE ADVANCED RESEARCH PROJECTS ACTIVITY", today, key, opener, budget)
    text = description(raw["description"], key, opener, budget)

Every call costs one request of the key's daily limit, a description included (the search
result holds only a link to it). SAM.gov answers 429 once the day's limit is reached; that
raises SamQuota and the run keeps what it has. Requests go over IPv4 only: api.sam.gov also
publishes an IPv6 address, which hangs from the scan PC (docs: portals/sam_gov/NOTES.md).
The key is added to each request at the last moment and never appears in a message or log.
"""
from __future__ import annotations

import html
import http.client
import json
import logging
import re
import socket
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import date, timedelta
from typing import Any

from portals.sam_gov.records import DESCRIPTION_CHARS

SEARCH_URL = "https://api.sam.gov/opportunities/v2/search"
PAGE_SIZE = 1000
MAX_PAGES = 10
TIMEOUT_S = 120
POSTED_WINDOW_DAYS = 364     # SAM.gov allows at most a year between postedFrom and postedTo
USER_AGENT = "velocity-bd-team scanner (Velocity Explorations)"

Opener = Callable[..., Any]   # an urlopen-like callable, or a test's stand-in

log = logging.getLogger("sam_gov.api")


class SamError(RuntimeError):
    """SAM.gov did not answer as expected. The pipeline records it and alerts."""


class SamQuota(SamError):
    """The key's daily limit, or this run's budget, is spent."""


class Budget:
    """Counts requests so a run never spends more than its share of the key's daily limit."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.used = 0
        self._lock = threading.Lock()

    def spend(self) -> None:
        with self._lock:
            if self.used >= self.limit:
                raise SamQuota(f"this run's budget of {self.limit} requests is spent")
            self.used += 1


# --------------------------------------------------------------------------- IPv4 only

def ipv4_connect(address: tuple[str, int], timeout: Any = socket._GLOBAL_DEFAULT_TIMEOUT,  # type: ignore[attr-defined]
                 source_address: Any = None) -> socket.socket:
    """socket.create_connection, but to the host's IPv4 addresses only."""
    host, port = address
    error: OSError | None = None
    for *_, sockaddr in socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM):
        try:
            return socket.create_connection((sockaddr[0], port), timeout, source_address)
        except OSError as exc:
            error = exc
    raise error or OSError(f"no IPv4 address for {host}")


class _IPv4HTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._create_connection = ipv4_connect   # TLS still checks the host name


class _IPv4HTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req: urllib.request.Request) -> Any:
        return self.do_open(_IPv4HTTPSConnection, req, context=self._context)  # type: ignore[attr-defined]


ipv4_urlopen: Opener = urllib.request.build_opener(_IPv4HTTPSHandler()).open


# ---------------------------------------------------------------------------- requests

def _with_key(url: str, key: str) -> str:
    return url + ("&" if "?" in url else "?") + urllib.parse.urlencode({"api_key": key})


def _get_json(url: str, key: str, opener: Opener, budget: Budget, retries: int = 1) -> Any:
    """One GET, retried once on failure. None when SAM.gov answers 404. Spends the budget per try."""
    for attempt in range(retries + 1):
        budget.spend()
        request = urllib.request.Request(_with_key(url, key), headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        try:
            with opener(request, timeout=TIMEOUT_S) as reply:
                return json.loads(reply.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise SamQuota("SAM.gov says this key's daily limit is reached") from None
            if exc.code == 404:
                return None
            problem = f"HTTP {exc.code}"
        except (urllib.error.URLError, OSError, ValueError) as exc:
            problem = type(exc).__name__
        if attempt < retries:
            log.info("SAM.gov request failed (%s); trying once more", problem)
    raise SamError(f"SAM.gov did not answer ({problem})") from None


def search(naics: str, today: date, key: str, opener: Opener, budget: Budget) -> list[dict[str, Any]]:
    """Every open notice posted in the last year under one NAICS code."""
    return _search({"ncode": naics}, f"NAICS {naics}", today, key, opener, budget)


def search_office(name: str, today: date, key: str, opener: Opener, budget: Budget) -> list[dict[str, Any]]:
    """Every open notice posted in the last year by one organization, whatever its NAICS codes. SAM.gov
    matches organizationName against department and sub-tier names; v2 ignores the older subtier
    parameter and returns every notice (PRO-537)."""
    return _search({"organizationName": name}, name, today, key, opener, budget)


def search_title(words: str, today: date, key: str, opener: Opener, budget: Budget) -> list[dict[str, Any]]:
    """Every open notice posted in the last year whose title holds `words`, whatever its NAICS codes:
    TRMC posts some notices with none (PRO-548)."""
    return _search({"title": words}, f"title {words}", today, key, opener, budget)


def _search(where: dict[str, str], label: str, today: date, key: str, opener: Opener,
            budget: Budget) -> list[dict[str, Any]]:
    """Every open notice (response deadline today or later) posted in the last year that matches `where`."""
    params = {
        **where,
        "postedFrom": (today - timedelta(days=POSTED_WINDOW_DAYS)).strftime("%m/%d/%Y"),
        "postedTo": today.strftime("%m/%d/%Y"),
        "rdlfrom": today.strftime("%m/%d/%Y"),
        "limit": PAGE_SIZE,
    }
    found: list[dict[str, Any]] = []
    for page in range(MAX_PAGES):
        offset = page * PAGE_SIZE
        query = urllib.parse.urlencode({**params, "offset": offset})
        data = _get_json(f"{SEARCH_URL}?{query}", key, opener, budget) or {}
        batch = data.get("opportunitiesData") or []
        found += batch
        if offset + PAGE_SIZE >= int(data.get("totalRecords") or 0) or len(batch) < PAGE_SIZE:
            return found
    log.warning("%s: more than %d pages of open notices; read the first %d", label, MAX_PAGES, len(found))
    return found


BREAKS = re.compile(r"(?i)<br\s*/?>|</(?:p|div|li|h[1-6]|tr)>")
TAGS = re.compile(r"<[^>]+>")


def plain_text(markup: str) -> str:
    """HTML to text: one line per paragraph or list item, entities decoded, spaces collapsed."""
    text = html.unescape(TAGS.sub(" ", BREAKS.sub("\n", markup))).replace("\xa0", " ")
    return "\n".join(" ".join(line.split()) for line in text.splitlines() if line.strip())


def description(url: str | None, key: str, opener: Opener, budget: Budget) -> str:
    """A notice's description as plain text, cut to DESCRIPTION_CHARS; "" when SAM.gov has none.
    Not retried: a description that fails is read again on the next run."""
    if not url or not str(url).startswith("https://api.sam.gov/"):
        return ""
    data = _get_json(str(url), key, opener, budget, retries=0) or {}
    return plain_text(str(data.get("description") or ""))[:DESCRIPTION_CHARS]
