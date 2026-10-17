"""Saved browser sessions, shared by every portal that logs in through a browser."""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from portals.shared import browser, session


@pytest.fixture(scope="module")
def context() -> Iterator[object]:
    pw, b, ctx, page = browser.launch()
    try:
        yield ctx
    finally:
        browser.close_all(pw, b, ctx, page)


def test_cookie_path_is_per_portal_under_data() -> None:
    path = session.cookie_path("example_portal")
    assert path.parts[-3:] == ("data", "example_portal", "cookies.json")
    assert path.is_absolute()


def test_save_and_load_round_trip(context, tmp_path: Path) -> None:
    context.add_cookies([{"name": "sid", "value": "abc", "domain": "example.invalid", "path": "/"}])
    path = tmp_path / "portal" / "cookies.json"   # the folder is created on save
    assert session.save_cookies(context, path) is True
    assert any(c["name"] == "sid" for c in json.loads(path.read_text(encoding="utf-8")))

    context.clear_cookies()
    assert context.cookies() == []
    assert session.load_cookies(context, path) is True
    assert any(c["name"] == "sid" and c["value"] == "abc" for c in context.cookies())


def test_load_handles_missing_empty_and_garbage(context, tmp_path: Path) -> None:
    assert session.load_cookies(context, tmp_path / "missing.json") is False
    empty = tmp_path / "empty.json"
    empty.write_text("[]", encoding="utf-8")
    assert session.load_cookies(context, empty) is False
    garbage = tmp_path / "garbage.json"
    garbage.write_text("not json", encoding="utf-8")
    assert session.load_cookies(context, garbage) is False


def test_save_never_raises(tmp_path: Path) -> None:
    class Broken:
        def cookies(self) -> list:
            raise RuntimeError("context closed")

    assert session.save_cookies(Broken(), tmp_path / "x.json") is False   # type: ignore[arg-type]


def test_clear_cookies(tmp_path: Path) -> None:
    path = tmp_path / "cookies.json"
    path.write_text("[]", encoding="utf-8")
    session.clear_cookies(path)
    assert not path.exists()
    session.clear_cookies(tmp_path / "never-existed.json")   # must not raise
