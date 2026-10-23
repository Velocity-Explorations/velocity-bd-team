"""SpaceWERX as the pipeline sees it (see portals/registry.py for the contract).

Its Get Funded page uses AFWERX's site template, so both adapters read it with
portals/shared/funding_list.py.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from portals.shared.funding_list import Site, fetch_all
from portals.shared.keyword_filter import filter_calls

SLUG = "spacewerx"
SITE = Site(portal="SpaceWERX", prefix="spacewerx", page_url="https://spacewerx.us/get-funded/",
            department="U.S. Space Force")
KEYWORDS_PATH = Path(__file__).resolve().parent / "keywords.yaml"   # this portal's filter settings
NOTES_PATH = Path(__file__).resolve().parent / "NOTES.md"           # what the assistant should know
HOW_TO_SUBMIT = (
    "Follow the listing's link. SBIR and STTR cycles take proposals through DSIP, the DoD SBIR/STTR "
    "Innovation Portal (dodsbirsttr.mil), while they are open; STRATFI and TACFI notices say how on "
    "SpaceWERX's STRATFI/TACFI page and need a current or recent Phase II award."
)


def fetch(page: Any, run_id: int, limit: int | None = None) -> dict[str, int]:
    """No browser: the pipeline passes page=None for this portal."""
    return fetch_all(run_id, SITE, limit=limit)


def filter_rows(rows: list[dict[str, Any]]) -> tuple[list[Any], list[Any]]:
    return filter_calls(rows, KEYWORDS_PATH)


PORTAL = {
    "slug": SLUG,
    "name": SITE.portal,
    "fetch": fetch,
    "filter": filter_rows,
    "fetch_timeout": 120,
    "needs_browser": False,
    "keywords": KEYWORDS_PATH,
    "how_to_submit": HOW_TO_SUBMIT,
    "notes": NOTES_PATH,
}
