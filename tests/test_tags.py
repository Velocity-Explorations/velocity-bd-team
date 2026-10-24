"""Tags from a set list on each call: rules from the call's own data, and Claude's and Grok's
picks on the TAGS line of their review answers (PRO-556)."""
from __future__ import annotations

import json
from typing import Any

import pytest

import run
from ledger import queries as lq
from review import reviewer, tags
from tests.test_reviewer import FakeModel

TAGS = tags.load_tags()


def call(**fields: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"portal": "", "type": "", "department": "", "set_aside": "", "extra": None}
    row.update(fields)
    if isinstance(row["extra"], dict):
        row["extra"] = json.dumps(row["extra"])
    return row


def seed(call_id: str = "c-1", kept: bool = True, **fields: Any) -> dict[str, Any]:
    run_id = lq.start_run("Vulcan SOF")
    lq.upsert_call({"id": call_id, "portal": "Vulcan SOF", "title": "C2 software", "description": "software",
                    "type": "OTA Prototype", "department": "USSOCOM / SOF Enterprise", **fields}, run_id)
    lq.set_filter(call_id, "kept" if kept else "rejected", tier="broad" if kept else None)
    return lq.get_call(call_id)   # type: ignore[return-value]


def test_the_list_has_four_groups_and_the_prompt_asks_for_exactly_one_type() -> None:
    assert list(TAGS.groups) == ["type", "work", "customer", "access"]
    assert "White paper" in TAGS.groups["type"] and "Members only" in TAGS.groups["access"]
    block = tags.prompt_block(TAGS)
    assert "exactly one" in block
    assert all(name in block for names in TAGS.groups.values() for name in names)


@pytest.mark.parametrize(("text", "expected"), [
    ("VERDICT: yes\nREASON: fits\nTAGS: OTA, software, AI and ML, SOCOM", ["OTA", "Software", "AI and ML", "SOCOM"]),
    ("TAGS: RFI, Proposal, Space, Made up.", ["RFI", "Space"]),   # one type only; a tag not on the list is dropped
    ("VERDICT: no\nREASON: hardware", []),
    ("TAGS:", []),
])
def test_tags_are_read_from_the_answer_s_tags_line(text: str, expected: list[str]) -> None:
    assert tags.parse_tags(text, TAGS) == expected


@pytest.mark.parametrize(("row", "expected"), [
    (call(portal="Vulcan SOF", type="OTA Prototype", department="USSOCOM / SOF Enterprise"), ["OTA", "SOCOM"]),
    (call(portal="Vulcan SOF", type="Tech Experimentation"), ["Demo or exercise", "SOCOM"]),
    (call(portal="NASA Forecast", type="Forecast", department="NASA KSC", set_aside="Small Business Set Aside - Total"),
     ["Forecast", "NASA", "Small business set-aside"]),
    (call(portal="NASA Forecast", type="Forecast", set_aside="No set aside used"), ["Forecast", "NASA"]),
    (call(portal="NSTXL", type="OTA opportunity", department="SpEC", extra={"nstxl_members_only": True}),
     ["OTA", "USSF", "Members only"]),
    (call(portal="NSTXL", type="Solicitation", department="S2MARTS"), ["Navy"]),   # the judges pick its type
    (call(portal="AFWERX", type="SBIR cycle", extra={"afwerx_branches": ["Air Force", "Space Force"]}),
     ["SBIR or STTR", "USSF", "USAF"]),
    (call(portal="SpaceWERX", type="TACFI", department="U.S. Space Force"), ["SBIR or STTR", "USSF", "Phase II holders only"]),
    (call(portal="SSC Front Door", type="Webinar"), ["Event", "USSF"]),
    (call(portal="DIU", type="CSO", department="Defense Innovation Unit"), ["White paper", "DIU"]),
    (call(portal="SAM.gov", type="Sources sought", department="DEPT OF DEFENSE / DEPT OF THE ARMY / AMC",
          set_aside="Total Small Business Set-Aside (FAR 19.5)"), ["RFI", "Army", "Small business set-aside"]),
    (call(portal="SAM.gov", type="Special notice",
          department="OFFICE OF THE DIRECTOR OF NATIONAL INTELLIGENCE / INTELLIGENCE ADVANCED RESEARCH PROJECTS ACTIVITY"),
     ["Intelligence community"]),
    (call(portal="DOE SBIR", type="Upcoming"), ["SBIR or STTR", "DOE"]),
    (call(portal="Space Florida", type="Solicitation"), ["Proposal", "Other buyer"]),
    (call(portal="APFIT", type="APFIT cycle"), ["Sponsor needed"]),
])
def test_rules_tag_what_a_call_s_data_makes_certain(row: dict[str, Any], expected: list[str]) -> None:
    assert tags.rule_tags(row, TAGS) == expected


def test_every_tag_a_rule_can_set_is_on_the_list() -> None:
    assert tags.rule_tag_names() <= set(TAGS.order)


def test_the_review_prompt_asks_for_tags_from_the_list() -> None:
    prompt = reviewer.build_prompt({"title": "Edge AI", "type": "OTA Prototype", "portal": "Vulcan SOF"})
    assert "TAGS:" in prompt and tags.prompt_block(TAGS) in prompt


def test_setting_one_source_s_tags_replaces_only_that_source(ledger_db: str) -> None:
    seed()
    lq.set_tags("c-1", "rule", ["OTA", "SOCOM"])
    lq.set_tags("c-1", "claude", ["OTA", "Software"])
    lq.set_tags("c-1", "claude", ["RFI"])
    assert lq.tags_on("c-1") == {"rule": ["OTA", "SOCOM"], "claude": ["RFI"]}


def test_each_judge_tags_the_call_in_its_review_answer(ledger_db: str) -> None:
    row = seed()
    reviewer.review_calls([row], FakeModel(["VERDICT: yes\nREASON: Builds C2 software.\nTAGS: OTA, Software, C2, SOCOM"]),
                          sleep=lambda s: None)
    reviewer.judge_calls([row], FakeModel(["VERDICT: maybe\nREASON: Unclear.\nTAGS: Demo or exercise, Software"]), "grok",
                         sleep=lambda s: None)
    assert lq.tags_on("c-1") == {"claude": ["OTA", "Software", "C2", "SOCOM"], "grok": ["Demo or exercise", "Software"]}


def test_a_failed_or_tagless_answer_leaves_the_tags_alone(ledger_db: str) -> None:
    row = seed()
    lq.set_tags("c-1", "claude", ["OTA"])
    reviewer.review_calls([row], FakeModel([RuntimeError("a"), RuntimeError("b")]), sleep=lambda s: None)
    reviewer.review_calls([row], FakeModel(["VERDICT: yes\nREASON: Fits."]), sleep=lambda s: None)
    assert lq.tags_on("c-1") == {"claude": ["OTA"]}


def test_the_pipeline_tags_every_call_a_run_saw_by_its_rules(ledger_db: str) -> None:
    row = seed()
    assert run.tag_by_rules(row["last_run_id"]) == 1
    assert lq.tags_on("c-1") == {"rule": ["OTA", "SOCOM"]}


def test_the_backfill_tags_every_call_by_rules_and_reviewed_calls_by_both_judges(
        ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    seed("k-1")
    lq.set_review("k-1", "maybe", "Partly software.")
    seed("r-1", kept=False)
    monkeypatch.setattr(run, "review_model", lambda: FakeModel(["TAGS: OTA, Software"]))
    monkeypatch.setattr(run, "grok_model", lambda: FakeModel(["TAGS: OTA, AI and ML"]))
    monkeypatch.setattr(run, "grok_enabled", lambda: True)
    assert run.backfill_tags() == 0
    assert lq.tags_on("k-1") == {"rule": ["OTA", "SOCOM"], "claude": ["OTA", "Software"], "grok": ["OTA", "AI and ML"]}
    assert lq.tags_on("r-1") == {"rule": ["OTA", "SOCOM"]}
    assert run.backfill_tags() == 0   # a second pass finds nothing left to ask the judges
