"""
Backfill Google Sheet with all seen opportunities.
Uses Google Sheets API directly with proper JSON array values.
"""

import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

SHEET_ID = "1loGmTp3jxfKqT9z5dfoYg9NAdliRXsccq7QtmdjYOw0"
ACCOUNT = "david@velocityexplorations.com"
DB_PATH = PROJECT_ROOT / "data" / "seen_opps.db"


def clean(val) -> str:
    if not val:
        return ""
    return str(val).strip().replace("\n", " ").replace("\r", "")


def get_access_token() -> str:
    """Get OAuth access token via gog."""
    result = subprocess.run(
        ["gog", "token", "-a", ACCOUNT, "--json"],
        capture_output=True, text=True, timeout=15
    )
    if result.returncode == 0:
        data = json.loads(result.stdout)
        return data.get("access_token", "")
    return ""


def sheets_append(token: str, values: list) -> bool:
    """Append a row to the sheet using Sheets API directly."""
    import urllib.request
    import urllib.parse

    url = (f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}"
           f"/values/Sheet1!A:N:append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS")

    body = json.dumps({"values": [values]}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"  API error: {e}")
        return False


def main():
    # Get token
    token = get_access_token()
    if not token:
        print("ERROR: Could not get OAuth token from gog")
        sys.exit(1)
    print(f"Got OAuth token ({len(token)} chars)")

    # Load dedup DB
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT id, portal, title, url, first_seen
        FROM seen_opps
        WHERE profile='velocity' AND id NOT LIKE 'test-%'
        ORDER BY first_seen DESC
    """).fetchall()
    conn.close()

    print(f"Backfilling {len(rows)} opportunities...")
    written = 0
    failed = 0

    for i, (opp_id, portal, title, url, first_seen) in enumerate(rows):
        date_found = first_seen[:10] if first_seen else ""

        # Clean URL — remove API endpoint URLs, use SAM.gov view URL
        clean_url = clean(url)
        if "api.sam.gov/prod" in clean_url and "noticeId" in clean_url:
            # Extract notice ID and build proper view URL
            clean_url = f"https://sam.gov/opp/{opp_id}/view"

        row = [
            date_found,           # A: Date Found
            clean(title),         # B: Title
            portal,               # C: Portal
            "",                   # D: Type
            "",                   # E: Agency
            "",                   # F: Posted
            "",                   # G: Due Date
            "",                   # H: NAICS
            "",                   # I: Set-Aside
            clean_url,            # J: URL
            "",                   # K: Relevant?
            "",                   # L: Notes
            "",                   # M: Yukon Score
            "",                   # N: Yukon Reasoning
        ]

        if sheets_append(token, row):
            written += 1
        else:
            failed += 1
            # Token may have expired — refresh
            token = get_access_token()
            if token:
                if sheets_append(token, row):
                    written += 1
                    failed -= 1

        if (i + 1) % 25 == 0:
            print(f"  Progress: {i+1}/{len(rows)} ({written} written)")

        time.sleep(0.3)  # Avoid rate limits

    print(f"\nDone. Written: {written} | Failed: {failed}")
    print(f"Sheet: https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")


if __name__ == "__main__":
    main()
