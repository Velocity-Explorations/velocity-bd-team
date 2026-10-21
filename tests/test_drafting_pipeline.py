"""The ported drafting pipeline, run with a fake model (Writer Plan W0)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from drafting import llm, opening, pipeline
from drafting.phases import PHASES, phase

ALL_FILES = ["requirements.md", "alignment.md", "outline.md", "draft.md", "draft_review_pass1.md",
             "draft_review_pass2.md", "draft_review_pass3.md", "draft_review_pass4.md", "draft_v2.md",
             "compliance_report.md", "draft_v3.md", "checklist.md", "draft_final.md"]


def canned(label: str) -> str:
    if label == "analyzing requirements":
        return "# Requirements\nKEYWORDS: edge AI"
    if label == "assessing alignment":
        return "# Alignment\nStrong Fit"
    if label == "building outline":
        return "# Outline\n## 1. Technical Approach"
    if label == "drafting response":
        return "# Draft\n[NEEDS INPUT: rates]"
    if label.startswith("review pass "):
        return f"# Draft after pass {label[len('review pass '):][0]}"
    if label == "compliance check":
        return "## 1. Keyword Verification\n- ❌ edge AI\n---CORRECTED DRAFT---\n# Draft v3"
    if label == "building checklist":
        return "# Checklist\n- [ ] rates"
    if label == "formatting document":
        return "# Final Draft"
    if label == "framing the opening":
        return "PLACE 1:" + chr(10) + "- the customer's problem" + chr(10) + "- our discriminator"
    raise AssertionError(f"unexpected phase label {label}")


class FakeModel:
    def __init__(self, fail: set[str] | None = None, outputs: dict[str, str] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.fail = fail or set()
        self.outputs = outputs or {}

    def __call__(self, prompt: str, system: str = "", model: str | None = None, max_tokens: int = 8000,
                 timeout: float = 600, phase_label: str = "", **kwargs: Any) -> str:
        self.calls.append({"label": phase_label, "prompt": prompt, "system": system, "model": model,
                           "max_tokens": max_tokens})
        if any(phase_label.startswith(f) for f in self.fail):
            raise llm.PhaseError(f"{phase_label}: boom")
        return self.outputs.get(phase_label, canned(phase_label))

    def labels(self) -> list[str]:
        return [c["label"] for c in self.calls]


class RecordingHooks:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, str]] = []

    def phase_started(self, ph: Any) -> None:
        self.events.append(("start", ph.id, ""))

    def phase_finished(self, ph: Any, status: str, stats: dict[str, Any]) -> None:
        self.events.append(("finish", ph.id, status))

    def status(self, phase_id: str) -> str:
        return next(s for kind, pid, s in self.events if kind == "finish" and pid == phase_id)


def inputs(**overrides: Any) -> pipeline.DraftInputs:
    base: dict[str, Any] = dict(title="Edge AI Logistics", portal="SAM.gov", opp_type="BAA", agency="NAVSEA",
                                due_date="2026-12-01", url="https://example.invalid/call", description="Short.",
                                listing_text="LISTING TEXT with KEYWORDS: edge AI",
                                attachments=[{"name": "sow.pdf", "text": "SOW TEXT"}, {"name": "blank.png", "text": ""}],
                                past_experience="PAST WORK", company_context="COMPANY KB", team_notes="",
                                template={"name": "baa_response", "text": "# Volume I: Technical"})
    base.update(overrides)
    return pipeline.DraftInputs(**base)


def run(tmp_path: Path, model: FakeModel, **kwargs: Any) -> tuple[pipeline.DraftOutputs, RecordingHooks]:
    hooks = RecordingHooks()
    out = pipeline.run_pipeline(kwargs.pop("draft_inputs", inputs()), tmp_path, hooks, generate=model, **kwargs)
    return out, hooks


def test_phase_list_is_the_reference_order_plus_the_opening() -> None:
    assert [(p.id, p.name) for p in PHASES] == [
        ("1", "Listing"), ("2", "Attachments"), ("3", "Past experience"), ("4", "Requirements"),
        ("4.5", "Alignment"), ("5", "Outline"), ("6", "Draft"), ("6.5", "Review ×4"), ("6.75", "Compliance"),
        ("7", "Checklist"), ("7.5", "Polish"), ("7.6", "Opening"), ("8", "Deliver")]
    assert phase("6.5").name == "Review ×4"
    with pytest.raises(KeyError):
        phase("9")


def test_a_full_run_writes_every_file_and_reports_every_phase(tmp_path: Path) -> None:
    model = FakeModel()
    out, hooks = run(tmp_path, model)
    for name in ALL_FILES:
        assert (tmp_path / name).exists(), name
    assert out.final_draft == tmp_path / "draft_final.md"
    assert [pid for kind, pid, _ in hooks.events if kind == "start"] == [p.id for p in PHASES]
    assert all(status == "completed" for kind, _, status in hooks.events if kind == "finish")
    assert len(model.calls) == 11
    assert set(out.documents) == {"requirements", "alignment", "outline", "draft", "compliance", "checklist"}


@pytest.mark.parametrize("phase_id, label, filename, expected_in_prompt", [
    ("4", "analyzing requirements", "requirements.md", ["LISTING TEXT", "[sow.pdf]\nSOW TEXT", "- Type: BAA"]),
    ("4.5", "assessing alignment", "alignment.md", ["# Requirements"]),
    ("5", "building outline", "outline.md", ["# Volume I: Technical", "ALIGNMENT ASSESSMENT (use this"]),
    ("6", "drafting response", "draft.md", ["# Outline", "PAST WORK"]),
    ("6.75", "compliance check", "draft_v3.md", ["DRAFT TO CHECK:\n# Draft after pass 4"]),
    ("7", "building checklist", "checklist.md", ["DRAFT RESPONSE:\n# Draft v3"]),
    ("7.5", "formatting document", "draft_final.md", ["DOCUMENT TO FORMAT:\n# Draft v3"]),
])
def test_each_model_phase_sends_its_inputs_and_writes_its_file(tmp_path: Path, phase_id: str, label: str,
                                                               filename: str, expected_in_prompt: list[str]) -> None:
    model = FakeModel()
    run(tmp_path, model)
    call = next(c for c in model.calls if c["label"] == label)
    for text in expected_in_prompt:
        assert text in call["prompt"], text
    written = (tmp_path / filename).read_text(encoding="utf-8")
    assert written == ("# Draft v3" if filename == "draft_v3.md" else canned(label))
    assert "COMPANY KB" in call["system"] or label in ("building checklist", "formatting document")


def test_the_review_passes_chain_and_save_draft_v2(tmp_path: Path) -> None:
    model = FakeModel()
    run(tmp_path, model)
    reviews = [c for c in model.calls if c["label"].startswith("review pass")]
    assert [c["label"] for c in reviews] == ["review pass 1/4: External evaluator",
                                             "review pass 2/4: Second independent evaluator",
                                             "review pass 3/4: Velocity Explorations leadership review",
                                             "review pass 4/4: Critical capability verification"]
    assert "DRAFT TO REVISE:\n# Draft\n" in reviews[0]["prompt"]
    assert "DRAFT TO REVISE:\n# Draft after pass 1" in reviews[1]["prompt"]
    assert (tmp_path / "draft_v2.md").read_text(encoding="utf-8") == "# Draft after pass 4"


def test_compliance_splits_the_report_from_the_corrected_draft(tmp_path: Path) -> None:
    out, _ = run(tmp_path, FakeModel())
    assert (tmp_path / "compliance_report.md").read_text(encoding="utf-8") == "## 1. Keyword Verification\n- ❌ edge AI"
    assert out.phases["6.75"]["open_items"] == 1


def test_compliance_without_a_separator_is_all_draft(tmp_path: Path) -> None:
    run(tmp_path, FakeModel(outputs={"compliance check": "# Whole thing"}))
    assert not (tmp_path / "compliance_report.md").exists()
    assert (tmp_path / "draft_v3.md").read_text(encoding="utf-8") == "# Whole thing"


def test_a_failed_review_pass_keeps_the_previous_draft(tmp_path: Path) -> None:
    model = FakeModel(fail={"review pass 2/4"})
    _, hooks = run(tmp_path, model)
    assert not (tmp_path / "draft_review_pass2.md").exists()
    pass3 = next(c for c in model.calls if c["label"].startswith("review pass 3/4"))
    assert "DRAFT TO REVISE:\n# Draft after pass 1" in pass3["prompt"]
    assert hooks.status("6.5") == "completed"


@pytest.mark.parametrize("fail, expected_final", [
    ({"formatting document"}, "draft_v3.md"),
    ({"formatting document", "compliance check"}, "draft_v2.md"),
])
def test_the_fallback_chain_picks_the_best_draft(tmp_path: Path, fail: set[str], expected_final: str) -> None:
    out, hooks = run(tmp_path, FakeModel(fail=fail))
    assert out.final_draft == tmp_path / expected_final
    assert hooks.status("7.5") == "failed" and hooks.status("8") == "completed"


def test_a_failed_draft_phase_leaves_nothing_to_review(tmp_path: Path) -> None:
    model = FakeModel(fail={"drafting response"})
    out, hooks = run(tmp_path, model)
    assert hooks.status("6") == "failed" and hooks.status("6.5") == "skipped"
    assert not any(c["label"].startswith("review pass") for c in model.calls)
    assert out.final_draft is None


def test_requirements_are_skipped_with_no_source_text(tmp_path: Path) -> None:
    model = FakeModel()
    _, hooks = run(tmp_path, model, draft_inputs=inputs(listing_text="", description="", attachments=[]))
    assert hooks.status("4") == "skipped" and "analyzing requirements" not in model.labels()


def test_from_phase_reuses_the_saved_files(tmp_path: Path) -> None:
    run(tmp_path, FakeModel())
    model = FakeModel()
    _, hooks = run(tmp_path, model, from_phase="6.5", to_phase="6.5")
    assert model.labels() == [f"review pass {n}/4: {label}" for n, label in enumerate(
        ["External evaluator", "Second independent evaluator", "Velocity Explorations leadership review",
         "Critical capability verification"], 1)]
    assert "# Draft\n[NEEDS INPUT: rates]" in model.calls[0]["prompt"]
    assert hooks.status("6") == "loaded" and hooks.status("7") == "not run"


def test_a_cancel_stops_the_whole_run(tmp_path: Path) -> None:
    class Cancelling(FakeModel):
        def __call__(self, prompt: str, system: str = "", **kwargs: Any) -> str:
            if kwargs.get("phase_label") == "building outline":
                raise llm.DraftCancelled("cancelled")
            return super().__call__(prompt, system, **kwargs)

    with pytest.raises(llm.DraftCancelled):
        run(tmp_path, Cancelling())
    assert not (tmp_path / "outline.md").exists()


def test_inputs_round_trip_through_json(tmp_path: Path) -> None:
    original = inputs()
    path = tmp_path / "inputs.json"
    original.save(path)
    assert pipeline.DraftInputs.load(path) == original


# ------------------------------------------------------------------ the opening (PRO-494)

PROSE_FINAL = ("# Edge AI Logistics\n\n## 1. Executive Summary\n\nVelocity proposes Echo C2 for NAVSEA sustainment. "
               "It fuses four data systems in the field. It ships in six months.\n\n## 2. Approach\n\nDetails here.")


def test_the_opening_is_left_for_a_person_with_points_to_land(tmp_path: Path) -> None:
    model = FakeModel(outputs={"formatting document": PROSE_FINAL,
                               "framing the opening": "PLACE 1:\n- NAVSEA's data is split\n- Echo C2 already fuses it"})
    out, hooks = run(tmp_path, model)
    final = (tmp_path / "draft_final.md").read_text(encoding="utf-8")
    assert "[PERSON WRITES: the opening paragraph and the first three sentences of the executive summary." in final
    assert "> - NAVSEA's data is split" in final and "Velocity proposes Echo C2" not in final
    assert final.endswith("## 2. Approach\n\nDetails here.")
    assert out.phases["7.6"]["person_writes"] == 1 and hooks.status("7.6") == "completed"
    assert "PERSON WRITES" in (tmp_path / "checklist.md").read_text(encoding="utf-8")
    call = next(c for c in model.calls if c["label"] == "framing the opening")
    assert "Edge AI Logistics" in call["prompt"] and "# Requirements" in call["prompt"]


def test_a_failed_framing_call_still_holds_the_opening(tmp_path: Path) -> None:
    model = FakeModel(fail={"framing the opening"}, outputs={"formatting document": PROSE_FINAL})
    out, hooks = run(tmp_path, model)
    final = (tmp_path / "draft_final.md").read_text(encoding="utf-8")
    assert "[PERSON WRITES:" in final and "Velocity proposes Echo C2" not in final
    assert opening.GENERIC_POINTS[0] in final
    assert hooks.status("7.6") == "completed" and "generic" in out.phases["7.6"]["note"]


def test_running_the_opening_again_changes_nothing(tmp_path: Path) -> None:
    model = FakeModel(outputs={"formatting document": PROSE_FINAL, "framing the opening": "PLACE 1:\n- a point"})
    run(tmp_path, model)
    first = (tmp_path / "draft_final.md").read_text(encoding="utf-8")
    again = FakeModel()
    out, _ = run(tmp_path, again, from_phase="7.6")
    assert (tmp_path / "draft_final.md").read_text(encoding="utf-8") == first
    assert again.labels() == [] and out.phases["7.6"]["person_writes"] == 1
