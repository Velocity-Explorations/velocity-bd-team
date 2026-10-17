"""The shared keyword filter, driven by a throwaway settings file."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledger import queries as lq
from portals.shared import keyword_filter as kf

SETTINGS = """
broad_keywords: [software, data, ai]
tight_keywords: [machine learning]
blocklist_patterns:
  - '\\bspare parts\\b'
"""


@pytest.fixture
def keywords_file(tmp_path: Path) -> Path:
    path = tmp_path / "keywords.yaml"
    path.write_text(SETTINGS, encoding="utf-8")
    return path


def test_rules_in_order(keywords_file: Path) -> None:
    kw = kf.load_keywords(keywords_file)
    blocked = kf.decide({"id": "a", "title": "Software spare parts", "description": ""}, kw)
    assert blocked.result == "rejected" and blocked.reason == "blocklist: \\bspare parts\\b"
    unmatched = kf.decide({"id": "b", "title": "Lawn care", "description": "mowing"}, kw)
    assert unmatched.result == "rejected" and unmatched.reason == kf.REASON_NO_KEYWORD
    tight = kf.decide({"id": "c", "title": "Machine learning for data", "description": "software"}, kw)
    assert tight.result == "kept" and tight.tier == "tight"
    assert tight.keywords == ["software", "data", "machine learning"]
    broad = kf.decide({"id": "d", "title": "Software", "description": ""}, kw)
    assert broad.result == "kept" and broad.tier == "broad" and broad.keywords == ["software"]


def test_filter_calls_writes_the_ledger_and_follows_the_file(ledger_db: str, keywords_file: Path, tmp_path: Path) -> None:
    run = lq.start_run("Example")
    lq.upsert_call({"id": "ex-a", "portal": "Example", "title": "Machine learning software", "description": ""}, run)
    lq.upsert_call({"id": "ex-b", "portal": "Example", "title": "Quantum widgets", "description": ""}, run)

    kept, rejected = kf.filter_calls(lq.calls_where(filter_result="pending"), keywords_file)
    assert [d.id for d in kept] == ["ex-a"] and [d.id for d in rejected] == ["ex-b"]
    a = lq.get_call("ex-a")
    assert a and a["filter_result"] == "kept" and a["match_tier"] == "tight"
    assert json.loads(a["matched_keywords"]) == ["software", "machine learning"]

    other = tmp_path / "other.yaml"
    other.write_text("broad_keywords: [quantum]\ntight_keywords: []\nblocklist_patterns: []\n", encoding="utf-8")
    kept, _ = kf.filter_calls(lq.calls_where(), other)
    assert [d.id for d in kept] == ["ex-b"]


def test_malformed_settings_are_a_clear_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("broad_keywords: notalist\n", encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        kf.load_keywords(bad)
    assert "broad_keywords" in str(exc.value)
