"""The SSC Front Door Events list, read over plain HTTP. No browser and no login.

    ids = framework_ids(home_html)          # (fwuid, communityApp "loaded" hash)
    body = request_body(page, size, ids)    # the form the site's own Events page posts
    listings = fetch_records()              # every listing, all pages

The Events page loads its list with one call to the site's Salesforce framework endpoint;
this module makes the same call (docs: portals/ssc_front_door/NOTES.md). Salesforce changes
the framework id at each release, so it is read from the home page on every run, and read
again once if the call fails.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

BASE = "https://sscfrontdoor.experience.crmforce.mil/SSCFrontDoor"
HOME_URL = f"{BASE}/s/"
AURA_URL = f"{BASE}/s/sfsites/aura?r=1&aura.ApexAction.execute=1"
EVENTS_PAGE = "/SSCFrontDoor/s/events"
APP = "siteforce:communityApp"
LOADED_KEY = f"APPLICATION@markup://{APP}"
PAGE_SIZE = 250
MAX_PAGES = 20
TIMEOUT_S = 30
USER_AGENT = "velocity-bd-team scanner (Velocity Explorations)"

FWUID_RE = re.compile(r'"fwuid":"([^"]+)"')
LOADED_RE = re.compile(r'"APPLICATION@markup://siteforce:communityApp":"([^"]+)"')

Opener = Callable[..., Any]   # urllib.request.urlopen, or a test's stand-in


class FrontDoorError(RuntimeError):
    """The site did not answer as expected. The pipeline records it and alerts."""


def framework_ids(home_html: str) -> tuple[str, str]:
    """The framework id and the app's loaded hash, from the home page's script addresses."""
    text = urllib.parse.unquote(home_html)
    fwuid, loaded = FWUID_RE.search(text), LOADED_RE.search(text)
    if not fwuid or not loaded:
        raise FrontDoorError("the home page no longer names its framework id")
    return fwuid.group(1), loaded.group(1)


def request_body(page: int, page_size: int, ids: tuple[str, str]) -> str:
    """The form body for one page of the Events list."""
    action = {
        "id": "1;a",
        "descriptor": "aura://ApexActionController/ACTION$execute",
        "callingDescriptor": "UNKNOWN",
        "params": {
            "namespace": "",
            "classname": "SSCFD_ManagedContentController",
            "method": "getContentList",
            "params": {"page": page, "pageSize": page_size, "language": "en_US", "filterby": "Events"},
            "cacheable": True,
            "isContinuation": False,
        },
    }
    context = {"mode": "PROD", "fwuid": ids[0], "app": APP, "loaded": {LOADED_KEY: ids[1]},
               "dn": [], "globals": {}, "uad": True}
    return urllib.parse.urlencode({
        "message": json.dumps({"actions": [action]}),
        "aura.context": json.dumps(context),
        "aura.pageURI": EVENTS_PAGE,
        "aura.token": "null",
    })


def records_from(response: dict[str, Any]) -> list[dict[str, Any]]:
    """The listings in one response; raises unless the call succeeded."""
    try:
        action = response["actions"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise FrontDoorError("the Events call returned an unexpected shape") from exc
    if action.get("state") != "SUCCESS":
        errors = action.get("error") or []
        detail = errors[0].get("message") if errors and isinstance(errors[0], dict) else action.get("state")
        raise FrontDoorError(f"the Events call failed: {detail}")
    listings = (action.get("returnValue") or {}).get("returnValue")
    if not isinstance(listings, list):
        raise FrontDoorError("the Events call returned no list")
    return listings


def _get(opener: Opener, url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with opener(request, timeout=TIMEOUT_S) as reply:
        return reply.read().decode("utf-8", errors="replace")


def _post(opener: Opener, body: str) -> dict[str, Any]:
    request = urllib.request.Request(AURA_URL, data=body.encode("utf-8"), method="POST", headers={
        "User-Agent": USER_AGENT,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    })
    with opener(request, timeout=TIMEOUT_S) as reply:
        return json.loads(reply.read().decode("utf-8"))


def _page(opener: Opener, page: int, page_size: int, ids: tuple[str, str]) -> list[dict[str, Any]]:
    return records_from(_post(opener, request_body(page, page_size, ids)))


def fetch_records(opener: Opener | None = None, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    """Every listing on the Events list. A failed page is retried once with freshly read ids."""
    opener = opener or urllib.request.urlopen
    ids = framework_ids(_get(opener, HOME_URL))
    found: list[dict[str, Any]] = []
    for page in range(MAX_PAGES):
        try:
            batch = _page(opener, page, page_size, ids)
        except (FrontDoorError, OSError, ValueError):
            ids = framework_ids(_get(opener, HOME_URL))   # a platform release may have changed the id
            batch = _page(opener, page, page_size, ids)
        found += batch
        if len(batch) < page_size:
            return found
    raise FrontDoorError(f"the Events list ran past {MAX_PAGES} pages")
