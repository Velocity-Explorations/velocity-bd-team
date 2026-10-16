from __future__ import annotations

from ledger import queries as lq
from review import feedback


def test_format_examples_labels_and_why() -> None:
    rows = [
        {"human_status": "pursue", "title": "Edge AI", "human_notes": "[2026-10-16T10:00:00Z U1] strong fit", "ai_reasoning": "x"},
        {"human_status": "submitted", "title": "C2 Tool", "human_notes": "", "ai_reasoning": "software C2  work\nmore"},
        {"human_status": "not_relevant", "title": "Hose", "human_notes": "[t U1] first\n[t U2] hardware-heavy, not us", "ai_reasoning": "x"},
        {"human_status": "dismissed", "title": "Boiler", "human_notes": None, "ai_reasoning": "r"},
        {"human_status": None, "title": "ignored", "ai_reasoning": "r"},
    ]
    block = feedback.format_examples(rows)
    lines = block.strip().splitlines()
    assert lines[0] == feedback.HEADER and lines[-1] == feedback.FOOTER
    assert lines[1] == "- [PURSUE] Edge AI: strong fit"
    assert lines[2] == "- [PURSUE] C2 Tool: software C2 work more"
    assert lines[3] == "- [NOT RELEVANT] Hose: hardware-heavy, not us"
    assert lines[4] == "- [NOT RELEVANT] Boiler: r"
    assert block.endswith("---\n\n")


def test_block_is_empty_without_decisions(ledger_db: str) -> None:
    assert feedback.build_examples_block() == ""
    run = lq.start_run("Vulcan SOF")
    lq.upsert_call({"id": "vulcan-1", "portal": "Vulcan SOF", "title": "Edge AI"}, run)
    lq.set_review("vulcan-1", "yes", "fits well")
    lq.set_human("vulcan-1", "pursue", "U1")
    block = feedback.build_examples_block(limit=5)
    assert "- [PURSUE] Edge AI: fits well" in block
