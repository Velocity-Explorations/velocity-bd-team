"""Vulcan SOF's keyword settings, applied by the shared keyword filter."""
from __future__ import annotations

import pytest

from ledger import queries as lq
from portals.shared import keyword_filter as kf
from portals.vulcan_sof.portal import KEYWORDS_PATH, filter_rows
from portals.vulcan_sof.run_filter import summarize

KW = kf.load_keywords(KEYWORDS_PATH)


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
    d = kf.decide({"id": "x", "title": title, "description": description}, KW)
    assert d.result == result and d.tier == tier
    if reason_prefix:
        assert d.reason is not None and d.reason.startswith(reason_prefix)


def test_blocklist_wins_over_keywords_and_hits_are_listed() -> None:
    d = kf.decide({"id": "x", "title": "AI spare parts forecasting", "description": "machine learning"}, KW)
    assert d.result == "rejected" and d.reason == "blocklist: \\bspare parts\\b"
    d = kf.decide({"id": "x", "title": "Command and Control software", "description": "cloud c2 analytics"}, KW)
    assert d.tier == "tight"
    assert {"software", "command and control", "c2", "cloud", "analytics"} <= set(d.keywords)
    assert len(d.keywords) == len(set(d.keywords))


def test_known_weakness_ai_in_maintain() -> None:
    d = kf.decide({"id": "x", "title": "Maintain the grounds", "description": ""}, KW)
    assert d.result == "kept" and d.tier == "broad" and d.keywords == ["ai"]


def test_portal_filter_uses_vulcan_keywords(ledger_db: str) -> None:
    run = lq.start_run("Vulcan SOF")
    lq.upsert_call({"id": "vulcan-a", "portal": "Vulcan SOF", "title": "Edge AI", "description": "computer vision"}, run)
    lq.upsert_call({"id": "vulcan-b", "portal": "Vulcan SOF", "title": "Dredging", "description": "harbor dredging"}, run)
    lq.upsert_call({"id": "vulcan-c", "portal": "Vulcan SOF", "title": "Quantum widgets", "description": "no overlap here"}, run)
    kept, rejected = filter_rows(lq.calls_where(filter_result="pending"))
    assert [d.id for d in kept] == ["vulcan-a"] and [d.id for d in rejected] == ["vulcan-b", "vulcan-c"]
    assert summarize(kept, rejected) == {"total": 3, "kept_tight": 1, "kept_broad": 0, "rejected_blocklist": 1, "rejected_no_keyword": 1}
