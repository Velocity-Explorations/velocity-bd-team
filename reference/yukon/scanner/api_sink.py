"""
Yukon — API Sink
Posts scanner results to the Yukon Prospector web app instead of Google Sheets.
"""

import json
import logging
import os
from typing import Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

log = logging.getLogger(__name__)

def _api_base() -> str:
    return os.environ.get("YUKON_API_URL", "http://127.0.0.1:3000")


def _headers() -> Dict[str, str]:
    token = os.environ.get("SCANNER_API_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _post(path: str, body: dict) -> Optional[dict]:
    url = f"{_api_base()}{path}"
    data = json.dumps(body).encode()
    req = Request(url, data=data, headers=_headers(), method="POST")
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except URLError as e:
        log.error(f"API request failed: {path} — {e}")
        return None


def _patch(path: str, body: dict) -> Optional[dict]:
    url = f"{_api_base()}{path}"
    data = json.dumps(body).encode()
    req = Request(url, data=data, headers=_headers(), method="PATCH")
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except URLError as e:
        log.error(f"API request failed: {path} — {e}")
        return None


def start_run(portal: str, metadata: Optional[dict] = None, profile: str = None) -> Optional[int]:
    """Create a scan run and return the run ID."""
    body = {"portal": portal, "metadata": metadata or {}}
    if profile:
        body["profile"] = profile
    result = _post("/api/scanner/runs", body)
    if result and "id" in result:
        return result["id"]
    return None


def complete_run(run_id: int, status: str = "completed", error: str = None):
    """Mark a scan run as completed or errored."""
    body = {"status": status}
    if error:
        body["error"] = error
    _patch(f"/api/scanner/runs/{run_id}", body)


def ingest_opportunities(opps: List[Dict], scan_run_id: Optional[int] = None, dry_run: bool = False, profile: str = None) -> int:
    """
    Post opportunities to the Yukon Prospector API.
    Returns number of opportunities inserted.
    """
    if not opps:
        return 0

    if dry_run:
        for opp in opps:
            log.info(f"[DRY RUN] Would ingest: {opp.get('title', '?')[:60]}")
        return len(opps)

    payload = []
    for opp in opps:
        item = {
            "portal": opp.get("portal", ""),
            "nativeId": opp.get("id", ""),
            "title": opp.get("title", ""),
            "agency": opp.get("department", ""),
            "postedDate": opp.get("posted_date", None),
            "dueDate": opp.get("due_date", None),
            "url": opp.get("url", ""),
            "naics": _parse_naics(opp.get("naics_code", "")),
            "setAside": opp.get("set_aside", ""),
            "estValue": opp.get("estimated_value", ""),
            "description": opp.get("description", ""),
            "descriptionSummary": opp.get("description_summary", ""),
            "scoreTotal": opp.get("yukon_score", None),
            "scoreTech": opp.get("score_tech", None),
            "scoreEcho": opp.get("score_echo", None),
            "scorePast": opp.get("score_past", None),
            "scoreVehicle": opp.get("score_vehicle", None),
            "scoreUrgency": opp.get("score_urgency", None),
            "aiSummary": opp.get("yukon_reasoning", ""),
        }
        if profile:
            item["profile"] = profile
        payload.append(item)

    body = {"opportunities": payload}
    if scan_run_id:
        body["scanRunId"] = scan_run_id

    result = _post("/api/scanner/ingest", body)
    if result:
        inserted = result.get("inserted", 0)
        skipped = result.get("skipped", 0)
        log.info(f"API ingest: {inserted} inserted, {skipped} skipped")
        return inserted
    return 0


def report_progress(
    run_id: int,
    stage: str,
    portal: str = None,
    status: str = "complete",
    message: str = None,
    count: int = None,
    detail: dict = None,
) -> bool:
    """Report pipeline progress for live UI updates."""
    if not run_id:
        return False
    body = {"stage": stage, "status": status}
    if portal:
        body["portal"] = portal
    if message:
        body["message"] = message
    if count is not None:
        body["count"] = count
    if detail:
        body["detail"] = detail
    result = _post(f"/api/scanner/runs/{run_id}/progress", body)
    return result is not None


def post_raw_listings(opps: List[Dict], portal: str, scan_run_id: Optional[int] = None, profile: str = None) -> int:
    """Post raw fetched listings for audit/tracking."""
    if not opps:
        return 0

    listings = []
    for opp in opps:
        listings.append({
            "portal": portal,
            "nativeId": opp.get("id", ""),
            "title": opp.get("title", ""),
            "agency": opp.get("department", ""),
            "postedDate": opp.get("posted_date", ""),
            "dueDate": opp.get("due_date", ""),
            "url": opp.get("url", ""),
            "naics": opp.get("naics_code", ""),
            "setAside": opp.get("set_aside", ""),
            "description": (opp.get("description", "") or "")[:500],
        })

    body = {"listings": listings}
    if scan_run_id:
        body["scanRunId"] = scan_run_id
    if profile:
        body["profile"] = profile

    result = _post("/api/scanner/raw-listings", body)
    if result:
        inserted = result.get("inserted", 0)
        log.info(f"Raw listings: {inserted} saved for {portal}")
        return inserted
    return 0


def update_listing_status(
    updates: List[Dict],
    scan_run_id: int,
) -> int:
    """Update filter status on raw listings (e.g. filtered, excluded, deduped, ingested)."""
    if not updates:
        return 0

    payload = []
    for u in updates:
        payload.append({
            "scanRunId": scan_run_id,
            "portal": u["portal"],
            "nativeId": u["nativeId"],
            "filterResult": u["filterResult"],
            "filterReason": u.get("filterReason", ""),
        })

    result = _patch("/api/scanner/raw-listings", {"updates": payload})
    if result:
        return result.get("updated", 0)
    return 0


def _parse_naics(raw) -> List[str]:
    """Parse NAICS codes from various formats into a list of strings."""
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(c) for c in raw]
    return [c.strip() for c in str(raw).split(",") if c.strip()]
