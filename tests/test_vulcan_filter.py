from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledger import queries as lq
from portals.vulcan_sof import filter as vf
from portals.vulcan_sof.run_filter import summarize

KW = vf.load_keywords(vf.KEYWORDS_PATH)


def test_keywords_yaml_loads_three_lists() -> None:
    assert "software" in KW.broad and "computer vision" in KW.tight
    assert any(p.pattern == r"\bindustry day\b" for p in KW.blocklist)


@pytest.mark.parametrize(
    "title, description, result, tier, reason_prefix",
    [
        ("Edge AI for ISR", "Computer vision on small UAS", "kept", "tight", None),
        ("Warfighter Network Tools", "Mesh networking for the joint force", "kept", "broad", None),
        ("Hose Assembly Replacement", "Supply of hose assembly units", "rejected", None, "blocklist: \\bhose assembly\\b"),
        ("Valve Kit", "Supply of valves NSN 4720-01-123-4567", "rejected", None, "blocklist: \\bnsn\\s+\\d"),
        ("Industry Day: Software Modernization", "Join our industry day", "rejected", None, "blocklist: \\bindustry day\\b"),
        ("Runway Paving", "Construction of a new airfield", "rejected", None, "blocklist: \\bconstruction\\b"),
        ("Lawn Care", "Mowing and trimming", "rejected", None, "no keyword match"),
    ],
)
def test_decide_rules(title: str, description: str, result: str, tier: str | None, reason_prefix: str | None) -> None:
    d = vf.decide({"id": "x", "title": title, "description": description}, KW)
    assert d.result == result and d.tier == tier
    if reason_prefix:
        assert d.reason is not None and d.reason.startswith(reason_prefix)


def test_blocklist_wins_over_keywords_and_hits_are_listed() -> None:
    d = vf.decide({"id": "x", "title": "AI spare parts forecasting", "description": "machine learning"}, KW)
    assert d.result == "rejected" and d.reason == "blocklist: \\bspare parts\\b"
    d = vf.decide({"id": "x", "title": "Command and Control software", "description": "cloud c2 analytics"}, KW)
    assert d.tier == "tight"
    assert {"software", "command and control", "c2", "cloud", "analytics"} <= set(d.keywords)
    assert len(d.keywords) == len(set(d.keywords))


def test_known_weakness_ai_in_maintain() -> None:
    d = vf.decide({"id": "x", "title": "Maintain the grounds", "description": ""}, KW)
    assert d.result == "kept" and d.tier == "broad" and d.keywords == ["ai"]


def test_filter_calls_writes_ledger_and_yaml_change_alters_result(ledger_db: str, tmp_path: Path) -> None:
    run = lq.start_run("Vulcan SOF")
    lq.upsert_call({"id": "vulcan-a", "portal": "Vulcan SOF", "title": "Edge AI", "description": "computer vision"}, run)
    lq.upsert_call({"id": "vulcan-b", "portal": "Vulcan SOF", "title": "Dredging", "description": "harbor dredging"}, run)
    lq.upsert_call({"id": "vulcan-c", "portal": "Vulcan SOF", "title": "Quantum widgets", "description": "no overlap here"}, run)

    kept, rejected = vf.filter_calls(lq.calls_where(filter_result="pending"))
    assert [d.id for d in kept] == ["vulcan-a"] and [d.id for d in rejected] == ["vulcan-b", "vulcan-c"]
    assert lq.calls_where(filter_result="pending") == []
    a = lq.get_call("vulcan-a")
    assert a and a["filter_result"] == "kept" and a["match_tier"] == "tight"
    assert "computer vision" in json.loads(a["matched_keywords"])
    c = lq.get_call("vulcan-c")
    assert c and c["filter_result"] == "rejected" and c["filter_reason"] == "no keyword match"
    assert summarize(kept, rejected) == {"total": 3, "kept_tight": 1, "kept_broad": 0, "rejected_blocklist": 1, "rejected_no_keyword": 1}

    custom = tmp_path / "kw.yaml"
    custom.write_text("broad_keywords: [quantum]\ntight_keywords: []\nblocklist_patterns: []\n", encoding="utf-8")
    kept, rejected = vf.filter_calls(lq.calls_where(), custom)
    assert [d.id for d in kept] == ["vulcan-c"] and len(rejected) == 2
    assert lq.get_call("vulcan-c")["filter_result"] == "kept"   # type: ignore[index]


def test_malformed_yaml_is_a_clear_error(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("broad_keywords: notalist\n", encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        vf.load_keywords(bad)
    assert "broad_keywords" in str(exc.value)
