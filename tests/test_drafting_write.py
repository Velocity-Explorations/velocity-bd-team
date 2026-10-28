"""The steps after Go (PW11 to PW14, PRO-578): Outline, First draft, Compliance check, Reviews, Final checks
and the Submit gate, each run with a stand-in model. The slop scanner is the stand-in in conftest.py."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from drafting import inputs, llm, steps, write
from drafting.prompts import Prompt
from ledger import queries as lq

FENCE = "`" * 3
EM, EN = chr(0x2014), chr(0x2013)
OUTLINE = f"""# Proposal outline

## 1. SUBMISSION FORMAT
10 pages, PDF.

{FENCE}json
{{"key_points": ["Three sections in 10 pages"], "page_limit": "10 pages",
  "sections": [{{"title": "1. Technical Approach", "criteria": ["Technical merit"], "share": "5 pages", "evidence": ["Cobra Gold 2026"]}},
               {{"title": "2. Past Performance", "criteria": [], "share": "3 pages", "evidence": []}},
               {{"title": ""}}],
  "unmapped_criteria": ["Cost realism"], "evidence": ["Cobra Gold 2026 after-action report"]}}
{FENCE}"""
DRAFT = (f"# Edge AI white paper\n\n[PERSON WRITES: the opening]\n\nVelocity built Echo C2 {EM} it runs offline. "
         f"Pages 3{EN}5 show it. [NEEDS INPUT: rates] [NEEDS INPUT: bios] [NEEDS EVIDENCE: latency]")
COMPLIANCE = "## 1. Keyword Verification\n- ❌ edge AI paraphrased\n- ⚠️ check CDIF\n---CORRECTED DRAFT---\n# Edge AI white paper v2"
FINAL = ("# Edge AI white paper\n\nVelocity proposes an edge AI decision aid for brigade staffs " + EM +
         " it runs on rugged laptops without a cloud link and explains each recommendation it makes.")
PACKET = f"""# Submission packet

Email the PDF to the contracting officer.

{FENCE}json
{{"key_points": ["One PDF by email"], "files": [{{"file": "White paper (PDF)", "slot": "email attachment"}}],
  "portal_steps": ["Email the PDF to the contracting officer"], "deadline": "2026-12-01, time not given"}}
{FENCE}"""
REPLIES = {"building outline": OUTLINE, "drafting response": DRAFT, "compliance check": COMPLIANCE,
           "building checklist": "# Checklist\n- [ ] rates", "formatting document": FINAL,
           "framing the opening": "PLACE 1:\n- the customer's problem\n- our discriminator", "submission packet": PACKET}


class Model:
    def __init__(self, fail: set[str] | None = None) -> None:
        self.asked: list[tuple[str, Prompt, int]] = []
        self.fail = fail or set()

    def __call__(self, prompt: Prompt, label: str, max_tokens: int) -> str:
        self.asked.append((label, prompt, max_tokens))
        if any(label.startswith(f) for f in self.fail):
            raise llm.PhaseError(f"{label}: the model refused this request")
        if label.startswith("review pass "):
            return f"# Edge AI white paper after pass {label[len('review pass '):][0]}"
        return REPLIES[label]

    def labels(self) -> list[str]:
        return [label for label, _, _ in self.asked]

    def prompt(self, label: str) -> Prompt:
        return next(p for asked, p, _ in self.asked if asked == label)


def _context(tmp_path: Path, model: Model, step: str, files: dict[str, str] | None = None,
             target_dates: dict[str, str] | None = None) -> steps.StepContext:
    run_id = lq.start_run("sam_gov")
    lq.upsert_call({"id": "sam-1", "portal": "SAM.gov", "title": "Edge AI for C2", "type": "Sources Sought",
                    "department": "DEPT OF THE ARMY", "due_date": "2026-12-01", "url": "https://sam.gov/opp/1",
                    "description": "The Army seeks edge AI."}, run_id)
    lq.set_human("sam-1", "pursue", "David Wood")
    pursuit_id = lq.start_pursuit("sam-1", "David Wood", format="White paper", direction="Lead with Echo C2",
                                  builds_on=[{"id": "d1", "name": "C2 prototype white paper"}])
    if target_dates:
        lq.set_target_dates(pursuit_id, target_dates)
    row = lq.claim_next_step()
    work_dir = tmp_path / f"pursuit-{pursuit_id}"
    work_dir.mkdir(parents=True)
    for name, text in (files or {}).items():
        (work_dir / name).write_text(text, encoding="utf-8")
    return steps.StepContext(pursuit=lq.get_pursuit(pursuit_id), step={**row, "step": step}, record=inputs.gather(pursuit_id),
                             work_dir=work_dir, ask=model, progress=lambda states: None, today=date(2026, 11, 28))


EARLIER = {"requirements.md": "# Requirements analysis\nKEYWORDS: edge AI", "alignment.md": "# Alignment\nStrong on C2",
           "opportunity_summary.md": "# Opportunity summary\nArmy edge AI"}


def test_dashes_are_replaced_in_words_ranges_and_lists() -> None:
    assert steps.fix_dashes(f"Echo C2 {EM} offline") == "Echo C2, offline"
    assert steps.fix_dashes(f"pages 3{EN}5 and 2026{EM}2027") == "pages 3 to 5 and 2026 to 2027"
    assert steps.fix_dashes(f"{EM} first item\n  {EN} second") == "- first item\n  - second"
    assert steps.count_dashes(f"a{EM}b{EN}c") == 2 and steps.count_dashes("plain - hyphen") == 0


def test_the_outline_follows_the_direction_and_lists_its_sections(ledger_db: str, tmp_path: Path) -> None:
    model = Model()
    ctx = _context(tmp_path, model, "outline", EARLIER)
    result = write.outline(ctx)
    saved = (ctx.work_dir / "outline.md").read_text(encoding="utf-8")
    assert saved.startswith("# Proposal outline") and "json" not in saved
    assert result.content["sections"] == [
        {"title": "1. Technical Approach", "criteria": ["Technical merit"], "share": "5 pages", "evidence": ["Cobra Gold 2026"]},
        {"title": "2. Past Performance", "criteria": [], "share": "3 pages", "evidence": []}]
    assert (result.content["page_limit"], result.content["unmapped_criteria"]) == ("10 pages", ["Cost realism"])
    assert result.content["direction"] == "Lead with Echo C2"
    system, user = model.prompt("building outline")
    assert "capture manager and proposal strategist" in system
    for expected in ("KEYWORDS: edge AI", "Strong on C2", "Lead with Echo C2", "C2 prototype white paper",
                     "## Phase 1: Research and evidence gathering", "## Phase 2: Document structure and outline"):
        assert expected in user, expected


def test_the_first_draft_follows_the_outline_and_counts_its_placeholders(ledger_db: str, tmp_path: Path) -> None:
    model = Model()
    ctx = _context(tmp_path, model, "draft", {**EARLIER, "outline.md": "# Proposal outline\n## 1. Technical Approach"})
    result = write.draft(ctx)
    saved = (ctx.work_dir / "draft_v1.md").read_text(encoding="utf-8")
    assert "Echo C2, it runs offline" in saved and "Pages 3 to 5" in saved and steps.count_dashes(saved) == 0
    assert result.content["placeholders"] == {"PERSON WRITES": 1, "NEEDS INPUT": 2, "NEEDS EVIDENCE": 1, "other": 0}
    assert result.summary.splitlines()[1] == "- Placeholders to fill: 1 PERSON WRITES, 2 NEEDS INPUT, 1 NEEDS EVIDENCE"
    system, user = model.prompt("drafting response")
    assert system.startswith("You are a proposal writer at Velocity Explorations")
    assert "## 1. Technical Approach" in user and "## Phase 3: Drafting" in user and "Lead with Echo C2" in user


def test_the_compliance_check_saves_its_report_and_the_next_draft(ledger_db: str, tmp_path: Path) -> None:
    ctx = _context(tmp_path, Model(), "compliance", {**EARLIER, "draft_v1.md": "# Edge AI white paper"})
    result = write.compliance(ctx)
    assert (ctx.work_dir / "compliance_report.md").read_text(encoding="utf-8").startswith("## 1. Keyword Verification")
    assert (ctx.work_dir / "draft_v2.md").read_text(encoding="utf-8").startswith("# Edge AI white paper v2")
    assert (result.content["corrections"], result.content["warnings"]) == (1, 1)
    assert [f["name"] for f in result.files] == ["Compliance report", "Draft v2"]


def test_the_compliance_check_needs_a_draft(ledger_db: str, tmp_path: Path) -> None:
    with pytest.raises(llm.PhaseError, match="no draft"):
        write.compliance(_context(tmp_path, Model(), "compliance", EARLIER))


def test_reviews_revise_the_draft_pass_by_pass_and_keep_it_when_one_fails(ledger_db: str, tmp_path: Path) -> None:
    model = Model(fail={"review pass 2/4"})
    ctx = _context(tmp_path, model, "reviews", {**EARLIER, "draft_v2.md": "# Edge AI white paper v2"})
    result = write.reviews(ctx)
    assert (ctx.work_dir / "draft_v3.md").read_text(encoding="utf-8").strip() == "# Edge AI white paper after pass 4"
    assert [p["status"] for p in result.content["passes"]] == ["revised", "failed", "revised", "revised"]
    assert len([label for label in model.labels() if label.startswith("review pass ")]) == 4
    with pytest.raises(llm.PhaseError, match="every review pass failed"):
        write.reviews(steps.StepContext(**{**ctx.__dict__, "ask": Model(fail={"review pass "})}))


def test_final_checks_polish_hold_the_opening_fix_dashes_and_scan(ledger_db: str, tmp_path: Path) -> None:
    ctx = _context(tmp_path, Model(), "final", {**EARLIER, "outline.md": "# Outline", "draft_v3.md": "# Edge AI white paper v3"})
    result = write.final(ctx)
    final = (ctx.work_dir / "draft_final.md").read_text(encoding="utf-8")
    assert "[PERSON WRITES:" in final and steps.count_dashes(final) == 0
    assert (ctx.work_dir / "checklist.md").exists() and (ctx.work_dir / "slop_report.md").exists()
    assert result.content["verdict"] == "Not ready: 1 PERSON WRITES; band clean (provisional)"
    assert (result.content["ready"], result.content["dashes_fixed"], result.content["person_writes"]) == (False, 1, 1)
    assert [f["name"] for f in result.files] == ["Final version", "Submission readiness checklist", "AI slop check report"]
    assert "written by AI" not in json.dumps(result.content)


def test_final_checks_need_a_draft(ledger_db: str, tmp_path: Path) -> None:
    with pytest.raises(llm.PhaseError, match="no draft"):
        write.final(_context(tmp_path, Model(), "final", EARLIER))


def test_the_submit_gate_says_what_is_not_yet_true_and_lists_the_files(ledger_db: str, tmp_path: Path) -> None:
    model = Model()
    final = "# Edge AI white paper\n\n[PERSON WRITES: the opening]\n\nBody."
    ctx = _context(tmp_path, model, "submit", {**EARLIER, "draft_final.md": final,
                                              "slop_scan.json": json.dumps({"band": "light", "findings": []})},
                   target_dates={"submit_by": "2026-11-27"})
    lq.save_checklist(ctx.pursuit["id"], [{"part": "documents", "text": "White paper PDF", "done": True},
                                          {"part": "inputs", "text": "Bios", "done": False}], "requirements")
    result = write.submit(ctx)
    checks = {c["check"]: (c["ok"], c["detail"]) for c in result.content["checks"]}
    assert checks["Checklist"] == (False, "1 item is still open")
    assert checks["Placeholders"] == (False, "Placeholders to fill: 1 PERSON WRITES")
    assert checks["AI slop check"] == (True, "Ready: band light (provisional)")
    assert checks["Dashes"] == (True, "none in the final version")
    assert checks["Internal submit-by date"] == (False, "2026-11-27 has passed")
    assert result.content["files"] == [{"file": "White paper (PDF)", "slot": "email attachment"}]
    assert result.content["call_page"] == "https://sam.gov/opp/1"
    assert (ctx.work_dir / "submission_packet.md").exists()
    assert "Body." in model.prompt("submission packet").user and "## Phase 6: Submission and archival" in model.prompt(
        "submission packet").system


@pytest.mark.parametrize("step", list(write.RUNNERS))
def test_no_prompt_carries_a_dash(ledger_db: str, tmp_path: Path, step: str) -> None:
    model = Model()
    files = {**EARLIER, "outline.md": "# Outline", "draft_v1.md": "# D1", "draft_v2.md": "# D2", "draft_v3.md": "# D3",
             "draft_final.md": "# Final", "slop_scan.json": json.dumps({"band": "clean", "findings": []})}
    write.RUNNERS[step](_context(tmp_path, model, step, files))
    for _, prompt, _ in model.asked:
        assert steps.count_dashes(prompt.system + prompt.user) == 0


def test_each_step_asks_the_question_its_part_of_the_skill_asks() -> None:
    skill = write.SKILL.read_text(encoding="utf-8")
    for step in ("outline", "draft", "compliance", "final"):
        assert write.QUESTIONS[step] in skill, step


def test_other_bracketed_notes_count_as_open_items_too() -> None:
    text = ("[PERSON WRITES: the opening] [NEEDS INPUT: rates] [CONFIRM the size standard] [UNVERIFIED] "
            "[REVIEW NEEDED: check the order] [DATE] [ADD one line]\n[INTERNAL PRE-SUBMISSION NOTE, delete this box\nbefore export.] "
            "[Insert the legend] [status. none verified] [x] [ ] [the notice](https://sam.gov/opp/1) [TBD](https://example.invalid)")
    counts = steps.placeholder_counts(text)
    assert counts == {"PERSON WRITES": 1, "NEEDS INPUT": 1, "NEEDS EVIDENCE": 0, "other": 6}
    assert steps.placeholder_line(counts) == "Placeholders to fill: 1 PERSON WRITES, 1 NEEDS INPUT, 6 other bracketed notes"
    assert steps.placeholder_line(steps.placeholder_counts("[DATE]")) == "Placeholders to fill: 1 other bracketed note"


def test_drafting_and_review_prompts_keep_open_items_in_the_three_counted_forms(ledger_db: str, tmp_path: Path) -> None:
    model = Model()
    ctx = _context(tmp_path, model, "draft", {**EARLIER, "outline.md": "# Outline", "draft_v1.md": "# D1", "draft_v2.md": "# D2"})
    write.draft(ctx)
    write.compliance(ctx)
    write.reviews(ctx)
    asked = {label: prompt for label, prompt, _ in model.asked}
    assert len(asked) == 6
    for label, prompt in asked.items():
        assert write.PLACEHOLDER_RULE in prompt.user, label
