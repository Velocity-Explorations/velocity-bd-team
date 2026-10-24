"""SSC Front Door as the pipeline sees it (see portals/registry.py for the contract)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from portals.shared.keyword_filter import filter_calls
from portals.ssc_front_door.records import PORTAL as PORTAL_NAME
from portals.ssc_front_door.scrape import fetch_all

SLUG = "ssc_front_door"
KEYWORDS_PATH = Path(__file__).resolve().parent / "keywords.yaml"   # this portal's filter settings
NOTES_PATH = Path(__file__).resolve().parent / "NOTES.md"           # what the assistant should know
HOW_TO_SUBMIT = (
    "Front Door takes no bids: register through the event's own link, answer a reposted notice on "
    "SAM.gov, or pitch an idea or product with Front Door's \"Share an Idea, Product, or Service\" form."
)


def fetch(page: Any, run_id: int, limit: int | None = None) -> dict[str, int]:
    """No browser: the pipeline passes page=None for this portal."""
    return fetch_all(run_id, limit=limit)


def filter_rows(rows: list[dict[str, Any]]) -> tuple[list[Any], list[Any]]:
    return filter_calls(rows, KEYWORDS_PATH)


PORTAL = {
    "slug": SLUG,
    "name": PORTAL_NAME,
    "fetch": fetch,
    "filter": filter_rows,
    "fetch_timeout": 300,   # every listing is checked against the ledger (PRO-550)
    "needs_browser": False,
    "keywords": KEYWORDS_PATH,
    "how_to_submit": HOW_TO_SUBMIT,
    "notes": NOTES_PATH,
}
