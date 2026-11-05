"""A minimal Linear GraphQL client on urllib, for the Pursuits sync (linear/pursuits.py).

    data = LinearClient().query(QUERY, variables)   # the response's data, or None

The key is BD_LINEAR_API_KEY, a personal API key of David's (docs/RUNBOOK.md, "Linear's Pursuits project"), so what
the sync writes reads as his. Every call has a 15 s timeout, logs failures and never raises into the pipeline. The key
is never logged.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from config import get

log = logging.getLogger(__name__)

API = "https://api.linear.app/graphql"
TIMEOUT_S = 15


class LinearClient:
    def __init__(self, key: str | None = None) -> None:
        self.key = key if key is not None else (get("BD_LINEAR_API_KEY") or "").strip()

    def query(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if not self.key:
            log.warning("Linear call skipped: BD_LINEAR_API_KEY missing")
            return None
        body = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
        request = urllib.request.Request(API, data=body, method="POST",
                                         headers={"Authorization": self.key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            log.warning("Linear call failed: HTTP %s %s", exc.code, str(exc.reason)[:200])
            return None
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            log.warning("Linear call failed: %s: %s", type(exc).__name__, str(exc)[:200])
            return None
        if payload.get("errors"):
            log.warning("Linear call rejected: %s", json.dumps(payload["errors"])[:300])
            return None
        return payload.get("data")
