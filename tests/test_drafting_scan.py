"""The AI slop check on every new draft (PW12, PW20 to PW23): the worker's own fixes, then the scan, kept in
`slop_scans`. The scanner is the stand-in in conftest.py, which reports each open placeholder."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from drafting import scan, slop_gate
from ledger import queries as lq

EM = chr(0x2014)


def _pursuit() -> tuple[int, int]:
    run_id = lq.start_run("sam_gov")
    lq.upsert_call({"id": "sam-1", "portal": "SAM.gov", "title": "Edge AI", "due_date": "2026-12-01"}, run_id)
    pursuit_id = lq.start_pursuit("sam-1", "David Wood")
    return pursuit_id, lq.claim_next_step()["id"]


def test_the_worker_fixes_dashes_and_tracking_parameters_on_its_own() -> None:
    text = (f"Echo C2 runs offline {EM} on laptops. See https://example.invalid/a?utm_source=li&id=3&fbclid=x9 "
            "and https://example.invalid/b?gclid=1.")
    fixed, count = scan.fix_text(text)
    assert fixed == "Echo C2 runs offline, on laptops. See https://example.invalid/a?id=3 and https://example.invalid/b."
    assert count == 4                                          # one dash, three tracking parameters
    assert scan.fix_text("Nothing to fix here.") == ("Nothing to fix here.", 0)


def test_a_new_draft_is_fixed_then_scanned_and_kept(ledger_db: str, tmp_path: Path) -> None:
    pursuit_id, step_id = _pursuit()
    draft = tmp_path / "draft_v1.md"
    draft.write_text(f"# White paper\n\nEcho C2 runs offline {EM} on laptops. [NEEDS INPUT: rates]\n" + "More words. " * 100,
                     encoding="utf-8")
    found = scan.check(pursuit_id, step_id, draft, "The Army seeks edge AI.")
    assert EM not in draft.read_text(encoding="utf-8")
    assert (found["verdict"], found["ready"], found["fixed"]) == ("Not ready: 1 NEEDS INPUT; band clean (provisional)", False, 1)
    row = lq.latest_slop_scan(pursuit_id)
    assert (row["id"], row["step_id"], row["draft_name"], row["fixed_count"], row["ready"]) == (found["scan_id"], step_id, "draft_v1.md", 1, 0)
    assert row["text_lines"] == draft.read_text(encoding="utf-8")
    assert json.loads((tmp_path / "slop_scan.json").read_text(encoding="utf-8"))["band"] == "clean"
    assert (tmp_path / "slop_report.md").exists()
    assert (tmp_path / "source" / "solicitation.txt").read_text(encoding="utf-8") == "The Army seeks edge AI."


def test_without_the_scanner_the_check_says_so_and_keeps_nothing(ledger_db: str, tmp_path: Path,
                                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    pursuit_id, step_id = _pursuit()
    draft = tmp_path / "draft_v1.md"
    draft.write_text("# White paper\n\nShort.", encoding="utf-8")

    def missing(*_: object, **__: object) -> dict:
        raise slop_gate.ScanError("slop scanner not found; install the ai-slop-detection skill or set AI_SLOP_SCAN")

    monkeypatch.setattr(slop_gate, "run_scan", missing)
    found = scan.check(pursuit_id, step_id, draft, "")
    assert found["verdict"] == "Not checked: slop scanner not found; install the ai-slop-detection skill or set AI_SLOP_SCAN"
    assert (found["scan_id"], found["ready"]) == (None, False)
    assert lq.latest_slop_scan(pursuit_id) is None


def test_nothing_the_check_says_speaks_of_ai_authorship() -> None:
    banned = ("written by ai", "ai-generated", "ai generated", "probability", "likely ai", "human-written", "detector")
    for path in (Path(scan.__file__), Path(slop_gate.__file__)):
        text = path.read_text(encoding="utf-8").lower()
        assert not [word for word in banned if word in text], path.name
