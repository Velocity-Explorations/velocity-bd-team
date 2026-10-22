"""
Yukon — Description Summarizer
Uses claude -p CLI to generate concise, actionable summaries of opportunity descriptions.
"""

import logging
import os
import subprocess
import time
from typing import Dict, List

log = logging.getLogger(__name__)

SUMMARIZE_TIMEOUT = 45
SUMMARIZE_COOLDOWN_SEC = 0.3


def summarize_description(description: str, title: str = "", agency: str = "") -> str:
    if not description or len(description.strip()) < 50:
        return description or ""

    prompt = "\n".join([
        "Summarize this government opportunity in 2-3 concise sentences.",
        "Focus on: what they need, what kind of work it involves, and any key requirements.",
        "Be specific and actionable — a BD team should immediately understand if this is worth pursuing.",
        "Do not include boilerplate about the solicitation process.",
        "",
        f"Title: {title}",
        f"Agency: {agency}",
        f"Description: {description[:3000]}",
    ])

    env = {k: v for k, v in os.environ.items()
           if k != "CLAUDECODE" and not k.startswith("CLAUDE_CODE_") and k != "AI_AGENT"}

    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True, text=True, timeout=SUMMARIZE_TIMEOUT,
            env=env,
        )
        if result.returncode != 0:
            log.warning(f"claude -p failed for '{title[:40]}': {result.stderr[:100]}")
            return ""
        summary = result.stdout.strip()
        return summary
    except subprocess.TimeoutExpired:
        log.warning(f"claude -p timed out for '{title[:40]}'")
    except FileNotFoundError:
        log.error("claude CLI not found — is Claude Code installed?")
    except Exception as e:
        log.error(f"Summarization error for '{title[:40]}': {e}")

    return ""


def summarize_opportunities(opps: List[Dict]) -> List[Dict]:
    if not opps:
        return opps

    log.info(f"── Summarizing {len(opps)} opportunity descriptions ──")

    for idx, opp in enumerate(opps, start=1):
        title = opp.get("title", "")
        description = opp.get("description", "")
        agency = opp.get("department", "")

        log.info(f"Summarizing {idx}/{len(opps)}: {title[:60]}")
        summary = summarize_description(description, title, agency)

        if summary:
            opp["description_summary"] = summary
            log.info(f"  Summary: {summary[:80]}...")
        else:
            opp["description_summary"] = ""

        if idx < len(opps):
            time.sleep(SUMMARIZE_COOLDOWN_SEC)

    summarized = sum(1 for o in opps if o.get("description_summary"))
    log.info(f"Summarization complete: {summarized}/{len(opps)} summaries generated")
    return opps
