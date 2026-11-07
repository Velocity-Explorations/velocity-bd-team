from __future__ import annotations

from ledger import queries as lq
from review import feedback


def test_format_examples_labels_and_why() -> None:
    rows = [
        {"human_status": "pursue", "title": "Edge AI", "ai_verdict": "yes", "human_notes": "[2026-10-16T10:00:00Z U1] strong fit", "ai_reasoning": "builds edge models"},
        {"human_status": "submitted", "title": "C2 Tool", "ai_verdict": "maybe", "human_notes": "", "ai_reasoning": "software C2  work\nmore"},
        {"human_status": "not_relevant", "title": "Hose", "ai_verdict": "yes", "human_notes": "[t U1] first\n[t U2] hardware-heavy, not us", "ai_reasoning": "x"},
        {"human_status": "dismissed", "title": "Boiler", "ai_verdict": "no", "human_notes": None, "ai_reasoning": "r"},
        {"human_status": None, "title": "ignored", "ai_reasoning": "r"},
    ]
    block = feedback.format_examples(rows)
    lines = block.strip().splitlines()
    assert lines[0] == feedback.HEADER and lines[-1] == feedback.FOOTER
    assert lines[1] == "- [PURSUE] Edge AI: builds edge models (team note: strong fit)"
    assert lines[2] == "- [PURSUE] C2 Tool: software C2 work more"
    assert lines[3] == "- [NOT RELEVANT] Hose: hardware-heavy, not us"
    assert lines[4] == "- [NOT RELEVANT] Boiler: r"
    assert block.endswith("---\n\n")


def example(status: str, verdict: str | None, notes: str | None = None) -> str:
    row = {"human_status": status, "title": "Call", "ai_verdict": verdict, "human_notes": notes, "ai_reasoning": "Claude's reasoning"}
    return feedback.format_examples([row]).strip().splitlines()[1]


def test_claudes_case_for_a_call_the_team_passed_on_is_not_shown_to_the_judges() -> None:
    """David, 6 Nov: it told the judges the call matched, under a label saying the team ruled it out."""
    assert example("not_relevant", "yes") == "- [NOT RELEVANT] Call"
    assert example("not_relevant", "maybe") == "- [NOT RELEVANT] Call"
    assert example("dismissed", "yes") == "- [NOT RELEVANT] Call"
    assert example("not_relevant", None) == "- [NOT RELEVANT] Call"


def test_claudes_case_against_a_call_the_team_pursued_is_not_shown_either() -> None:
    assert example("pursue", "no") == "- [PURSUE] Call"
    assert example("submitted", "no") == "- [PURSUE] Call"
    assert example("pursue", "no", "[t U1] the customer asked us to bid") == "- [PURSUE] Call: team note: the customer asked us to bid"


def test_a_note_on_a_pursued_call_follows_the_reasoning_and_does_not_read_as_the_reason() -> None:
    """David, 6 Nov: a pursued call's only reason read 'this one seems hardware heavy', a side remark on it."""
    assert example("pursue", "yes", "[t U1] Just to note, this one seems hardware heavy") == \
        "- [PURSUE] Call: Claude's reasoning (team note: Just to note, this one seems hardware heavy)"
    assert example("pursue", "maybe", "[t U1] first\n[t U2] the newest") == "- [PURSUE] Call: Claude's reasoning (team note: the newest)"


def test_a_note_on_a_call_the_team_passed_on_is_the_reason() -> None:
    assert example("not_relevant", "yes", "[t U1] Staffing or IT support") == "- [NOT RELEVANT] Call: Staffing or IT support"
    assert example("not_relevant", "no", "[t U1] Staffing or IT support") == "- [NOT RELEVANT] Call: Staffing or IT support"


def test_each_part_of_an_example_stays_short() -> None:
    row = {"human_status": "pursue", "title": "Call", "ai_verdict": "yes", "ai_reasoning": "r" * 500, "human_notes": "[t U1] " + "n" * 500}
    line = feedback.format_examples([row]).strip().splitlines()[1]
    assert line == f"- [PURSUE] Call: {'r' * feedback.MAX_WHY} (team note: {'n' * feedback.MAX_WHY})"


def test_block_is_empty_without_decisions(ledger_db: str) -> None:
    assert feedback.build_examples_block() == ""
    run = lq.start_run("Vulcan SOF")
    lq.upsert_call({"id": "vulcan-1", "portal": "Vulcan SOF", "title": "Edge AI"}, run)
    lq.set_review("vulcan-1", "yes", "fits well")
    lq.set_human("vulcan-1", "pursue", "U1")
    block = feedback.build_examples_block(limit=5)
    assert "- [PURSUE] Edge AI: fits well" in block
