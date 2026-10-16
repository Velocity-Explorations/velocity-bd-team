from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from portals.vulcan_sof import auth, browser, session


@pytest.fixture(scope="module")
def ctx() -> Iterator[tuple[object, object]]:
    pw, b, context, page = browser.launch()
    try:
        yield context, page
    finally:
        browser.close_all(pw, b, context, page)


def test_save_and_load_round_trip(ctx, tmp_path: Path) -> None:
    context, _ = ctx
    context.add_cookies([{"name": "sid", "value": "abc", "domain": "example.invalid", "path": "/"}])
    path = tmp_path / "cookies.json"
    assert session.save_cookies(context, path) is True
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert any(c["name"] == "sid" for c in saved)

    context.clear_cookies()
    assert context.cookies() == []
    assert session.load_cookies(context, path) is True
    assert any(c["name"] == "sid" and c["value"] == "abc" for c in context.cookies())


def test_load_handles_missing_empty_and_garbage(ctx, tmp_path: Path) -> None:
    context, _ = ctx
    assert session.load_cookies(context, tmp_path / "missing.json") is False
    empty = tmp_path / "empty.json"
    empty.write_text("[]", encoding="utf-8")
    assert session.load_cookies(context, empty) is False
    garbage = tmp_path / "garbage.json"
    garbage.write_text("not json", encoding="utf-8")
    assert session.load_cookies(context, garbage) is False
    session.clear_cookies(tmp_path / "never-existed.json")   # must not raise


def test_save_never_raises(tmp_path: Path) -> None:
    class Broken:
        def cookies(self) -> list:
            raise RuntimeError("context closed")

    assert session.save_cookies(Broken(), tmp_path / "x.json") is False   # type: ignore[arg-type]


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
    cookie_path = tmp_path / "cookies.json"
    cookie_path.write_text(json.dumps([{"name": "sid", "value": "x", "domain": "vulcan-sof.com", "path": "/"}]), encoding="utf-8")
    monkeypatch.setattr(auth, "load_cookies", lambda c: session.load_cookies(c, cookie_path))
    monkeypatch.setattr(page, "goto", lambda url, **kw: page.set_content("<html><body><h1>Calls</h1></body></html>"))
    monkeypatch.setattr(type(page), "url", property(lambda self: "https://vulcan-sof.com/login/ng2/search/calls"))

    def must_not_run(*a, **k):
        raise AssertionError("password path should not run")

    monkeypatch.setattr(auth, "_login", must_not_run)
    assert auth.login(page, context, "u", "p") is True
