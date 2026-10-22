"""SAM.gov as the pipeline sees it (see portals/registry.py for the contract)."""
from __future__ import annotations

from typing import Any

from portals.sam_gov.records import KEYWORDS_PATH, PORTAL as PORTAL_NAME, SEARCH_PATH
from portals.sam_gov.scrape import fetch_all
from portals.shared.keyword_filter import filter_calls

SLUG = "sam_gov"
NOTES_PATH = KEYWORDS_PATH.parent / "NOTES.md"   # what the assistant should know
HOW_TO_SUBMIT = (
    "Each notice says how to respond: usually by email to the contracting officer it names, sometimes "
    "through a system such as PIEE. Open the notice on SAM.gov and follow its instructions and deadline."
)
__all__ = ["PORTAL", "SEARCH_PATH", "KEYWORDS_PATH", "NOTES_PATH"]


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
    "fetch_timeout": 1800,
    "needs_browser": False,
    "keywords": KEYWORDS_PATH,
    "how_to_submit": HOW_TO_SUBMIT,
    "notes": NOTES_PATH,
}
