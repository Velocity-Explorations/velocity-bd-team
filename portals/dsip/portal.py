"""DSIP as the pipeline sees it (see portals/registry.py for the contract): the Defense Department's SBIR and STTR
topics, one call a topic, from SBIR.gov's copy and from DSIP DOCX files a person drops in data/dsip/inbox (David,
16 Nov 2026)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from portals.dsip.records import PORTAL as PORTAL_NAME
from portals.dsip.scrape import fetch_all
from portals.dsip.watch import missed_releases
from portals.shared.keyword_filter import filter_calls

SLUG = "dsip"
KEYWORDS_PATH = Path(__file__).resolve().parent / "keywords.yaml"   # this portal's filter settings
NOTES_PATH = Path(__file__).resolve().parent / "NOTES.md"           # what the assistant should know
HOW_TO_SUBMIT = (
    "Through DSIP, the DoD SBIR/STTR Innovation Portal (dodsbirsttr.mil), before the topic closes (12:00 p.m. ET on "
    "the close date): find the topic in DSIP's topic search, read its solicitation's instructions, and submit the "
    "proposal there. Submitting needs a DSIP account."
)


def fetch(page: Any, run_id: int, limit: int | None = None) -> dict[str, int]:
    """No browser: the pipeline passes page=None for this portal."""
    return fetch_all(run_id, limit=limit)


def filter_rows(rows: list[dict[str, Any]]) -> tuple[list[Any], list[Any]]:
    return filter_calls(rows, KEYWORDS_PATH)


def watch(run_id: int) -> list[str]:
    """After a completed scan: an alert for each open DoD cycle with no topics in the ledger."""
    return missed_releases(run_id)


PORTAL = {
    "slug": SLUG,
    "name": PORTAL_NAME,
    "fetch": fetch,
    "filter": filter_rows,
    "fetch_timeout": 600,   # about 90 requests a second apart, with room for a slow SBIR.gov
    "needs_browser": False,
    "keywords": KEYWORDS_PATH,
    "how_to_submit": HOW_TO_SUBMIT,
    "notes": NOTES_PATH,
    "watch": watch,
}
