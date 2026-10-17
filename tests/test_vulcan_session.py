"""Vulcan SOF's own session rules: where its cookies live and what counts as logged in."""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from portals.shared import browser
from portals.vulcan_sof import auth


@pytest.fixture(scope="module")
def ctx() -> Iterator[tuple[object, object]]:
    pw, b, context, page = browser.launch()
    try:
        yield context, page
    finally:
        browser.close_all(pw, b, context, page)


def test_vulcan_cookies_live_in_its_own_data_folder() -> None:
    assert auth.COOKIE_FILE.parts[-3:] == ("data", "vulcan_sof", "cookies.json")


def test_is_logged_in_ignores_app_prefix(ctx, monkeypatch: pytest.MonkeyPatch) -> None:
    _, page = ctx
    page.set_content("<html><body><h1>Calls</h1><p>Search results</p></body></html>")
    cases = {
        "https://vulcan-sof.com/login/ng2/search/calls": True,
        "https://vulcan-sof.com/login/ng2/home/commercial/abc": True,
        "https://vulcan-sof.com/login/ng2/auth/login": False,
    }
    for url, expected in cases.items():
        monkeypatch.setattr(type(page), "url", property(lambda self, u=url: u))
        assert auth.is_logged_in(page) is expected, url


def test_login_restores_from_cookies_without_password(ctx, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    context, page = ctx
    cookie_file = tmp_path / "cookies.json"
    cookie_file.write_text(json.dumps([{"name": "sid", "value": "x", "domain": "vulcan-sof.com", "path": "/"}]), encoding="utf-8")
    monkeypatch.setattr(auth, "COOKIE_FILE", cookie_file)
    monkeypatch.setattr(page, "goto", lambda url, **kw: page.set_content("<html><body><h1>Calls</h1></body></html>"))
    monkeypatch.setattr(type(page), "url", property(lambda self: "https://vulcan-sof.com/login/ng2/search/calls"))

    def must_not_run(*a, **k):
        raise AssertionError("password path should not run")

    monkeypatch.setattr(auth, "_login", must_not_run)
    assert auth.login(page, context, "u", "p") is True
