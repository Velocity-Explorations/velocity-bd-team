"""Short operational alerts to Slack (chat.postMessage).

    send_alert("FETCH TIMEOUT ...")  -> True when posted

Needs SLACK_BOT_TOKEN and SLACK_CHANNEL_ID. When either is missing, or Slack fails, the
alert is logged at WARNING and the function returns False. It never raises and never logs
the token. Standard library only.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from config import get

log = logging.getLogger("slack.alerts")

POST_URL = "https://slack.com/api/chat.postMessage"
TIMEOUT_S = 15


def send_alert(text: str, channel: str | None = None) -> bool:
    token = get("SLACK_BOT_TOKEN")
    channel = channel or get("SLACK_CHANNEL_ID")
    if not token or not channel:
        log.warning("Alert not sent (SLACK_BOT_TOKEN or SLACK_CHANNEL_ID missing): %s", text[:200])
        return False
    body = json.dumps({"channel": channel, "text": text}).encode("utf-8")
    request = urllib.request.Request(
        POST_URL,
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        log.warning("Alert not sent (%s: %s): %s", type(exc).__name__, str(exc)[:120], text[:200])
        return False
    if not payload.get("ok"):
        log.warning("Alert rejected by Slack (%s): %s", payload.get("error", "unknown"), text[:200])
        return False
    log.info("Alert sent to Slack")
    return True
