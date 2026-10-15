"""
Yukon — Discord alert delivery
Posts new opportunities to a Discord channel via REST API.
"""

import logging
import os
import time
from pathlib import Path
from typing import Dict, List

import requests
from dotenv import load_dotenv

log = logging.getLogger(__name__)

DISCORD_API = "https://discord.com/api/v10"


def _get_bot_token() -> str:
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN not set in environment")
    return token


def _format_opp(opp: Dict) -> str:
    """Format an opportunity as a Discord message."""
    title = opp.get("title", "Unknown Title")
    portal = opp.get("portal", "Unknown Portal")
    opp_type = opp.get("type", "—")
    posted = opp.get("posted_date", "—")
    due = opp.get("due_date", "—")
    naics = opp.get("naics_code", "—")
    set_aside = opp.get("set_aside", "—") or "—"
    url = opp.get("url", "")
    department = opp.get("department", "") or "—"
    description = opp.get("description", "") or ""

    # Clean up dates
    if posted and "T" in str(posted):
        posted = posted.split("T")[0]
    if due and "T" in str(due):
        due = due.split("T")[0]

    is_forecast = opp.get("source_type") == "forecast"
    header = f"📋 **NASA Forecast — {portal}**" if is_forecast else f"🏔️ **New Opportunity — {portal}**"

    lines = [
        header,
        f"**{title}**",
        f"Agency: {department}",
    ]
    if is_forecast:
        est_val = opp.get("estimated_value", "") or "—"
        sol_fy = opp.get("sol_release_fy", "") or "—"
        sol_qtr = opp.get("sol_release_quarter", "") or "—"
        award_fy = opp.get("forecast_fy", "") or "—"
        award_qtr = opp.get("forecast_quarter", "") or "—"
        lines.append(f"Est. Value: {est_val} | Sol. Release: {sol_fy} {sol_qtr} | Award: {award_fy} {award_qtr}")
        lines.append(f"NAICS: {naics} | Set-Aside: {set_aside}")
        lines.append("⚠️ *This is a forecast, not an active solicitation*")
    else:
        lines.append(f"Type: {opp_type} | Posted: {posted} | Due: {due}")
        lines.append(f"NAICS: {naics} | Set-Aside: {set_aside}")
    if description:
        lines.append(f"> {description}")
    if url:
        lines.append(f"🔗 <{url}>")

    return "\n".join(lines)


def _format_slack_opp(opp: Dict) -> str:
    """Format an opportunity as a Slack message using mrkdwn (*bold*)."""
    title = opp.get("title", "Unknown Title")
    portal = opp.get("portal", "Unknown Portal")
    opp_type = opp.get("type", "—")
    posted = opp.get("posted_date", "—")
    due = opp.get("due_date", "—")
    naics = opp.get("naics_code", "—")
    set_aside = opp.get("set_aside", "—") or "—"
    url = opp.get("url", "")
    department = opp.get("department", "") or "—"
    description = opp.get("description", "") or ""

    # Clean up dates
    if posted and "T" in str(posted):
        posted = posted.split("T")[0]
    if due and "T" in str(due):
        due = due.split("T")[0]

    is_forecast = opp.get("source_type") == "forecast"
    header = f"📋 *NASA Forecast — {portal}*" if is_forecast else f"🏔️ *New BD Opportunity — {portal}*"

    lines = [
        header,
        f"*{title}*",
        f"Agency: {department}",
    ]
    if is_forecast:
        est_val = opp.get("estimated_value", "") or "—"
        sol_fy = opp.get("sol_release_fy", "") or "—"
        sol_qtr = opp.get("sol_release_quarter", "") or "—"
        award_fy = opp.get("forecast_fy", "") or "—"
        award_qtr = opp.get("forecast_quarter", "") or "—"
        lines.append(f"Est. Value: {est_val} | Sol. Release: {sol_fy} {sol_qtr} | Award: {award_fy} {award_qtr}")
        lines.append(f"NAICS: {naics} | Set-Aside: {set_aside}")
        lines.append("_This is a forecast, not an active solicitation_")
    else:
        lines.append(f"Type: {opp_type} | Posted: {posted} | Due: {due}")
        lines.append(f"NAICS: {naics} | Set-Aside: {set_aside}")
    if description:
        lines.append(f"> {description}")
    if url:
        lines.append(f"🔗 {url}")

    return "\n".join(lines)


def _load_slack_bot_token() -> str:
    """Load Yukon Slack bot token from secrets file."""
    from pathlib import Path
    import json as _json
    token_file = Path(__file__).parent.parent / "configs" / "velocity" / "slack_tokens.json"
    if token_file.exists():
        data = _json.loads(token_file.read_text())
        return data.get("SLACK_YUKON_BOT_TOKEN", data.get("SLACK_BOT_TOKEN", ""))
    return ""


def send_slack_alerts(opps: List[Dict], webhook_url: str = "", dry_run: bool = False,
                      channel_id: str = "C0AN8AMM4AW"):
    """Send opportunity alerts to Slack via bot token (chat.postMessage).
    Uses bot token so messages are deletable by reacting ❌ or 🪓.
    """
    if not opps:
        log.info("No new opportunities to alert (Slack).")
        return

    if dry_run:
        log.info(f"[DRY RUN] Would post {len(opps)} opportunities to Slack")
        for opp in opps:
            print("\n" + "─" * 60)
            print(_format_slack_opp(opp))
        print("─" * 60)
        return

    bot_token = _load_slack_bot_token()
    if not bot_token:
        log.warning("No Slack bot token found — skipping Slack alerts")
        return

    sent = 0
    for opp in opps:
        message = _format_slack_opp(opp)
        try:
            resp = requests.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {bot_token}", "Content-Type": "application/json"},
                json={"channel": channel_id, "text": message},
                timeout=10
            ).json()
            if resp.get("ok"):
                sent += 1
                log.info(f"Slack alerted: {opp.get('title', '?')[:60]}")
            elif resp.get("error") == "ratelimited":
                time.sleep(2)
                resp2 = requests.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {bot_token}", "Content-Type": "application/json"},
                    json={"channel": channel_id, "text": message},
                    timeout=10
                ).json()
                if resp2.get("ok"):
                    sent += 1
            else:
                log.error(f"Slack postMessage error: {resp.get('error','')}")
        except Exception as e:
            log.error(f"Failed to send Slack alert: {e}")

        if len(opps) > 1:
            time.sleep(1)

    log.info(f"Slack alerts sent: {sent}/{len(opps)}")


def send_alerts(opps: List[Dict], channel_id: str, dry_run: bool = False):
    """Send opportunity alerts to a Discord channel."""
    if not opps:
        log.info("No new opportunities to alert.")
        return

    if dry_run:
        log.info(f"[DRY RUN] Would post {len(opps)} opportunities to channel {channel_id}")
        for opp in opps:
            print("\n" + "─" * 60)
            print(_format_opp(opp))
        print("─" * 60)
        return

    token = _get_bot_token()
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json",
    }
    url = f"{DISCORD_API}/channels/{channel_id}/messages"

    sent = 0
    for opp in opps:
        message = _format_opp(opp)
        try:
            resp = requests.post(url, headers=headers, json={"content": message}, timeout=10)
            if resp.status_code == 200:
                sent += 1
                log.info(f"Alerted: {opp.get('title', '?')[:60]}")
            elif resp.status_code == 429:
                retry_after = resp.json().get("retry_after", 2)
                log.warning(f"Rate limited — sleeping {retry_after}s")
                time.sleep(retry_after)
                resp = requests.post(url, headers=headers, json={"content": message}, timeout=10)
                if resp.status_code == 200:
                    sent += 1
            else:
                log.error(f"Discord API error {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            log.error(f"Failed to send alert: {e}")

        if len(opps) > 1:
            time.sleep(1)

    log.info(f"Alerts sent: {sent}/{len(opps)}")
