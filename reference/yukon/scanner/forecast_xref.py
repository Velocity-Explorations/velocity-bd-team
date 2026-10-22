"""
Yukon — NASA Forecast SAM.gov Cross-Reference
Reads the Forecasts tab, searches SAM.gov for matching live solicitations,
and updates the SAM.gov Match column (P) when a match is found.

Run weekly after the NASA forecast adapter:
  python -m scanner.forecast_xref --profile velocity
  python -m scanner.forecast_xref --profile velocity --dry-run
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

log = logging.getLogger(__name__)

SHEET_ID = "1loGmTp3jxfKqT9z5dfoYg9NAdliRXsccq7QtmdjYOw0"
SHEET_ACCOUNT = "david@velocityexplorations.com"
FORECASTS_TAB = "📋 Forecasts"

# Column positions (0-indexed in sheet values array, after header)
COL_TITLE = 2        # C
COL_NAICS = 5        # F
COL_MATCH = 15       # P — SAM.gov Match


def _load_api_key() -> str:
    env_path = PROJECT_ROOT / "configs" / "velocity" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("SAM_GOV_API_KEY="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("SAM_GOV_API_KEY", "")


def _read_forecasts() -> Tuple[List[List], int]:
    """
    Read all rows from Forecasts tab.
    Returns (rows_including_header, header_row_index=0).
    """
    result = subprocess.run(
        ["gog", "sheets", "read", SHEET_ID, f"{FORECASTS_TAB}!A1:P200",
         "-a", SHEET_ACCOUNT, "--json"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        log.error(f"Failed to read Forecasts tab: {result.stderr[:200]}")
        return [], 0
    data = json.loads(result.stdout)
    rows = data.get("values", []) or []
    return rows, 0


def _update_match_cell(row_num: int, match_text: str, dry_run: bool = False) -> bool:
    """Update the SAM.gov Match cell (column P) for a given 1-indexed row number."""
    if dry_run:
        log.info(f"[DRY RUN] Would update row {row_num} col P: {match_text[:60]}")
        return True
    # Read current row to preserve all existing values
    result = subprocess.run(
        ["gog", "sheets", "read", SHEET_ID, f"{FORECASTS_TAB}!P{row_num}",
         "-a", SHEET_ACCOUNT, "--json"],
        capture_output=True, text=True, timeout=20
    )
    # Write just the P cell
    escaped = match_text.replace("|", "/").replace("\n", " ")
    cmd = [
        "gog", "sheets", "update", SHEET_ID,
        f"'{FORECASTS_TAB}'!P{row_num}",
        escaped,
        "-a", SHEET_ACCOUNT, "--json"
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if r.returncode == 0:
        try:
            d = json.loads(r.stdout)
            return d.get("updatedCells", 0) > 0
        except Exception:
            return True
    log.error(f"Failed to update match cell row {row_num}: {r.stderr[:100]}")
    return False


def _search_sam_gov(title: str, naics: str, api_key: str) -> Optional[Dict]:
    """
    Search SAM.gov for a live solicitation matching the forecast title + NAICS.
    Returns the best match opp dict, or None.
    """
    import requests

    # Build a short keyword query from the title (first 5 meaningful words)
    stop_words = {"the", "a", "an", "of", "for", "and", "or", "in", "to", "with", "on", "at", "by"}
    words = [w for w in re.split(r'\W+', title.lower()) if w and w not in stop_words and len(w) > 2]
    keywords = " ".join(words[:5])
    if not keywords:
        return None

    base_url = "https://api.sam.gov/opportunities/v2/search"
    params = {
        "api_key": api_key,
        "q": keywords,
        "limit": 5,
        "postedFrom": "01/01/2025",
    }
    if naics:
        params["naicsCode"] = naics

    try:
        resp = requests.get(base_url, params=params, timeout=20)
        if resp.status_code == 429:
            log.warning("SAM.gov quota hit during cross-reference — stopping early")
            return None
        if resp.status_code != 200:
            log.warning(f"SAM.gov search returned {resp.status_code}")
            return None
        data = resp.json()
        hits = data.get("opportunitiesData", [])
        if not hits:
            return None

        # Score each hit by keyword overlap with forecast title
        title_words = set(words)
        best = None
        best_score = 0
        for hit in hits:
            hit_title = (hit.get("title") or "").lower()
            hit_words = set(re.split(r'\W+', hit_title))
            overlap = len(title_words & hit_words)
            if overlap > best_score:
                best_score = overlap
                best = hit

        if best and best_score >= 2:
            return best
        return None

    except Exception as e:
        log.error(f"SAM.gov search error: {e}")
        return None


def run_crossref(profile_name: str = "velocity", dry_run: bool = False):
    """Main cross-reference routine."""
    api_key = _load_api_key()
    if not api_key:
        log.error("No SAM.gov API key — cannot run cross-reference")
        return

    rows, _ = _read_forecasts()
    if not rows:
        log.info("Forecasts tab is empty — nothing to cross-reference")
        return

    header = rows[0]
    data_rows = rows[1:]  # skip header

    total = 0
    matched = 0
    already_matched = 0
    no_match = 0

    log.info(f"Cross-referencing {len(data_rows)} forecasts against SAM.gov...")

    for i, row in enumerate(data_rows):
        row_num = i + 2  # 1-indexed, +1 for header

        # Pad row if needed
        while len(row) < 16:
            row.append("")

        title = row[COL_TITLE] if len(row) > COL_TITLE else ""
        naics = row[COL_NAICS] if len(row) > COL_NAICS else ""
        existing_match = row[COL_MATCH] if len(row) > COL_MATCH else ""

        if not title:
            continue

        total += 1

        # Skip rows already matched
        if existing_match and existing_match.strip() and existing_match.strip().lower() not in ("", "forecast", "no match"):
            already_matched += 1
            log.debug(f"Row {row_num} already has match: {existing_match[:40]}")
            continue

        # Search SAM.gov
        match = _search_sam_gov(title, naics, api_key)
        time.sleep(0.5)  # Rate limit buffer

        if match:
            opp_id = match.get("noticeId", "")
            opp_title = match.get("title", "")[:80]
            posted = (match.get("postedDate") or "")[:10]
            due = (match.get("responseDeadLine") or "")[:10]
            sam_url = f"https://sam.gov/opp/{opp_id}/view" if opp_id else ""

            match_text = f"✅ LIVE on SAM.gov: {opp_title} | Posted: {posted} | Due: {due} | {sam_url}"
            log.info(f"Row {row_num} MATCH: {title[:40]} → {opp_title[:40]}")

            _update_match_cell(row_num, match_text, dry_run=dry_run)
            matched += 1
        else:
            # Mark as checked with no match (so we don't re-check every week)
            _update_match_cell(row_num, f"No match as of {datetime.now(timezone.utc).strftime('%Y-%m-%d')}", dry_run=dry_run)
            no_match += 1

    log.info(
        f"Cross-reference complete: {matched} matched, {no_match} no match, "
        f"{already_matched} already had match (of {total} total)"
    )
    return matched, no_match, total


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Yukon NASA Forecast SAM.gov Cross-Reference")
    parser.add_argument("--profile", default="velocity")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = run_crossref(args.profile, args.dry_run)
    if result:
        matched, no_match, total = result
        print(f"\nDone: {matched}/{total} forecasts found on SAM.gov as live solicitations")
