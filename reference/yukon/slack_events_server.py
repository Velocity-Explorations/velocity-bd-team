"""
Yukon — Slack Events Webhook Server
Listens for reaction_added and message events from #bd-prospector
and creates BD Activities cards when triggered.

Runs on port 3002 (Mission Control uses 3001).

Trigger conditions:
  - Reaction 👍 (thumbsup) on a Yukon opp message
  - Reply containing "add to board", "add this", "add it" to a Yukon opp message

When triggered:
  - Creates a new item in BD Activities Slack List (F0931PFSNEL) with status Backlog
  - Replies in thread confirming the card was created
"""

import hashlib
import hmac
import json
import logging
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
import subprocess
from flask import Flask, request, jsonify

app = Flask(__name__)
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Config
BD_CHANNEL_ID = "C0AN8AMM4AW"   # #bd-prospector
BD_LIST_ID = "F0931PFSNEL"       # BD Activities Slack List
YUKON_LIST_ID = "F0ANYCR7M9A"   # Yukon BD Opportunities (standalone list)

# Yukon list column IDs (confirmed from test ticket)
YUKON_COLS = {
    "name":        "Col0ANUQXPWD8",   # Opportunity title (primary) — rich_text
    "portal":      "Col0ANRCLST8D",   # Portal name — rich_text
    "agency":      "Col0AP7N676AD",   # Agency — rich_text
    "type":        "Col0APP3F1YFJ",   # Opp type — rich_text
    "url":         "Col0ANSNUGSR4",   # Links/URL — rich_text with link element (no text prop)
    "naics":       "Col0ANNDLKTC3",   # NAICS code — rich_text
    "score":       "Col0ANDBNS78X",   # Yukon Score — number array
    "reasoning":   "Col0ANYCRHLHJ",   # Yukon Reasoning — rich_text
    "drive":       "Col0ANUQY1Z5G",   # Google Drive link — link: [{original_url: ...}]
    "description": "Col0ANX4WEF5K",   # Description — rich_text
    "assignee":    "Col0ANU5SL18B",   # Assigned To — user: "U..."
    "status":      "Col0ANX464W77",   # Status — select: ["OptID"]
}

# Yukon list status option IDs (discovered by cycling test ticket)
YUKON_STATUS = {
    "backlog":     "Opt7O8AZS3A",
    "in_progress": "OptWGRN9UNS",
    "review":      "Opt9TAX8UO8",
    "blocked":     "OptOV2BMJE6",
    "completed":   "OptFEU06KPP",
    "graveyard":   "OptMCIF648P",
    "forecasts":   "Opt5BCCEUZ6",
}
BD_DRIVE_FOLDER_ID = "1LbHUGFrwhiwOfW6FlV1wF-n4rnslPiJm"  # BD Shared Drive folder
DRIVE_ACCOUNT = "david@velocityexplorations.com"
SECRETS_DIR = Path(__file__).parent.parent / "configs" / "velocity"

# Trigger phrases for "add to board"
ADD_TRIGGERS = [
    "add to board", "add this to board", "add it to board",
    "add to bd activities", "board this opp", "add to backlog",
    "add to tracker"
]

# Trigger emoji
ADD_EMOJI = "+1"
DELETE_EMOJIS = {"x", "axe"}  # ❌ or 🪓 reaction deletes the bot message
THUMBSDOWN_EMOJI = "-1"         # 👎 reaction marks opp as not relevant
SUBMIT_EMOJI = "white_check_mark"  # ✅ reaction marks opp as submitted

# Cache of processed event IDs (prevent duplicates)
_processed = set()

# Cache of message timestamps that have already triggered BD card creation
# In-memory (fast) + SQLite (persistent across restarts)
_bd_card_created = set()

# Threads where Yukon has posted — replies in these threads trigger auto-response
_yukon_threads = set()
BD_CARDS_DB = Path(__file__).parent.parent / "data" / "bd-cards-created.db"


def _init_cards_db():
    """Initialize persistent BD card dedup store."""
    BD_CARDS_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(BD_CARDS_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bd_cards (
                channel TEXT NOT NULL,
                msg_ts  TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (channel, msg_ts)
            )
        """)

def _is_card_created(channel: str, msg_ts: str) -> bool:
    """Check if a BD card was already created for this message (memory + DB)."""
    key = f"{channel}:{msg_ts}"
    if key in _bd_card_created:
        return True
    try:
        with sqlite3.connect(BD_CARDS_DB) as conn:
            row = conn.execute(
                "SELECT 1 FROM bd_cards WHERE channel=? AND msg_ts=?",
                (channel, msg_ts)
            ).fetchone()
            if row:
                _bd_card_created.add(key)  # warm the memory cache
                return True
    except Exception:
        pass
    return False

def _mark_card_created(channel: str, msg_ts: str):
    """Mark a BD card as created (memory + DB)."""
    from datetime import datetime, timezone
    key = f"{channel}:{msg_ts}"
    _bd_card_created.add(key)
    try:
        with sqlite3.connect(BD_CARDS_DB) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO bd_cards (channel, msg_ts, created_at) VALUES (?, ?, ?)",
                (channel, msg_ts, datetime.now(timezone.utc).isoformat())
            )
    except Exception as e:
        log.warning(f"Could not persist card dedup: {e}")


_init_cards_db()


def load_tokens():
    token_file = SECRETS_DIR / "slack_tokens.json"
    if token_file.exists():
        data = json.loads(token_file.read_text())
        # Use Yukon bot token for event delivery + replies
        # Use user token for BD Activities list operations
        bot_token = data.get("SLACK_YUKON_BOT_TOKEN", data.get("SLACK_BOT_TOKEN", ""))
        user_token = data.get("SLACK_USER_TOKEN", "")
        return user_token, bot_token
    return "", ""


def get_message(channel: str, ts: str) -> dict:
    """Fetch a specific message from Slack."""
    _, bot_token = load_tokens()
    resp = requests.get(
        "https://slack.com/api/conversations.history",
        headers={"Authorization": f"Bearer {bot_token}"},
        params={"channel": channel, "latest": ts, "limit": 1, "inclusive": True},
        timeout=10
    )
    msgs = resp.json().get("messages", [])
    return msgs[0] if msgs else {}


def get_message_with_continuation(channel: str, ts: str) -> dict:
    """Fetch a message and its continuation if Slack split a long post."""
    _, bot_token = load_tokens()
    resp = requests.get(
        "https://slack.com/api/conversations.history",
        headers={"Authorization": f"Bearer {bot_token}"},
        params={"channel": channel, "oldest": ts, "limit": 3, "inclusive": True},
        timeout=10
    )
    msgs = resp.json().get("messages", [])
    if not msgs:
        return {}
    primary = msgs[0]
    primary_user = primary.get("user", "")
    primary_ts = float(primary.get("ts", "0"))
    for m in msgs[1:]:
        if m.get("user") == primary_user and abs(float(m.get("ts", "0")) - primary_ts) < 2.0:
            primary["text"] = primary.get("text", "") + "\n" + m.get("text", "")
        else:
            break
    return primary


def extract_opp_from_message(text: str) -> dict:
    """Parse a Yukon opp message to extract title, portal, URL, due date.
    Supports both old format (New BD Opportunity) and new format (Portal — Title header).
    """
    opp = {"title": "", "portal": "", "url": "", "due": "", "agency": "", "description": "", "type": ""}

    lines = text.split("\n")
    for line in lines:
        line = line.strip()

        # New format header: "🏔️ *Portal — Title*"
        if ("🏔️" in line or ":snow_capped_mountain:" in line or ":snowcappedmountain:" in line) and "—" in line:
            # Strip markdown bold and all emoji variants
            clean = re.sub(r"[*_]", "", line)
            clean = re.sub(r":snow_capped_mountain:|:snowcappedmountain:|🏔️", "", clean).strip()
            if "—" in clean:
                parts = clean.split("—", 1)
                # Strip any leading/trailing punctuation or spaces from portal
                portal = parts[0].strip().strip(":").strip()
                opp["portal"] = portal
                opp["title"] = parts[1].strip()
            continue

        # Old format: "New BD Opportunity — Portal"
        if "New BD Opportunity" in line:
            m = re.search(r"—\s*(.+?)\*?$", line)
            if m:
                opp["portal"] = m.group(1).strip().strip("*")
            continue

        # Old format title: standalone "*Title*"
        if line.startswith("*") and line.endswith("*") and len(line) > 2 and not opp["title"]:
            title = line.strip("*").strip()
            if title and "New BD" not in title and "—" not in title:
                opp["title"] = title
            continue

        if line.startswith("Agency:"):
            opp["agency"] = line.replace("Agency:", "").strip()
        elif line.startswith("Engagement type:"):
            opp["type"] = line.replace("Engagement type:", "").strip()
        elif line.startswith("Type:"):
            raw_type = re.sub(r"\|.*", "", line.replace("Type:", "")).strip()
            opp["type"] = raw_type[:80] if len(raw_type) > 80 else raw_type
            if len(raw_type) > 200 and not opp["description"]:
                opp["description"] = raw_type
        elif line.startswith("Due date:"):
            opp["due"] = line.replace("Due date:", "").strip()
        elif line.startswith("Due:"):
            opp["due"] = line.replace("Due:", "").strip()
        elif line.startswith("_") and line.endswith("_"):
            # Italicized description
            opp["description"] = line.strip("_").strip()
        elif line.startswith(">") or line.startswith("&gt;"):
            desc = re.sub(r"^[>&gt;]+\s*", "", line).strip()
            if desc and "🔗" not in desc:
                opp["description"] = desc
        elif line.startswith("<http") and line.endswith(">"):
            # Bare URL in angle brackets: <https://...>
            opp["url"] = line.strip("<>").strip()
        elif "🔗" in line or ":link:" in line:
            m = re.search(r"https?://\S+", line)
            if m:
                opp["url"] = m.group(0).strip(">")

    return opp


def create_bd_card(opp: dict, triggered_by: str, msg_ts: str = "", channel: str = "") -> bool:
    """Create a new item in BD Activities Slack List."""
    user_token, _ = load_tokens()
    if not user_token:
        log.error("No user token for BD Activities")
        return False

    title = opp.get("title", "Untitled Opportunity")
    portal = opp.get("portal", "Unknown")
    url = opp.get("url", "")
    agency = opp.get("agency", "")
    description = opp.get("description", "")
    opp_type = opp.get("type", "")
    name_text = title

    def rt(text):
        return [{"type": "rich_text", "elements": [{"type": "rich_text_section", "elements": [{"type": "text", "text": text}]}]}]

    def rt_link(url, label="View Opportunity"):
        return [{"type": "rich_text", "elements": [{"type": "rich_text_section", "elements": [{"type": "link", "url": url, "text": label}]}]}]

    # Step 1: Create item with status = Backlog
    fields = [
        {"key": "Col092DQ3KWGL", "value": "Opt5N4GHVFJ"},   # Status = Backlog
    ]

    resp = requests.post(
        "https://slack.com/api/slackLists.items.create",
        headers={"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"},
        json={"list_id": BD_LIST_ID, "fields": fields},
        timeout=15
    )
    result = resp.json()
    if not result.get("ok"):
        log.error(f"Failed to create BD card: {result.get('error')} — {result}")
        return False

    item_id = result.get("item", {}).get("id")
    log.info(f"BD card created (blank): {item_id}")

    # Step 2: Set all fields via update cells
    cells = [
        # Name (title)
        {"column_id": "Col0931PFV7FS", "rich_text": rt(name_text), "row_id": item_id},
        # Assignee
        {"column_id": "Col01", "user": "U08V7ULPH1N", "row_id": item_id},
    ]

    # Description field (Col098FD2LJAD)
    if description:
        cells.append({"column_id": "Col098FD2LJAD", "rich_text": rt(description), "row_id": item_id})

    # Links field (Col092MQZRLEP) — URL as clickable link
    if url:
        cells.append({"column_id": "Col092MQZRLEP", "rich_text": [{"type": "rich_text", "elements": [{"type": "rich_text_section", "elements": [{"type": "link", "url": url}]}]}], "row_id": item_id})

    # Type (e.g. "SBIR/STTR", "Solicitation")
    if opp_type:
        cells.append({"column_id": "Col0ANAPU7K99", "rich_text": rt(opp_type), "row_id": item_id})

    # Portal Name
    if portal:
        cells.append({"column_id": "Col0ANLNQ7GDS", "rich_text": rt(portal), "row_id": item_id})

    # Agency
    if agency:
        cells.append({"column_id": "Col0ANW2UP073", "rich_text": rt(agency), "row_id": item_id})

    # Due Date — parse multiple formats, set to actual close date (no offset)
    if opp.get("due"):
        due_str = None
        due_raw = opp["due"].strip()
        # Try ISO format: 2026-04-13
        try:
            due_dt = datetime.strptime(due_raw[:10], "%Y-%m-%d")
            due_str = due_dt.strftime("%Y-%m-%d")
        except Exception:
            pass
        # Try "M/D/YYYY" or "MM/DD/YYYY" format
        if not due_str:
            try:
                m = re.search(r"(\d{1,2})/(\d{1,2})/(20\d{2})", due_raw)
                if m:
                    due_dt = datetime(int(m.group(3)), int(m.group(1)), int(m.group(2)))
                    due_str = due_dt.strftime("%Y-%m-%d")
            except Exception:
                pass
        # Try "13 APR 2026" format
        if not due_str:
            try:
                m = re.search(r"(\d{1,2})\s+([A-Z]{3})\s+(20\d{2})", due_raw)
                if m:
                    due_dt = datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %b %Y")
                    due_str = due_dt.strftime("%Y-%m-%d")
            except Exception:
                pass
        # Try "DEC 25 2026" or "25 DEC 2026 : 23:59 MST"
        if due_str:
            cells.append({"column_id": "Col02", "date": [due_str], "row_id": item_id})
            log.info(f"Due date set: {due_str} (from '{due_raw[:30]}')")
        else:
            log.warning(f"Could not parse due date: '{due_raw[:40]}'")

    resp2 = requests.post(
        "https://slack.com/api/slackLists.items.update",
        headers={"Authorization": f"Bearer {user_token}", "Content-Type": "application/json; charset=utf-8"},
        json={"list_id": BD_LIST_ID, "cells": cells},
        timeout=15
    )
    result2 = resp2.json()
    if result2.get("ok"):
        log.info(f"BD card named: {name_text[:60]}")
    else:
        log.warning(f"BD card created but cell update failed: {result2.get('error')}")

    # Create Google Drive folder for this opp
    try:
        folder_name = name_text[:100]  # truncate for Drive
        result = subprocess.run(
            ["/opt/homebrew/bin/gog", "drive", "mkdir", folder_name,
             "--parent", BD_DRIVE_FOLDER_ID,
             "-a", DRIVE_ACCOUNT, "--client", "velocity", "-j"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            import json as _json
            folder_data = _json.loads(result.stdout)
            folder_url = folder_data.get("folder", {}).get("webViewLink", "")
            log.info(f"Drive folder created: {folder_url}")
            # Write Drive folder link back to the Slack card
            if folder_url and item_id:
                r3 = requests.post(
                    "https://slack.com/api/slackLists.items.update",
                    headers={"Authorization": f"Bearer {user_token}", "Content-Type": "application/json; charset=utf-8"},
                    json={"list_id": BD_LIST_ID, "cells": [
                        {"column_id": "Col0AARNSF9LP", "rich_text": [{"type": "rich_text", "elements": [{"type": "rich_text_section", "elements": [{"type": "link", "url": folder_url}]}]}], "row_id": item_id}
                    ]},
                    timeout=15
                ).json()
                if r3.get("ok"):
                    log.info(f"Drive link written to card")
                else:
                    log.warning(f"Drive link write failed: {r3.get('error')}")

            # Launch RFP Response Agent asynchronously
            folder_id = folder_data.get("folder", {}).get("id", "")
            if folder_id:
                try:
                    agent_script = str(Path(__file__).parent / "rfp_response_agent.py")
                    venv_python = str(Path(__file__).resolve().parent.parent / ".venv" / "bin" / "python")
                    agent_env = os.environ.copy()
                    agent_env.setdefault("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
                    subprocess.Popen(
                        [venv_python, agent_script,
                         "--opp-json", json.dumps(opp),
                         "--drive-folder-id", folder_id,
                         "--slack-channel", channel or BD_CHANNEL_ID,
                         "--slack-thread", msg_ts],
                        start_new_session=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        env=agent_env,
                    )
                    log.info(f"RFP Response Agent launched for: {opp.get('title', '?')[:60]}")
                except Exception as e:
                    log.warning(f"RFP Response Agent launch failed: {e}")
        else:
            log.warning(f"Drive folder creation failed: {result.stderr[:100]}")
    except Exception as e:
        log.warning(f"Drive folder creation error: {e}")

    return True


def create_forecast_card(opp: dict, triggered_by: str) -> bool:
    """Create a new item in Yukon BD Opportunities Slack List with Forecasts status."""
    user_token, _ = load_tokens()
    if not user_token:
        log.error("No user token for Yukon list")
        return False

    title = opp.get("title", "Untitled Forecast")
    portal = opp.get("portal", "NASA Forecast")
    url = opp.get("url", "")
    agency = opp.get("agency", "")
    description = opp.get("description", "")
    opp_type = opp.get("type", "Forecast")
    name_text = title

    def rt(text):
        return [{"type": "rich_text", "elements": [{"type": "rich_text_section", "elements": [{"type": "text", "text": str(text)}]}]}]

    # Step 1: Create item with status = Forecasts
    fields = [
        {"key": "Col092DQ3KWGL", "value": YUKON_STATUS["forecasts"]},
    ]
    resp = requests.post(
        "https://slack.com/api/slackLists.items.create",
        headers={"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"},
        json={"list_id": YUKON_LIST_ID, "fields": fields},
        timeout=15
    )
    result = resp.json()
    if not result.get("ok"):
        log.error(f"Failed to create forecast card: {result.get('error')} — {result}")
        return False

    item_id = result.get("item", {}).get("id")
    log.info(f"Forecast card created (blank): {item_id}")

    # Step 2: Populate fields
    cells = [
        {"column_id": "Col0931PFV7FS", "rich_text": rt(name_text), "row_id": item_id},
        {"column_id": "Col01", "user": "U08V7ULPH1N", "row_id": item_id},
    ]
    if description:
        cells.append({"column_id": "Col098FD2LJAD", "rich_text": rt(description), "row_id": item_id})
    if url:
        cells.append({
            "column_id": "Col092MQZRLEP",
            "rich_text": [{"type": "rich_text", "elements": [{"type": "rich_text_section", "elements": [{"type": "link", "url": url}]}]}],
            "row_id": item_id
        })
    if opp_type:
        cells.append({"column_id": "Col0ANAPU7K99", "rich_text": rt(opp_type), "row_id": item_id})
    if portal:
        cells.append({"column_id": "Col0ANLNQ7GDS", "rich_text": rt(portal), "row_id": item_id})
    if agency:
        cells.append({"column_id": "Col0ANW2UP073", "rich_text": rt(agency), "row_id": item_id})

    resp2 = requests.post(
        "https://slack.com/api/slackLists.items.update",
        headers={"Authorization": f"Bearer {user_token}", "Content-Type": "application/json; charset=utf-8"},
        json={"list_id": YUKON_LIST_ID, "cells": cells},
        timeout=15
    )
    result2 = resp2.json()
    if result2.get("ok"):
        log.info(f"Forecast card populated: {name_text[:60]}")
        return True
    else:
        log.warning(f"Forecast card created but cell update failed: {result2.get('error')}")
        return True  # card exists, cells failed — still partial success


def post_reply(channel: str, thread_ts: str, text: str):
    """Post a reply in a Slack thread."""
    _, bot_token = load_tokens()
    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {bot_token}", "Content-Type": "application/json"},
        json={"channel": channel, "thread_ts": thread_ts, "text": text},
        timeout=10
    )
    if resp.json().get("ok"):
        # Track this thread so follow-up replies trigger auto-response
        _yukon_threads.add(f"{channel}:{thread_ts}")
    else:
        log.error(f"Reply failed: {resp.json().get('error')}")


def handle_mention(event: dict, payload: dict):
    """Handle @Yukon mentions in Slack — answer questions using RAG context."""
    import threading
    thread = threading.Thread(target=_handle_mention_async, args=(event, payload))
    thread.daemon = True
    thread.start()


def _handle_mention_async(event: dict, payload: dict):
    """Run in background thread so we return 200 to Slack quickly."""
    channel = event.get("channel", BD_CHANNEL_ID)
    thread_ts = event.get("thread_ts") or event.get("ts", "")
    user = event.get("user", "")

    # Strip the @Yukon mention from text
    text = event.get("text", "")
    text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()

    if not text:
        post_reply(channel, thread_ts, "Hey! Ask me anything about Velocity BD history, past submissions, or current opportunities. I'll do my best to help.")
        return

    log.info(f"@Yukon mention from {user}: {text[:80]}")


    # Post immediate "thinking" placeholder
    _, bot_token = load_tokens()
    _ph_resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {bot_token}", "Content-Type": "application/json"},
        json={"channel": channel, "thread_ts": thread_ts, "text": "⏳ _Searching BD history..._"},
        timeout=10
    ).json()
    _placeholder_ts = _ph_resp.get("ts") if _ph_resp.get("ok") else None

    # Build RAG context
    rag_context = _get_mention_context(text)

    # Build prompt — instruct the agent to answer as Yukon only, no meta-commentary
    prompt = f"""You are answering a question on behalf of Yukon, Velocity Explorations\'s automated BD intelligence tool.
Answer ONLY the question below using the context provided. Do not reference OpenClaw, Reptar, or yourself.
Do not say you don\'t have access to documents — the context below IS your knowledge.
Keep your answer concise and useful for a Slack channel. Use bullet points where appropriate.

{rag_context if rag_context else "No specific past BD data found for this query."}

Question: {text}

Answer (as Yukon, in plain text for Slack):"""


    try:
        result = subprocess.run(
            ["/opt/homebrew/bin/openclaw", "agent", "--message", prompt, "--agent", "main", "--json"],
            capture_output=True, text=True, timeout=90
        )
        if result.returncode != 0:
            raise RuntimeError(f"openclaw agent failed: {result.stderr[:200]}")
        resp_data = json.loads(result.stdout)
        payloads = resp_data.get("result", {}).get("payloads", [])
        response = payloads[0].get("text", "").strip() if payloads else ""
        if not response:
            raise RuntimeError("Empty response")

        # Handle feedback mentions — log to feedback.jsonl
        text_lower = text.lower()
        if any(w in text_lower for w in ["not relevant", "irrelevant", "skip this", "no go", "pass on"]):
            _log_feedback(text, "no", user)
        elif any(w in text_lower for w in ["good opp", "yes on this", "interested"]) or re.search(r"\brelevant\b", text_lower) or re.search(r"\bpursue\b", text_lower):
            _log_feedback(text, "yes", user)

        # Update placeholder with real answer
        if _placeholder_ts:
            requests.post(
                "https://slack.com/api/chat.update",
                headers={"Authorization": f"Bearer {bot_token}", "Content-Type": "application/json"},
                json={"channel": channel, "ts": _placeholder_ts, "text": response},
                timeout=10
            )
        else:
            post_reply(channel, thread_ts, response)

    except Exception as e:
        log.error(f"Mention handler error: {e}")
        err_text = f"Sorry, ran into an error: {str(e)[:100]}"
        if _placeholder_ts:
            requests.post(
                "https://slack.com/api/chat.update",
                headers={"Authorization": f"Bearer {bot_token}", "Content-Type": "application/json"},
                json={"channel": channel, "ts": _placeholder_ts, "text": err_text},
                timeout=10
            )
        else:
            post_reply(channel, thread_ts, err_text)


def _get_mention_context(query: str) -> str:
    """Get RAG context from ChromaDB for a user question."""
    try:
        import chromadb

        resp = requests.post("http://localhost:11434/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": query[:500]}, timeout=15)
        if resp.status_code != 200:
            return ""
        emb = resp.json().get("embedding", [])
        if not emb:
            return ""

        client = chromadb.PersistentClient(path=str(Path(__file__).parent.parent / "data" / "chroma"))
        parts = []

        # Search BD Activities
        try:
            acts = client.get_collection("bd_activities")
            r1 = acts.query(query_embeddings=[emb], n_results=5)
            if r1["documents"][0]:
                parts.append("## Relevant past BD activities:")
                for doc, meta in zip(r1["documents"][0], r1["metadatas"][0]):
                    parts.append(f"- [{meta.get('status', '')}] {meta.get('title', '')[:80]}")
        except Exception:
            pass

        # Search BD Documents
        try:
            docs = client.get_collection("bd_documents")
            r2 = docs.query(query_embeddings=[emb], n_results=4)
            if r2["documents"][0]:
                parts.append("\n## Relevant past documents:")
                seen = set()
                for doc, meta in zip(r2["documents"][0], r2["metadatas"][0]):
                    fname = meta.get("filename", "")
                    if fname not in seen:
                        seen.add(fname)
                        snippet = doc[:300].replace("\n", " ").strip()
                        parts.append(f"- [{meta.get('doc_type', '')}] {fname}: \"{snippet}...\"")
        except Exception:
            pass

        return "\n".join(parts) if parts else ""
    except Exception:
        return ""


def _log_feedback_opp(opp: dict, verdict: str, user: str):
    """Log structured opp feedback from Slack reactions to feedback.jsonl."""
    import json as _json
    from datetime import datetime, timezone
    from pathlib import Path as _Path
    feedback_path = _Path(__file__).parent.parent / "data" / "feedback.jsonl"
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "user": user,
        "verdict": verdict,
        "source": "slack_reaction",
        "title": opp.get("title", ""),
        "portal": opp.get("portal", ""),
        "agency": opp.get("agency", ""),
        "type": opp.get("type", ""),
        "url": opp.get("url", ""),
        "description": opp.get("description", "")[:200],
    }
    with open(feedback_path, "a") as f:
        f.write(_json.dumps(entry) + "\n")
    log.info(f"Feedback logged: verdict={verdict} title={opp.get('title','')[:50]}")


def _log_feedback(text: str, verdict: str, user: str):
    """Log user feedback on opportunities to feedback.jsonl."""
    from datetime import datetime as _dt, timezone as _tz
    feedback_path = Path(__file__).parent.parent / "data" / "feedback.jsonl"
    entry = {
        "ts": _dt.now(_tz.utc).isoformat(),
        "user": user,
        "text": text[:200],
        "verdict": verdict,
        "source": "slack_mention"
    }
    with open(feedback_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    log.info(f"Feedback logged: verdict={verdict}")


def _update_bd_card_status(title: str, status: str):
    """Search BD Activities list for a card matching the title and update its status."""
    user_token, _ = load_tokens()
    if not user_token:
        return
    status_opt = {
        "backlog": "Opt5N4GHVFJ",
        "in_progress": "OptFT5KPAU",
        "completed": "OptFEU06KPP",
    }.get(status)
    if not status_opt:
        return

    resp = requests.post(
        "https://slack.com/api/slackLists.items.list",
        headers={"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"},
        json={"list_id": BD_LIST_ID, "limit": 200},
        timeout=15,
    )
    items = resp.json().get("items", [])
    for item in items:
        cells = item.get("fields", {})
        name_cell = cells.get("Col0931PFV7FS", {})
        name_text = ""
        for block in name_cell.get("rich_text", []):
            for el in block.get("elements", []):
                for seg in el.get("elements", []):
                    name_text += seg.get("text", "")
        if title.lower().strip() in name_text.lower().strip() or name_text.lower().strip() in title.lower().strip():
            item_id = item.get("id")
            requests.post(
                "https://slack.com/api/slackLists.items.update",
                headers={"Authorization": f"Bearer {user_token}", "Content-Type": "application/json"},
                json={"list_id": BD_LIST_ID, "cells": [
                    {"column_id": "Col092DQ3KWGL", "select": [status_opt], "row_id": item_id},
                ]},
                timeout=15,
            )
            log.info(f"BD card '{name_text[:50]}' status → {status}")
            return
    log.warning(f"No BD card found matching title: {title[:60]}")


@app.route("/yukon/slack-events", methods=["POST"])
def slack_events():
    data = request.json or {}

    # Slack URL verification challenge
    if data.get("type") == "url_verification":
        return jsonify({"challenge": data["challenge"]})

    # Ignore retries
    if request.headers.get("X-Slack-Retry-Num"):
        return jsonify({"ok": True})

    event = data.get("event", {})
    event_type = event.get("type")
    event_id = data.get("event_id", "")

    # Dedup
    if event_id in _processed:
        return jsonify({"ok": True})
    _processed.add(event_id)
    if len(_processed) > 500:
        _processed.clear()

    # Debug log every event
    log.info(f"Event received: type={event_type} channel={event.get('channel')} reaction={event.get('reaction')} user={event.get('user')}")
    log.info(f"Event item: {event.get('item', {})}")

    # Handle @Yukon mentions from any channel
    if event_type == "app_mention":
        handle_mention(event, data)
        return jsonify({"ok": True})

    # Only handle other events from #bd-prospector
    channel = event.get("channel") or event.get("item", {}).get("channel", "")
    log.info(f"Resolved channel: {channel} (expected: {BD_CHANNEL_ID})")
    if channel != BD_CHANNEL_ID:
        log.info(f"Skipping — wrong channel")
        return jsonify({"ok": True})

    # ── REACTION ADDED ──────────────────────────────────────────────

    # ❌/🪓 reaction = delete bot message + entire thread
    if event_type == "reaction_added" and event.get("reaction") in DELETE_EMOJIS:
        item = event.get("item", {})
        msg_ts = item.get("ts", "")
        msg_channel = item.get("channel", channel)
        if msg_ts:
            _, bot_token = load_tokens()

            # Fetch all thread replies first
            thread_resp = requests.get(
                "https://slack.com/api/conversations.replies",
                headers={"Authorization": f"Bearer {bot_token}"},
                params={"channel": msg_channel, "ts": msg_ts, "limit": 100},
                timeout=10
            ).json()
            thread_msgs = thread_resp.get("messages", [])

            # Delete all replies (skip the parent — delete last)
            deleted = 0
            for tmsg in thread_msgs:
                if tmsg.get("ts") == msg_ts:
                    continue  # skip parent for now
                del_r = requests.post(
                    "https://slack.com/api/chat.delete",
                    headers={"Authorization": f"Bearer {bot_token}", "Content-Type": "application/json"},
                    json={"channel": msg_channel, "ts": tmsg["ts"]},
                    timeout=10
                ).json()
                if del_r.get("ok"):
                    deleted += 1

            # Delete the parent message
            del_resp = requests.post(
                "https://slack.com/api/chat.delete",
                headers={"Authorization": f"Bearer {bot_token}", "Content-Type": "application/json"},
                json={"channel": msg_channel, "ts": msg_ts},
                timeout=10
            ).json()
            if del_resp.get("ok"):
                log.info(f"Deleted message {msg_ts} + {deleted} thread replies")
            else:
                log.warning(f"Delete failed: {del_resp.get('error')} — may not be a bot message")
        return jsonify({"ok": True})

    # 👎 thumbsdown = not relevant — log feedback and reply
    if event_type == "reaction_added" and event.get("reaction") == THUMBSDOWN_EMOJI:
        item = event.get("item", {})
        msg_ts = item.get("ts", "")
        if not msg_ts:
            return jsonify({"ok": True})
        msg = get_message(BD_CHANNEL_ID, msg_ts)
        text = msg.get("text", "")
        if "New BD Opportunity" not in text and ":snow_capped_mountain:" not in text and "🏔️" not in text:
            return jsonify({"ok": True})
        opp = extract_opp_from_message(text)
        triggered_by = event.get("user", "unknown")
        log.info(f"👎 not-relevant feedback: {opp.get('title','?')[:60]} by {triggered_by}")
        # Log to feedback.jsonl
        _log_feedback_opp(opp, "no", triggered_by)
        # Reply confirming
        title = opp.get("title", "this opportunity")
        post_reply(BD_CHANNEL_ID, msg_ts,
            f"Got it — marked *{title[:80]}* as not relevant. "
            f"Future similar opps will be weighted down in the AI review. 👎")
        return jsonify({"ok": True})

    # ✅ white_check_mark = mark as submitted
    if event_type == "reaction_added" and event.get("reaction") == SUBMIT_EMOJI:
        item = event.get("item", {})
        msg_ts = item.get("ts", "")
        if not msg_ts:
            return jsonify({"ok": True})
        msg = get_message_with_continuation(BD_CHANNEL_ID, msg_ts)
        text = msg.get("text", "")
        if "New BD Opportunity" not in text and ":snow_capped_mountain:" not in text and "🏔️" not in text:
            return jsonify({"ok": True})
        opp = extract_opp_from_message(text)
        triggered_by = event.get("user", "unknown")
        title = opp.get("title", "")
        portal = opp.get("portal", "")
        log.info(f"✅ submit reaction: {title[:60]} by {triggered_by}")

        # Mark submitted in Yukon Prospector DB
        scanner_token = os.environ.get("SCANNER_API_TOKEN", "")
        submit_ok = False
        try:
            sr = requests.post(
                "http://localhost:3000/api/opportunities/submit-by-title",
                headers={
                    "Authorization": f"Bearer {scanner_token}",
                    "Content-Type": "application/json",
                },
                json={"title": title, "portal": portal, "submittedBy": triggered_by},
                timeout=10,
            )
            submit_ok = sr.status_code == 200
            if not submit_ok:
                log.warning(f"Submit API returned {sr.status_code}: {sr.text[:100]}")
        except Exception as e:
            log.error(f"Submit API call failed: {e}")

        # Update BD Activities card status to Completed
        try:
            _update_bd_card_status(title, "completed")
        except Exception as e:
            log.warning(f"BD card status update failed: {e}")

        now_str = datetime.now().strftime("%b %d, %Y")
        if submit_ok:
            post_reply(BD_CHANNEL_ID, msg_ts,
                f"✅ Marked *{title[:80]}* as submitted on {now_str}.")
        else:
            post_reply(BD_CHANNEL_ID, msg_ts,
                f"✅ Noted submission for *{title[:80]}* — but couldn't update the database (is Yukon Prospector running?).")
        return jsonify({"ok": True})

    if event_type == "reaction_added" and event.get("reaction") == ADD_EMOJI:
        item = event.get("item", {})
        msg_ts = item.get("ts", "")
        if not msg_ts:
            return jsonify({"ok": True})

        # Get the original message (with continuation if Slack split it)
        msg = get_message_with_continuation(BD_CHANNEL_ID, msg_ts)
        text = msg.get("text", "")

        # Only act on Yukon opp messages
        if "New BD Opportunity" not in text and ":snow_capped_mountain:" not in text and "🏔️" not in text:
            return jsonify({"ok": True})

        is_forecast = "NASA Forecast" in text or "📋 NASA Forecast" in text or ":clipboard: NASA Forecast" in text

        opp = extract_opp_from_message(text)
        triggered_by = event.get("user", "unknown")
        log.info(f"👍 reaction trigger ({'forecast' if is_forecast else 'opp'}): {opp.get('title','?')[:60]} by {triggered_by}")

        if _is_card_created(BD_CHANNEL_ID, msg_ts):
            log.info(f"Skipping — card already created for {msg_ts}")
            return jsonify({"ok": True})
        _mark_card_created(BD_CHANNEL_ID, msg_ts)

        if is_forecast:
            # Route to Yukon BD Opportunities list with Forecasts status
            if create_forecast_card(opp, triggered_by):
                post_reply(BD_CHANNEL_ID, msg_ts,
                    f"📋 Added *{opp.get('title','?')[:80]}* to Yukon BD Opportunities (Forecasts).")
            else:
                post_reply(BD_CHANNEL_ID, msg_ts, "⚠️ Failed to create forecast card.")
        else:
            if create_bd_card(opp, triggered_by, msg_ts=msg_ts, channel=BD_CHANNEL_ID):
                _log_feedback_opp(opp, "yes", triggered_by)
                post_reply(BD_CHANNEL_ID, msg_ts,
                    f"✅ Added *{opp.get('title','?')[:80]}* to BD Activities board (Backlog).")
            else:
                post_reply(BD_CHANNEL_ID, msg_ts, "⚠️ Failed to create BD Activities card.")

    # ── MESSAGE / REPLY ─────────────────────────────────────────────
    elif event_type == "message" and event.get("thread_ts"):
        text = event.get("text", "").lower().strip()
        thread_ts = event.get("thread_ts", "")
        bot_id = event.get("bot_id")

        # Ignore bot messages and our own replies
        if bot_id or event.get("subtype"):
            return jsonify({"ok": True})

        # Auto-respond if this is a reply in a thread where Yukon has already posted
        thread_key = f"{channel}:{thread_ts}"
        if thread_key in _yukon_threads:
            raw_text = event.get("text", "").strip()
            if raw_text:
                log.info(f"Thread follow-up in {thread_ts}: {raw_text[:60]}")
                handle_mention(event, data)
                return jsonify({"ok": True})

        # Check for trigger phrase (add to board)
        if not any(trigger in text for trigger in ADD_TRIGGERS):
            return jsonify({"ok": True})

        # Get the parent message
        parent = get_message(BD_CHANNEL_ID, thread_ts)
        parent_text = parent.get("text", "")

        if "New BD Opportunity" not in parent_text and ":snow_capped_mountain:" not in parent_text and "🏔️" not in parent_text:
            return jsonify({"ok": True})

        opp = extract_opp_from_message(parent_text)
        triggered_by = event.get("user", "unknown")
        log.info(f"Reply trigger: {opp.get('title','?')[:60]} by {triggered_by}")

        if _is_card_created(BD_CHANNEL_ID, thread_ts):
            log.info(f"Skipping — BD card already created for {thread_ts}")
            return jsonify({"ok": True})
        _mark_card_created(BD_CHANNEL_ID, thread_ts)

        if create_bd_card(opp, triggered_by, msg_ts=thread_ts, channel=BD_CHANNEL_ID):
            post_reply(BD_CHANNEL_ID, thread_ts,
                f"✅ Added *{opp.get('title','?')[:80]}* to BD Activities board (Backlog).")
        else:
            post_reply(BD_CHANNEL_ID, thread_ts, "⚠️ Failed to create BD Activities card.")

    return jsonify({"ok": True})


@app.route("/health")
def health():
    return jsonify({"ok": True, "service": "yukon-slack-events"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3002))
    log.info(f"Yukon Slack Events server starting on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
