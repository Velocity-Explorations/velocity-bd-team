"""The dashboard fits the window: no sideways scrolling, and 24px each side (PRO-552).

These tests load the pages in headless Chromium, so they need a dashboard that is serving.
Name it in DASHBOARD_TEST_URL (for example http://localhost:8000); without it they are skipped.
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest

URL = os.environ.get("DASHBOARD_TEST_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(not URL, reason="set DASHBOARD_TEST_URL to a running dashboard")

PAGES = ["/", "/review", "/calls", "/brief", "/judges", "/requests", "/runs", "/proposals", "/profile"]
WIDTHS = [1024, 1280, 1440, 1920, 2560]
MARGIN = 24

# The top bar's and the content's inner edges (inside their padding), how far the page scrolls
# sideways, and the most any table hides behind its own sideways scroll.
MEASURE = """() => {
  const inner = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return {left: r.left + parseFloat(s.paddingLeft), right: r.right - parseFloat(s.paddingRight)};
  };
  const hidden = Array.from(document.querySelectorAll('.table-wrap')).map((w) => w.scrollWidth - w.clientWidth);
  return {width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth,
          bar: inner(document.querySelector('.topbar')), main: inner(document.querySelector('main')),
          hidden: Math.max(0, ...hidden)};
}"""


@pytest.fixture(scope="module")
def page() -> Iterator[Any]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser.new_page(viewport={"width": WIDTHS[0], "height": 900})
        browser.close()


def problems(m: dict[str, Any]) -> list[str]:
    """What breaks the layout rule in one measurement."""
    found = []
    width = m["width"]
    if m["scroll"] > width:
        found.append(f"the page scrolls sideways by {m['scroll'] - width}px")
    for name in ("bar", "main"):
        left, right = m[name]["left"], m[name]["right"]
        if left < MARGIN - 0.5 or right > width - MARGIN + 0.5:
            found.append(f"{name} keeps {left:.0f}px and {width - right:.0f}px at the sides")
    if m["main"]["right"] < width - MARGIN - 0.5:
        found.append(f"the content stops {width - m['main']['right']:.0f}px short of the right edge")
    if m["hidden"] > 1:
        found.append(f"a table hides {m['hidden']}px behind a sideways scroll")
    return found


@pytest.mark.parametrize("path", PAGES)
def test_the_page_fits_the_window_with_24px_each_side(page: Any, path: str) -> None:
    page.goto(URL + path, wait_until="load", timeout=120_000)
    failures = []
    for width in WIDTHS:
        page.set_viewport_size({"width": width, "height": 900})
        failures += [f"{width}px: {p}" for p in problems(page.evaluate(MEASURE))]
    assert not failures, failures
