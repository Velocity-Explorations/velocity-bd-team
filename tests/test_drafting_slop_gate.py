"""Each draft ends with a slop check (PRO-510): the skill's scanner, read into a ready or not-ready verdict."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from drafting import slop_gate


def report(band: str = "clean", placeholders: tuple[str, ...] = (), fired: dict[str, str] | None = None,
           hot: list[dict[str, Any]] | None = None, calibrated: bool = False) -> dict[str, Any]:
    """A report shaped like slop_scan.py --json output."""
    families = {name: {"label": label, "tier": "discourse", "fired": True} for name, label in (fired or {}).items()}
    families["triads"] = {"label": "lists of three", "tier": "surface", "fired": True}
    families["prop_open_item"] = {"label": "open placeholders", "tier": "proposal", "fired": bool(placeholders)}
    return {"band": band, "confidence": "full", "words": 2642, "thresholds": {"calibrated": calibrated},
            "families": families, "hot_paragraphs": hot or [],
            "findings": [{"family": "prop_open_item", "tier": "proposal", "line": n + 1, "match": m}
                         for n, m in enumerate(placeholders)]}


SAMPLE = report(placeholders=("[PERSON WRITES: the opening paragraph. Evaluators read dozens of proposals.]",
                              "[NEEDS INPUT: rates]", "[NEEDS INPUT: date]", "[NEEDS EVIDENCE: CAGE]", "[TBD]"),
                hot=[{"lines": [173, 180], "findings": 16, "families": ["open placeholders"]},
                     {"lines": [13, 13], "findings": 2, "families": ["open placeholders", "puffery"]}])


def test_open_placeholders_are_counted_by_kind_and_the_draft_is_not_ready() -> None:
    gate = slop_gate.summarize(SAMPLE)
    assert gate.placeholders == {"PERSON WRITES": 1, "NEEDS INPUT": 2, "NEEDS FACT": 0, "NEEDS EVIDENCE": 1, "other": 1}
    assert not gate.ready
    assert slop_gate.verdict(gate) == ("Not ready: 1 PERSON WRITES, 2 NEEDS INPUT, 1 NEEDS EVIDENCE, 1 other; "
                                       "band clean (provisional)")
    fact = slop_gate.summarize(report(placeholders=("[NEEDS FACT: the certification date]",)))
    assert fact.placeholders["NEEDS FACT"] == 1 and slop_gate.verdict(fact).startswith("Not ready: 1 NEEDS FACT;")


def test_a_draft_is_ready_with_nothing_open_and_a_clean_or_light_band() -> None:
    assert slop_gate.summarize(report(band="light")).ready
    assert slop_gate.verdict(slop_gate.summarize(report(band="light", calibrated=True))) == "Ready: band light"
    revise = slop_gate.summarize(report(band="revise", fired={"corrective": "corrective framing", "puffery": "puffery"}))
    assert not revise.ready and revise.families == ["corrective framing", "puffery"]
    assert slop_gate.verdict(revise) == "Not ready: band revise (provisional)"


def test_under_150_words_there_is_no_band_and_only_the_placeholders_decide() -> None:
    short = slop_gate.summarize(report(band="unscored", placeholders=("[NEEDS INPUT: rates]",)))
    assert not short.ready and slop_gate.verdict(short) == "Not ready: 1 NEEDS INPUT; no band"
    clean = slop_gate.summarize(report(band="unscored"))
    assert clean.ready and slop_gate.verdict(clean) == "Ready: no band"


def test_the_report_lists_what_to_fix_first() -> None:
    text = slop_gate.render_report(slop_gate.summarize(SAMPLE), Path("data") / "drafting" / "x" / "draft_final.md")
    assert text.startswith("# Slop check\n\nNot ready: 1 PERSON WRITES")
    assert "- 1 PERSON WRITES" in text and "- 2 NEEDS INPUT" in text
    assert "- Lines 173 to 180: open placeholders" in text and "- Line 13: open placeholders, puffery" in text
    assert "provisional" in text and "python -m drafting.cli check --draft" in text
    assert "lists of three" not in text   # surface habits are not the first thing to fix


def test_scan_file_runs_the_skills_scanner_with_the_proposal_profile(tmp_path: Path,
                                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    scanner = tmp_path / "slop_scan.py"
    scanner.write_text("", encoding="utf-8")
    seen: dict[str, Any] = {}

    def fake_run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.update(command=command, timeout=kwargs.get("timeout"))
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps([SAMPLE]), stderr="")

    monkeypatch.setattr(slop_gate.subprocess, "run", fake_run)
    got = slop_gate.scan_file(tmp_path / "draft.md", tmp_path / "solicitation.txt", scanner)
    assert got["band"] == "clean"
    assert seen["command"] == [sys.executable, str(scanner), str(tmp_path / "draft.md"), "--profile", "proposal",
                               "--json", "--solicitation", str(tmp_path / "solicitation.txt")]
    assert seen["timeout"] == slop_gate.SCAN_TIMEOUT_S


def test_a_missing_scanner_says_how_to_point_at_it(tmp_path: Path) -> None:
    with pytest.raises(slop_gate.ScanError, match="AI_SLOP_SCAN"):
        slop_gate.scan_file(tmp_path / "draft.md", None, tmp_path / "missing.py")


def test_the_solicitation_text_is_the_listing_and_the_attachments() -> None:
    from tests.test_drafting_pipeline import inputs

    text = slop_gate.solicitation_text(inputs())
    assert text.startswith("LISTING TEXT") and "[sow.pdf]\nSOW TEXT" in text and "blank.png" not in text
