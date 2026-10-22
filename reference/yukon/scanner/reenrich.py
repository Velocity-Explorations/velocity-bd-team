"""
Yukon — Re-enrichment script
Pulls existing SAM.gov opps from the DB, fetches their attachments,
re-scores with the current scorer, and updates the DB via the ingest API.
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.request import Request, urlopen

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from scanner.attachments import enrich_with_attachments, cleanup_rejected, _extract_text
from scanner.velocity_scorer import score_opportunity
from scanner.portals.sam_gov import _load_api_keys, _normalize, _strip_html

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

SAM_API_BASE = "https://api.sam.gov/opportunities/v2/search"
SAM_RESOURCES_API = "https://sam.gov/api/prod/opps/v3/opportunities"

def _load_config():
    env_path = Path(__file__).parent.parent / "configs" / "velocity" / ".env"
    config = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                config[k.strip()] = v.strip()
    return config


def _db_query(sql: str) -> List[Dict]:
    """Query the Yukon Prospector DB via docker exec."""
    import subprocess

    prospector_dir = Path(__file__).parent.parent.parent / "prospector"
    if not prospector_dir.exists():
        prospector_dir = Path(__file__).parent.parent

    cmd = [
        "docker", "compose", "exec", "-T", "postgres",
        "psql", "-U", "yukon", "-d", "yukon_prospector",
        "-t", "-A", "-F", "\t",
        "-c", sql,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=str(prospector_dir))
    if result.returncode != 0:
        log.error(f"DB query failed: {result.stderr}")
        return []

    rows = []
    for line in result.stdout.strip().split("\n"):
        if line.strip():
            rows.append(line.split("\t"))
    return rows


def _fetch_resources(notice_id: str, api_key: str) -> List[Dict]:
    """Fetch attachment details from the v3 resources endpoint.
    Returns list of dicts with 'name' and 'link' keys matching _rank_attachments format."""
    try:
        url = f"{SAM_RESOURCES_API}/{notice_id}/resources"
        resp = requests.get(url, params={"api_key": api_key}, timeout=20)
        if resp.status_code != 200:
            return []
        data = resp.json()
        att_list = data.get("_embedded", {}).get("opportunityAttachmentList", [])
        results = []
        for group in att_list:
            for att in group.get("attachments", []):
                resource_id = att.get("resourceId", "")
                name = att.get("name", "")
                if resource_id and name:
                    link = f"https://sam.gov/api/prod/opps/v3/opportunities/resources/files/{resource_id}/download"
                    results.append({"name": name, "link": link})
        return results
    except Exception as e:
        log.debug(f"Resource fetch failed for {notice_id}: {e}")
        return []


def _fetch_opp_details(notice_id: str, api_key: str) -> Optional[Dict]:
    """Fetch a single opportunity from SAM.gov API to get resourceLinks."""
    try:
        from datetime import datetime, timedelta
        today = datetime.now()
        year_ago = today - timedelta(days=364)
        params = {
            "api_key": api_key,
            "noticeid": notice_id,
            "limit": 1,
            "postedFrom": year_ago.strftime("%m/%d/%Y"),
            "postedTo": today.strftime("%m/%d/%Y"),
        }
        resp = requests.get(SAM_API_BASE, params=params, timeout=30)
        if resp.status_code == 429:
            log.warning(f"SAM.gov API rate limited (429)")
            return "RATE_LIMITED"
        if resp.status_code != 200:
            log.warning(f"SAM.gov API error ({resp.status_code}) for {notice_id}: {resp.text[:200]}")
            return None

        data = resp.json()
        opps = data.get("opportunitiesData", [])
        if not opps:
            return None

        return opps[0]
    except Exception as e:
        log.warning(f"SAM.gov API error for {notice_id}: {e}")
        return None


def _ingest_opps(opps: List[Dict], config: dict):
    """POST updated opps to the Yukon Prospector ingest API."""
    api_url = config.get("YUKON_API_URL", "http://127.0.0.1:3000")
    token = config.get("SCANNER_API_TOKEN", "")

    payload = []
    for opp in opps:
        item = {
            "portal": opp.get("portal", "SAM.gov"),
            "nativeId": opp.get("id", ""),
            "title": opp.get("title", ""),
            "agency": opp.get("department", ""),
            "postedDate": opp.get("posted_date") or None,
            "dueDate": opp.get("due_date") or None,
            "url": opp.get("url", ""),
            "naics": [opp["naics_code"]] if opp.get("naics_code") else None,
            "setAside": opp.get("set_aside", ""),
            "estValue": opp.get("estimated_value", ""),
            "description": opp.get("description", ""),
            "scoreTotal": opp.get("yukon_score"),
            "scoreTech": opp.get("score_tech"),
            "scoreEcho": opp.get("score_echo"),
            "scorePast": opp.get("score_past"),
            "scoreVehicle": opp.get("score_vehicle"),
            "scoreUrgency": opp.get("score_urgency"),
            "aiSummary": opp.get("yukon_reasoning", ""),
        }
        payload.append(item)

    body = json.dumps({"opportunities": payload}).encode()
    req = Request(
        f"{api_url}/api/scanner/ingest",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            log.info(f"Ingest: {result.get('inserted', 0)} updated")
            return result
    except Exception as e:
        log.error(f"Ingest failed: {e}")
        return None


def reenrich(
    status_filter: str = "pending",
    limit: int = 0,
    skip_attachments: bool = False,
    dry_run: bool = False,
):
    """
    Main re-enrichment flow.

    Args:
        status_filter: DB review_status to target ("pending", "valid", "all")
        limit: Max opps to process (0 = all)
        skip_attachments: If True, skip SAM API calls and just re-score with existing data
        dry_run: If True, score but don't update DB
    """
    config = _load_config()
    api_keys = _load_api_keys()

    if not api_keys and not skip_attachments:
        log.error("No SAM.gov API keys found")
        return

    # Pull opps from DB
    where = "native_id NOT LIKE 'sheet-%'"
    if not skip_attachments:
        where += " AND portal = 'SAM.gov'"
    if status_filter != "all":
        where += f" AND review_status = '{status_filter}'"
    limit_clause = f" LIMIT {limit}" if limit else ""

    sql = f"""
        SELECT native_id, title, agency, description, due_date, posted_date,
               url, naics, set_aside, est_value, review_status
        FROM opportunities
        WHERE {where}
        ORDER BY id{limit_clause}
    """
    rows = _db_query(sql)
    if not rows:
        log.info("No opps to process")
        return

    log.info(f"Processing {len(rows)} opps (status={status_filter})")

    # Build opp dicts
    opps = []
    for row in rows:
        if len(row) < 11:
            continue
        opp = {
            "id": row[0],
            "title": row[1],
            "department": row[2] if row[2] != "\\N" else "",
            "description": row[3] if row[3] != "\\N" else "",
            "due_date": row[4] if row[4] != "\\N" else "",
            "posted_date": row[5] if row[5] != "\\N" else "",
            "url": row[6] if row[6] != "\\N" else "",
            "naics_code": row[7].strip("{}") if row[7] and row[7] != "\\N" else "",
            "set_aside": row[8] if row[8] != "\\N" else "",
            "estimated_value": row[9] if row[9] != "\\N" else "",
            "portal": "SAM.gov",
            "review_status": row[10] if row[10] != "\\N" else "pending",
            "type": "",
            "resource_links": [],
        }
        opps.append(opp)

    log.info(f"Loaded {len(opps)} opps from DB")

    # Phase 1: Fetch resourceLinks from SAM.gov API (if not skipping)
    if not skip_attachments:
        key_idx = len(api_keys) - 1
        fetched = 0
        skipped = 0
        all_exhausted = False

        for i, opp in enumerate(opps):
            if all_exhausted:
                break

            notice_id = opp["id"]
            log.info(f"[{i+1}/{len(opps)}] Fetching details for {notice_id}: {opp['title'][:50]}")

            raw = _fetch_opp_details(notice_id, api_keys[key_idx])

            if raw == "RATE_LIMITED":
                log.warning(f"Key {key_idx+1}/{len(api_keys)} rate limited, rotating...")
                key_idx -= 1
                if key_idx < 0:
                    log.error("All API keys exhausted")
                    all_exhausted = True
                    continue
                raw = _fetch_opp_details(notice_id, api_keys[key_idx])
                if raw == "RATE_LIMITED":
                    log.error("New key also rate limited, stopping")
                    all_exhausted = True
                    continue

            if raw is None:
                skipped += 1
                continue

            opp["resource_links"] = _fetch_resources(notice_id, api_keys[key_idx])

            raw_desc = raw.get("description") or ""
            if raw_desc and raw_desc.startswith("https://api.sam.gov/"):
                try:
                    desc_resp = requests.get(raw_desc, params={"api_key": api_keys[key_idx]}, timeout=30)
                    if desc_resp.status_code == 200:
                        desc_data = desc_resp.json()
                        raw_html = desc_data.get("description", "")
                        opp["description"] = _strip_html(raw_html)[:4000]
                except Exception:
                    pass
            elif raw_desc:
                opp["description"] = _strip_html(raw_desc)[:4000]

            opp_type_raw = str(raw.get("type") or raw.get("opportunityType") or "")
            type_map = {
                "o": "Solicitation", "p": "Pre-solicitation",
                "k": "Combined Synopsis", "r": "Sources Sought",
                "s": "SBIR/STTR",
            }
            opp["type"] = type_map.get(opp_type_raw.lower(), opp_type_raw.capitalize())

            fetched += 1
            time.sleep(0.15)

        log.info(f"Fetched details for {fetched}/{len(opps)} opps ({skipped} not found on SAM.gov)")

        # Phase 2: Download and extract attachments
        opps_with_links = [o for o in opps if o.get("resource_links")]
        if opps_with_links:
            log.info(f"Downloading attachments for {len(opps_with_links)} opps...")
            enrich_with_attachments(opps_with_links, api_keys)
            enriched = sum(1 for o in opps_with_links if o.get("attachment_text"))
            log.info(f"Enriched {enriched}/{len(opps_with_links)} opps with attachment text")

    # Phase 3: Re-score all opps
    log.info("Re-scoring all opps...")
    scored = []
    for i, opp in enumerate(opps):
        try:
            result = score_opportunity(opp)
            scored.append(result)
            if (i + 1) % 25 == 0:
                log.info(f"Scored {i+1}/{len(opps)}...")
        except Exception as e:
            log.error(f"Scoring error for {opp.get('title', '?')[:40]}: {e}")
            opp["yukon_score"] = 3.0
            opp["yukon_reasoning"] = f"Scoring error: {str(e)[:60]}"
            scored.append(opp)

    log.info(f"Scored {len(scored)} opps")

    # Show score distribution
    scores = [o.get("yukon_score", 0) for o in scored]
    high = sum(1 for s in scores if s >= 7)
    mid = sum(1 for s in scores if 4 <= s < 7)
    low = sum(1 for s in scores if s < 4)
    log.info(f"Score distribution: {high} high (>=7), {mid} mid (4-7), {low} low (<4)")

    if scored:
        top5 = sorted(scored, key=lambda x: x.get("yukon_score", 0), reverse=True)[:5]
        log.info("Top 5:")
        for o in top5:
            log.info(f"  {o.get('yukon_score', 0):.1f} — {o.get('title', '?')[:60]}")

    # Phase 4: Update DB
    if not dry_run and scored:
        log.info(f"Updating {len(scored)} opps in DB...")
        batch_size = 50
        for i in range(0, len(scored), batch_size):
            batch = scored[i:i + batch_size]
            _ingest_opps(batch, config)
            time.sleep(0.1)
        log.info("DB update complete")
    elif dry_run:
        log.info("[DRY RUN] Would have updated DB")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Re-enrich existing SAM.gov opportunities")
    parser.add_argument("--status", default="pending", help="Filter by review_status (pending, valid, all)")
    parser.add_argument("--limit", type=int, default=0, help="Max opps to process (0=all)")
    parser.add_argument("--skip-attachments", action="store_true", help="Skip API calls, just re-score existing data")
    parser.add_argument("--dry-run", action="store_true", help="Score but don't update DB")
    args = parser.parse_args()

    reenrich(
        status_filter=args.status,
        limit=args.limit,
        skip_attachments=args.skip_attachments,
        dry_run=args.dry_run,
    )
