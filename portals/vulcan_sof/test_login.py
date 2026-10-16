"""Live login check against Vulcan SOF. Not a pytest test; run it by hand:

    python -m portals.vulcan_sof.test_login            # real credentials from .env
    python -m portals.vulcan_sof.test_login --bad-password   # expect a clean False

On success it opens the calls listing, saves data/after_login.png, and prints the URL and
the number of anchors whose href contains collectionUuid. Exit code 0 on success, 1 on a
failed login, 2 on a configuration problem.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from config import ConfigError, require
from portals.vulcan_sof.auth import login, open_calls
from portals.vulcan_sof.browser import close_all, launch
from portals.vulcan_sof.session import clear_cookies

REPO_ROOT = Path(__file__).resolve().parents[2]
SCREENSHOT = REPO_ROOT / "data" / "after_login.png"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Vulcan SOF live login check")
    parser.add_argument("--bad-password", action="store_true", help="use a wrong password to prove a clean failure")
    parser.add_argument("--fresh", action="store_true", help="delete the saved cookies first, forcing password + OTP")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    started = time.time()
    if args.fresh:
        clear_cookies()

    try:
        username = require("VULCAN_SOF_USERNAME")
        password = "definitely-not-the-password" if args.bad_password else require("VULCAN_SOF_PASSWORD")
        require("VULCAN_OTP_MAILBOX")
    except ConfigError as exc:
        print(exc)
        return 2

    pw, browser, context, page = launch()
    try:
        ok = login(page, context, username, password)
        print(f"login() returned {ok}")
        if not ok:
            return 1
        url = open_calls(page)
        SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SCREENSHOT), full_page=True, timeout=15_000)
        count = page.evaluate("() => document.querySelectorAll('a[href*=\"collectionUuid\"]').length")
        print(f"calls listing URL: {url}")
        print(f"collectionUuid anchors: {count}")
        print(f"saved {SCREENSHOT.relative_to(REPO_ROOT)}")
        return 0
    finally:
        close_all(pw, browser, context, page)
        print(f"wall clock: {time.time() - started:.1f} s")


if __name__ == "__main__":
    sys.exit(main())
