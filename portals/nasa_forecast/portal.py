"""NASA's acquisition forecast as the pipeline sees it (see portals/registry.py for the contract)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from portals.nasa_forecast.records import PORTAL as PORTAL_NAME
from portals.nasa_forecast.scrape import fetch_all
from portals.shared.keyword_filter import filter_calls

SLUG = "nasa_forecast"
KEYWORDS_PATH = Path(__file__).resolve().parent / "keywords.yaml"   # this portal's filter settings
NOTES_PATH = Path(__file__).resolve().parent / "NOTES.md"           # what the assistant should know
HOW_TO_SUBMIT = (
    "Nothing to submit yet: a forecast row is a planned buy. Watch SAM.gov for the solicitation in the "
    "quarter NASA expects to release it, and reach the row's technical or small business contact before then."
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
