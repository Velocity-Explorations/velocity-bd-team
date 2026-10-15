"""
Yukon — Few-Shot Feedback Examples
Fetches recent triage decisions per profile and formats them
as few-shot examples for the LLM review prompt.
"""

import json
import logging
import os
from typing import Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

log = logging.getLogger(__name__)

MAX_VALID_EXAMPLES = 5
MAX_NOT_VALID_EXAMPLES = 5


def _api_base() -> str:
    return os.environ.get("YUKON_API_URL", "http://127.0.0.1:3000")


def _scanner_token() -> str:
    return os.environ.get("SCANNER_API_TOKEN", "")


def fetch_recent_examples(profile: str, limit: int = 50) -> List[dict]:
    url = f"{_api_base()}/api/scanner/triage-data?profile={profile}&limit={limit}"
    headers = {
        "Authorization": f"Bearer {_scanner_token()}",
        "Content-Type": "application/json",
    }
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return data.get("decisions", [])
    except (URLError, Exception) as e:
        log.warning(f"Failed to fetch feedback examples for {profile}: {e}")
        return []


def format_examples_block(decisions: List[dict]) -> str:
    valid = [d for d in decisions if d["reviewStatus"] == "valid"][:MAX_VALID_EXAMPLES]
    not_valid = [d for d in decisions if d["reviewStatus"] == "not_valid"][:MAX_NOT_VALID_EXAMPLES]

    if not valid and not not_valid:
        return ""

    lines = [
        "--- REVIEWER FEEDBACK (learn from these past decisions) ---",
    ]

    if valid:
        lines.append("")
        lines.append("APPROVED (the reviewer wants to see opportunities like these):")
        for opp in valid:
            title = opp.get("title", "?")[:80]
            agency = opp.get("agency", "") or ""
            notes = opp.get("reviewNotes", "") or ""
            line = f"  - \"{title}\""
            if agency:
                line += f" | Agency: {agency}"
            if notes:
                line += f" | Reviewer note: {notes}"
            lines.append(line)

    if not_valid:
        lines.append("")
        lines.append("REJECTED (the reviewer does NOT want opportunities like these):")
        for opp in not_valid:
            title = opp.get("title", "?")[:80]
            agency = opp.get("agency", "") or ""
            notes = opp.get("reviewNotes", "") or ""
            line = f"  - \"{title}\""
            if agency:
                line += f" | Agency: {agency}"
            if notes:
                line += f" | Reviewer note: {notes}"
            lines.append(line)

    lines.append("")
    lines.append("Use these examples to understand what this company is looking for.")
    lines.append("---")

    return "\n".join(lines)


def get_feedback_block(profile: str) -> str:
    decisions = fetch_recent_examples(profile)
    if not decisions:
        return ""
    block = format_examples_block(decisions)
    if block:
        log.info(f"Loaded {len(decisions)} feedback examples for {profile}")
    return block
