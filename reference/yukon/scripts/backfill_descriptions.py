#!/usr/bin/env python3
"""
One-shot backfill: fetch SAM.gov descriptions for opportunities that still
have a URL instead of text, re-summarize with Claude, and update the DB
via the ingest API (upsert).

Usage:
    python scripts/backfill_descriptions.py --profile <profile>
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen

import requests as http_requests

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
from scanner.summarize import summarize_description

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&#\d+;", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_desc(url: str, api_keys: list[str]) -> str:
    for key in api_keys:
        try:
            resp = http_requests.get(url, params={"api_key": key}, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                raw = data.get("description", "")
                if raw:
                    return strip_html(raw)[:4000]
            elif resp.status_code == 429:
                log.debug(f"  429 on key ...{key[-4:]}, trying next")
                continue
            else:
                log.debug(f"  HTTP {resp.status_code}")
        except Exception as e:
            log.warning(f"  Fetch error: {e}")
    return ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default="velocity")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    env_path = BASE_DIR / "configs" / args.profile / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)

    api_url = os.environ.get("YUKON_API_URL", "http://127.0.0.1:3000")
    token = os.environ.get("SCANNER_API_TOKEN", "")
    db_url = os.environ.get("DATABASE_URL", "postgres://yukon:yukon_dev@127.0.0.1:54329/yukon_prospector")

    api_keys = []
    for k in ["SAM_GOV_API_KEY_2", "SAM_GOV_RFP_AGENT_KEY", "SAM_GOV_API_KEY", "SAM_GOV_API_KEY_3"]:
        v = os.environ.get(k)
        if v:
            api_keys.append(v)

    if not api_keys:
        log.error("No SAM.gov API keys found")
        return

    log.info(f"Using {len(api_keys)} API keys")

    # Query DB directly for opps with URL descriptions
    import psycopg2
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, native_id, title, agency, description, portal,
               posted_date, due_date, url, naics, set_aside
        FROM opportunities
        WHERE profile = %s AND portal = 'SAM.gov'
          AND description LIKE 'https://api.sam.gov/%%'
        ORDER BY id
    """, (args.profile,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    log.info(f"Found {len(rows)} opps with URL descriptions")
    if not rows:
        return

    fixed = 0
    for i, row in enumerate(rows, 1):
        db_id, native_id, title, agency, desc_url, portal, posted, due, url, naics, set_aside = row
        short_title = (title or "?")[:60]

        log.info(f"[{i}/{len(rows)}] {short_title}")

        new_desc = fetch_desc(desc_url, api_keys)
        if not new_desc:
            log.warning(f"  Could not fetch description, skipping")
            continue

        log.info(f"  Got {len(new_desc)} chars, summarizing...")
        summary = summarize_description(new_desc, title=title or "", agency=agency or "")
        log.info(f"  Summary: {(summary or '(empty)')[:80]}")

        if args.dry_run:
            log.info(f"  [DRY RUN] would update")
            fixed += 1
            continue

        payload = {
            "opportunities": [{
                "portal": portal,
                "nativeId": native_id,
                "title": title,
                "agency": agency or "",
                "postedDate": posted.isoformat() if posted else None,
                "dueDate": due.isoformat() if due else None,
                "url": url or "",
                "naics": naics or "",
                "setAside": set_aside or "",
                "description": new_desc,
                "descriptionSummary": summary,
                "profile": args.profile,
            }],
        }

        req = Request(
            f"{api_url}/api/scanner/ingest",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        result = json.loads(urlopen(req, timeout=30).read())
        log.info(f"  Ingested: {result}")
        fixed += 1
        time.sleep(0.3)

    log.info(f"Done: {fixed}/{len(rows)} descriptions backfilled")


if __name__ == "__main__":
    main()
