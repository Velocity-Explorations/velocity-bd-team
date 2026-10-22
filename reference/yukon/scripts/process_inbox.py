"""
Yukon — Inbox Review Processor
Reads the Inbox tab, moves rows to Valid or Not Valid based on Relevant column.

Usage:
  python scripts/process_inbox.py           # live run
  python scripts/process_inbox.py --dry-run # preview only
"""

import json
import re
from pathlib import Path
import subprocess
import sys
import time

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
from scanner.rfp_attachments import download_all_sam_attachments, _extract_sam_notice_id

SHEET_ID = "1loGmTp3jxfKqT9z5dfoYg9NAdliRXsccq7QtmdjYOw0"
ACCOUNT = "david@velocityexplorations.com"

INBOX_TAB = "📥 Inbox"
VALID_TAB = "✅ Valid"
NOT_VALID_TAB = "❌ Not Valid"
MAX_ROWS = 600  # Read up to this many rows from inbox


def _load_slack_webhook() -> str:
    """Load Slack webhook URL from profile .env."""
    from pathlib import Path
    env_path = Path(__file__).parent.parent / "configs" / "velocity" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("SLACK_WEBHOOK_BD_PROSPECTOR="):
                return line.split("=", 1)[1].strip()
    return ""


BD_CHANNEL_ID = "C0AN8AMM4AW"  # #bd-prospector


def post_to_slack(opp_row: list, webhook_url: str = None):
    """Post an approved opportunity to Slack #bd-prospector via bot token.
    Bot token required so ❌ reactions can delete the message.
    Inbox: A=Date B=Relevant C=Portal D=Title E=Desc F=Type G=Agency H=Posted I=Due J=NAICS K=SetAside L=URL M=Notes N=Score O=Reasoning
    """
    import requests, json
    secrets_path = Path(__file__).parent.parent / "configs" / "velocity" / "slack_tokens.json"
    bot_token = json.loads(secrets_path.read_text()).get("SLACK_BOT_TOKEN", "") if secrets_path.exists() else ""
    if not bot_token:
        print("  No Slack bot token — skipping Slack post")
        return
    use_webhook = False

    portal    = opp_row[2]  if len(opp_row) > 2  else "?"
    title     = opp_row[3]  if len(opp_row) > 3  else "?"
    desc      = opp_row[4]  if len(opp_row) > 4  else ""
    eng_type  = opp_row[5]  if len(opp_row) > 5  else ""
    agency    = opp_row[6]  if len(opp_row) > 6  else ""
    due       = opp_row[8]  if len(opp_row) > 8  else ""
    url       = opp_row[11] if len(opp_row) > 11 else ""
    score     = opp_row[13] if len(opp_row) > 13 else ""
    reasoning = opp_row[14] if len(opp_row) > 14 else ""

    lines = [f"🏔️ *{portal} — {title}*"]
    if agency:
        lines.append(f"Agency: {agency}")
    if eng_type:
        lines.append(f"Engagement type: {eng_type}")
    lines.append(f"Due date: {due or 'TBD'}")
    if url:
        lines.append(f"<{url}>")
    if desc:
        lines.append(f"\n_{desc[:300]}_")
    if score or reasoning:
        yukon_line = f"Yukon score: {score}/10" if score else ""
        if reasoning:
            yukon_line += f" — {reasoning[:120]}"
        lines.append(f"\n{yukon_line}")
    text = "\n".join(lines)
    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {bot_token}", "Content-Type": "application/json"},
        json={"channel": BD_CHANNEL_ID, "text": text, "unfurl_links": False, "unfurl_media": False},
        timeout=15
    )
    result = resp.json()
    if not result.get("ok"):
        print(f"  Slack bot post failed: {result.get('error')}")


def read_range(tab: str, range_str: str) -> list:
    result = subprocess.run(
        ["gog", "sheets", "read", SHEET_ID, f"{tab}!{range_str}",
         "-a", ACCOUNT, "--json"],
        capture_output=True, text=True, timeout=20
    )
    if result.returncode != 0:
        print(f"ERROR reading {tab}!{range_str}: {result.stderr[:100]}")
        return []
    data = json.loads(result.stdout)
    return data.get("values", [])


def write_row(tab: str, row_num: int, cells: list) -> bool:
    """Write a row to a specific tab and row number."""
    clean_cells = [str(c).replace("|", " ").replace(",", ";").strip() for c in cells]
    row_str = "|".join(clean_cells)
    result = subprocess.run(
        ["gog", "sheets", "update", SHEET_ID, f"{tab}!A{row_num}:O{row_num}",
         row_str, "-a", ACCOUNT, "--json"],
        capture_output=True, text=True, timeout=20
    )
    return result.returncode == 0


def get_next_data_row(tab: str) -> int:
    """Find next empty data row — always row 2 or later, never overwrites header."""
    rows = read_range(tab, "A2:A600")
    for i, row in enumerate(rows):
        if not row or not str(row[0]).strip():
            return i + 2  # +1 for 0-index, +1 for header row
    return len(rows) + 2


def append_row(tab: str, cells: list) -> bool:
    """Append a row at next available slot — never touches header row 1."""
    next_row = get_next_data_row(tab)
    clean_cells = [str(c).replace("|", " ").replace(",", ";").strip() for c in cells]
    row_str = "|".join(clean_cells)
    result = subprocess.run(
        ["gog", "sheets", "update", SHEET_ID, f"{tab}!A{next_row}:O{next_row}",
         row_str, "-a", ACCOUNT, "--json"],
        capture_output=True, text=True, timeout=20
    )
    return result.returncode == 0


def clear_row(row_num: int) -> bool:
    """Clear a row from the Inbox tab."""
    result = subprocess.run(
        ["gog", "sheets", "clear", SHEET_ID, f"{INBOX_TAB}!A{row_num}:O{row_num}",
         "-a", ACCOUNT, "--json"],
        capture_output=True, text=True, timeout=20
    )
    return result.returncode == 0


def get_next_empty_row(tab: str) -> int:
    """Find the next empty row in a tab (after header)."""
    rows = read_range(tab, f"A1:A{MAX_ROWS}")
    # Find first empty row after header
    for i, row in enumerate(rows):
        if i == 0:
            continue  # skip header
        if not row or not str(row[0]).strip():
            return i + 1
    return len(rows) + 1


def process_inbox(dry_run: bool = False):
    print(f"{'[DRY RUN] ' if dry_run else ''}Reading Inbox...")

    # Read all inbox rows
    rows = read_range(INBOX_TAB, f"A1:O{MAX_ROWS}")
    if not rows:
        print("Inbox is empty.")
        return

    header = rows[0]
    data_rows = rows[1:]

    # Find column indices
    try:
        relevant_col = header.index("Relevant")
    except ValueError:
        # Try col B (index 1) as fallback
        relevant_col = 1

    print(f"Total rows in Inbox: {len(data_rows)}")
    print(f"Relevant column: {relevant_col} ({header[relevant_col] if relevant_col < len(header) else 'B'})")

    to_valid = []
    to_not_valid = []
    unreviewed = []

    for i, row in enumerate(data_rows):
        row_num = i + 2  # +1 for 0-index, +1 for header

        # Pad row to at least relevant_col + 1 length
        while len(row) <= relevant_col:
            row.append("")

        verdict = str(row[relevant_col]).strip().lower()

        if verdict in ("yes", "maybe"):
            to_valid.append((row_num, row))
        elif verdict == "no":
            to_not_valid.append((row_num, row))
        else:
            unreviewed.append((row_num, row))

    print(f"\nResults:")
    print(f"  → ✅ Valid:     {len(to_valid)} rows")
    print(f"  → ❌ Not Valid: {len(to_not_valid)} rows")
    print(f"  → Unreviewed:   {len(unreviewed)} rows (will stay in Inbox)")

    if dry_run:
        print("\n[DRY RUN] Preview of moves:")
        print("\nValid:")
        for _, row in to_valid[:5]:
            title = row[2] if len(row) > 2 else row[0] if row else "?"
            print(f"  ✅ {str(title)[:70]}")
        print("\nNot Valid:")
        for _, row in to_not_valid[:5]:
            title = row[2] if len(row) > 2 else row[0] if row else "?"
            print(f"  ❌ {str(title)[:70]}")
        return

    def remap_row(row):
        """Remap Inbox column order to Valid/NotValid column order.
        Inbox:    A=Date B=Relevant C=Portal D=Title E=Desc F=Type G=Agency H=Posted I=Due J=NAICS K=SetAside L=URL M=Notes N=Score O=Reasoning
        Valid/NV: A=Date B=Relevant C=Title  D=Portal          E=Type F=Agency G=Posted H=Due  I=NAICS J=SetAside K=URL  L=Notes M=Score N=Reasoning
        """
        def g(r, i): return r[i] if len(r) > i else ""
        return [g(row,0), g(row,1), g(row,3), g(row,2), g(row,5),
                g(row,6), g(row,7), g(row,8), g(row,9), g(row,10),
                g(row,11), g(row,12), g(row,13), g(row,14)]

        # Write Valid rows + download all attachments + post to Slack
    if to_valid:
        print(f"\nWriting {len(to_valid)} rows to ✅ Valid...")
        for idx, (_, row) in enumerate(to_valid):
            if append_row(VALID_TAB, remap_row(row)):
                url = row[11] if len(row) > 11 else ""
                if url and "sam.gov" in url.lower():
                    notice_id = _extract_sam_notice_id(url)
                    if notice_id:
                        print(f"  📎 Downloading all attachments for {notice_id}...")
                        atts = download_all_sam_attachments(url)
                        print(f"  📎 {len(atts)} attachment(s) cached")
                post_to_slack(row)
                time.sleep(0.5)
            else:
                print(f"  FAILED: {row[3][:40] if len(row) > 3 else '?'}")
            if (idx + 1) % 10 == 0:
                print(f"  {idx+1}/{len(to_valid)} written")
            time.sleep(0.2)

    # Write Not Valid rows
    if to_not_valid:
        print(f"Writing {len(to_not_valid)} rows to ❌ Not Valid...")
        for idx, (_, row) in enumerate(to_not_valid):
            if append_row(NOT_VALID_TAB, remap_row(row)):
                pass
            else:
                print(f"  FAILED: {row[3][:40] if len(row) > 3 else '?'}")
            if (idx + 1) % 25 == 0:
                print(f"  {idx+1}/{len(to_not_valid)} written")
            time.sleep(0.2)

    # Clear moved rows from Inbox (clear in reverse order to preserve row numbers)
    rows_to_clear = sorted([r for r, _ in to_valid] + [r for r, _ in to_not_valid], reverse=True)
    if rows_to_clear:
        print(f"Clearing {len(rows_to_clear)} processed rows from Inbox...")
        for row_num in rows_to_clear:
            clear_row(row_num)
            time.sleep(0.1)

    print(f"\n✅ Done!")
    print(f"  Moved to Valid: {len(to_valid)}")
    print(f"  Moved to Not Valid: {len(to_not_valid)}")
    print(f"  Remaining in Inbox: {len(unreviewed)}")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    process_inbox(dry_run=dry_run)
