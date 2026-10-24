"""DOE SBIR as the pipeline sees it (see portals/registry.py for the contract)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from portals.doe_sbir.records import PORTAL as PORTAL_NAME
from portals.doe_sbir.scrape import fetch_all
from portals.shared.keyword_filter import filter_calls

SLUG = "doe_sbir"
KEYWORDS_PATH = Path(__file__).resolve().parent / "keywords.yaml"   # this portal's filter settings
NOTES_PATH = Path(__file__).resolve().parent / "NOTES.md"           # what the assistant should know
HOW_TO_SUBMIT = (
    "Through DOE's SBIR/STTR Application Hub (sbir-sttr.connectwerx.org): request an account on ATI's "
    "Acquisition Management Portal (AMP), then respond to the open solicitation there before its "
    "deadline. A Phase I application starts with a short pitch; DOE invites the strongest to apply in full."
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
    "fetch_timeout": 120,
    "needs_browser": False,
    "keywords": KEYWORDS_PATH,
    "how_to_submit": HOW_TO_SUBMIT,
    "notes": NOTES_PATH,
}
