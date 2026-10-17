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


# --------------------------------------------------------------- editing the settings file

FILE_TEXT = r"""# Relevance filter. Edit this file, then re-run the filter.
# Blocklist entries are regular expressions.

broad_keywords:
  - software
  - data
  # added 2026-10-16 after a live run
  - zero trust

tight_keywords:
  - machine learning

blocklist_patterns:
  - '\brepair\b'
  - '\bspare parts\b'
"""


def _changes(**given: list[str]) -> dict[str, list[str]]:
    return {key: given.get(key, []) for key in kf.CHANGE_KEYS}


def test_apply_changes_adds_and_removes() -> None:
    kw = kf.load_keywords_text(FILE_TEXT)
    after = kf.apply_changes(kw, _changes(add_broad=["Digital Twin"], remove_broad=["data"], add_block=[r"\bturret\b"]))
    assert after.broad == ["software", "zero trust", "digital twin"]
    assert [b.pattern for b in after.blocklist] == [r"\brepair\b", r"\bspare parts\b", r"\bturret\b"]
    with pytest.raises(ValueError, match="'nope' is not in the broad keywords"):
        kf.apply_changes(kw, _changes(remove_broad=["nope"]))
    with pytest.raises(ValueError, match="not a valid blocklist pattern"):
        kf.apply_changes(kw, _changes(add_block=["(unclosed"]))


def test_edit_adds_items_under_a_dated_comment_and_keeps_everything_else() -> None:
    text = kf.edit_keywords_text(FILE_TEXT, _changes(add_broad=["digital twin"], add_block=[r"\bturret\b"]),
                                 note="added 2026-10-17 by request #3, approved by Dana")
    assert text.startswith("# Relevance filter. Edit this file, then re-run the filter.\n# Blocklist")
    assert ("  # added 2026-10-16 after a live run\n  - zero trust\n"
            "  # added 2026-10-17 by request #3, approved by Dana\n  - digital twin\n\ntight_keywords:") in text
    assert text.endswith(r"""  - '\bspare parts\b'
  # added 2026-10-17 by request #3, approved by Dana
  - '\bturret\b'
""")
    kw = kf.load_keywords_text(text)
    assert kw.broad[-1] == "digital twin" and kw.blocklist[-1].pattern == r"\bturret\b"


def test_edit_removes_only_the_named_lines() -> None:
    text = kf.edit_keywords_text(FILE_TEXT, _changes(remove_broad=["Data"], remove_block=[r"\brepair\b"]))
    assert text == FILE_TEXT.replace("  - data\n", "").replace(r"  - '\brepair\b'" + "\n", "")


def test_edit_quotes_values_yaml_would_misread() -> None:
    text = kf.edit_keywords_text(FILE_TEXT, _changes(add_broad=["c2: ops", "yes", "5g"]))
    assert "  - 'c2: ops'\n" in text and "  - 'yes'\n" in text and "  - 5g\n" in text
    assert kf.load_keywords_text(text).broad[-3:] == ["c2: ops", "yes", "5g"]


def test_edit_leaves_a_present_keyword_alone() -> None:
    assert kf.edit_keywords_text(FILE_TEXT, _changes(add_broad=["software"]), note="added today") == FILE_TEXT


def test_edit_refuses_what_it_cannot_do_safely() -> None:
    with pytest.raises(ValueError, match="'nope' is not in the tight keywords"):
        kf.edit_keywords_text(FILE_TEXT, _changes(remove_tight=["nope"]))
    with pytest.raises(ValueError, match="one item per line"):
        kf.edit_keywords_text(SETTINGS, _changes(add_broad=["digital twin"]))
