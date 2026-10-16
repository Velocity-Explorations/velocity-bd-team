"""Reconnaissance of the Vulcan SOF login page. No credentials are used.

    python -m portals.vulcan_sof.recon

Loads the login page headless, saves a full-page screenshot and an inventory of every
<input> and <button> to data/, and prints the inventory as JSON plus the final URL and the
first 300 characters of visible text.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from playwright.sync_api import Page

from portals.vulcan_sof.browser import close_all, launch

LOGIN_URL = "https://vulcan-sof.com/login/ng2/auth/login"
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
SCREENSHOT = DATA_DIR / "recon_login.png"
INVENTORY = DATA_DIR / "recon_login.json"

FORM_JS = """
() => ({
  inputs: Array.from(document.querySelectorAll('input')).map(el => ({
    type: el.getAttribute('type') || 'text',
    name: el.getAttribute('name'),
    id: el.id || null,
    placeholder: el.getAttribute('placeholder'),
    aria_label: el.getAttribute('aria-label'),
    autocomplete: el.getAttribute('autocomplete'),
    visible: el.offsetParent !== null
  })),
  buttons: Array.from(document.querySelectorAll('button')).map(el => ({
    text: (el.innerText || el.textContent || '').trim(),
    type: el.getAttribute('type'),
    disabled: el.disabled
  }))
})
"""


def collect_form(page: Page) -> dict[str, Any]:
    return page.evaluate(FORM_JS)


def body_text(page: Page, limit: int = 300) -> str:
    text = page.evaluate("() => document.body ? document.body.innerText : ''")
    return " ".join(text.split())[:limit]


def recon(url: str = LOGIN_URL) -> dict[str, Any]:
    pw, browser, context, page = launch()
    try:
        page.goto(url, timeout=30_000, wait_until="domcontentloaded")
        page.wait_for_load_state("domcontentloaded", timeout=15_000)
        page.wait_for_timeout(2_000)
        try:
            page.wait_for_selector("input", timeout=10_000)   # Angular renders after bootstrap
        except Exception:
            pass
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SCREENSHOT), full_page=True, timeout=15_000)
        result = collect_form(page)
        result["url"] = page.url
        result["body_text_head"] = body_text(page)
        INVENTORY.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result
    finally:
        close_all(pw, browser, context, page)


def main() -> int:
    result = recon()
    print(json.dumps({"inputs": result["inputs"], "buttons": result["buttons"]}, indent=2))
    print(f"\nfinal url: {result['url']}")
    print(f"body text (first 300): {result['body_text_head']}")
    print(f"\nsaved {SCREENSHOT.relative_to(REPO_ROOT)} and {INVENTORY.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
