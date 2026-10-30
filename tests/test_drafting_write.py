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
           "framing the opening": "PLACE 1:\n- the customer's problem\n- our discriminator", "submission packet": PACKET,
           "final compliance re-check": "## 1. Keyword Verification\n- ❌ edge AI paraphrased\n- ⚠️ check CDIF"}


def review_reply(n: int) -> str:
    """A reviewer's evaluation: one change whose text is in the draft, one whose text is not; evaluators rate."""
    data = {"key_points": [f"Pass {n} found one fix"],
            "ratings": [{"criterion": "Technical merit", "rating": "Good", "strengths": "Clear", "weaknesses": "Thin evidence"}] if n < 3 else [],
            "changes": [{"section": "1. Approach", "now": f"Claim {n}.", "suggested": f"Claim {n}, with evidence.", "why": "Unsupported"},
                        {"section": "2. Team", "now": "Text that is not in the draft", "suggested": "x", "why": "y"}]}
    return f"# Review {n}\n\nThe evaluation.\n\n{FENCE}json\n{json.dumps(data)}\n{FENCE}"


def _reviews_step(pursuit_id: int) -> int:
    """A Reviews attempt the owner has decided, made directly in the ledger for the Final checks tests."""
    from ledger.db import now_iso, q, tx

    now = now_iso()
    with tx() as conn:
        cur = q(conn, "INSERT INTO pursuit_steps (pursuit_id, step, attempt, state, requested_by, queued_at, updated_at) "
                      "VALUES (?, 'reviews', 1, 'approved', 'David Wood', ?, ?) RETURNING id", (pursuit_id, now, now))
        return int(cur.fetchone()[0])


class Model:
    def __init__(self, fail: set[str] | None = None) -> None:
        self.asked: list[tuple[str, Prompt, int]] = []
        self.fail = fail or set()

    def __call__(self, prompt: Prompt, label: str, max_tokens: int) -> str:
        self.asked.append((label, prompt, max_tokens))
        if any(label.startswith(f) for f in self.fail):
            raise llm.PhaseError(f"{label}: the model refused this request")
        if label.startswith("review "):
            return review_reply(int(label.split()[1]))
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
    assert result.content["slop"] == "Not ready: 1 PERSON WRITES, 2 NEEDS INPUT, 1 NEEDS EVIDENCE; band clean (provisional)"
    assert lq.latest_slop_scan(ctx.pursuit["id"])["draft_name"] == "draft_v1.md"
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


def test_reviews_propose_changes_one_per_row_and_the_evaluators_rate_the_criteria(ledger_db: str, tmp_path: Path) -> None:
    model = Model()
    ctx = _context(tmp_path, model, "reviews", {**EARLIER, "draft_v2.md": "# Edge AI white paper\n\nClaim 1. Claim 2. Claim 3."})
    result = write.reviews(ctx)
    assert model.labels() == ["review 1 of 3: External evaluator", "review 2 of 3: Second independent evaluator",
                              "review 3 of 3: Velocity leadership"]
    rows = lq.step_changes(ctx.step["id"])
    assert [(r["reviewer"], r["section"], r["before_text"], r["after_text"], r["state"]) for r in rows] == [
        ("evaluator_1", "1. Approach", "Claim 1.", "Claim 1, with evidence.", "proposed"),
        ("evaluator_2", "1. Approach", "Claim 2.", "Claim 2, with evidence.", "proposed"),
        ("leadership", "1. Approach", "Claim 3.", "Claim 3, with evidence.", "proposed")]
    assert [(p["reviewer"], p["changes"], p["dropped"], len(p["ratings"])) for p in result.content["passes"]] == [
        ("External evaluator", 1, 1, 1), ("Second independent evaluator", 1, 1, 1), ("Velocity leadership", 1, 1, 0)]
    assert result.content["changes"] == 3 and result.content["question"] == write.QUESTIONS["reviews"]
    assert "Claim 1, with evidence." in model.prompt("review 2 of 3: Second independent evaluator").user
    assert "### Review 3: Internal Velocity leadership" in model.prompt("review 3 of 3: Velocity leadership").system
    assert not (ctx.work_dir / "draft_v3.md").exists()            # the draft changes once the owner has decided
    assert [f["name"] for f in result.files] == ["Review 1, External evaluator", "Review 2, Second independent evaluator",
                                                 "Review 3, Velocity leadership"]


def test_every_step_reads_the_whole_draft_and_a_rewrite_has_room_for_all_of_it(ledger_db: str, tmp_path: Path) -> None:
    """Compliance, Reviews, Final checks and the re-check read only a draft's first 50,000 or 60,000 characters,
    so a long draft lost its end; the rewrites now also have output room for the whole draft."""
    long_draft = "# Edge AI white paper\n\nClaim 1. " + "The approach is sound. " * 6_000 + "\n\n## 9. Glossary"

    class Long(Model):   # the formatting pass gives back the whole draft, so the re-check reads it too
        def __call__(self, prompt: Prompt, label: str, max_tokens: int) -> str:
            reply = super().__call__(prompt, label, max_tokens)
            return long_draft if label == "formatting document" else reply

    model = Long()
    ctx = _context(tmp_path, model, "compliance", {**EARLIER, "outline.md": "# Outline", "draft_v1.md": long_draft})
    write.compliance(ctx)
    (ctx.work_dir / "draft_v2.md").write_text(long_draft, encoding="utf-8")
    write.reviews(ctx)
    (ctx.work_dir / "draft_v3.md").write_text(long_draft, encoding="utf-8")
    write.final(ctx)
    readers = [(label, p, room) for label, p, room in model.asked
               if label.startswith(("compliance check", "review ", "building checklist", "formatting document", "final compliance"))]
    assert len(readers) == 7 and all("## 9. Glossary" in p.user for _, p, _ in readers)
    assert all(room >= len(long_draft) // 2 for label, _, room in readers if label in ("compliance check", "formatting document"))


def test_a_review_cut_off_before_its_changes_fails_rather_than_proposing_none(ledger_db: str, tmp_path: Path) -> None:
    """The 29 Oct trial: every reviewer hit max_tokens inside its json, and the step said "0 changes proposed"."""
    class CutOff(Model):
        def __call__(self, prompt: Prompt, label: str, max_tokens: int) -> str:
            reply = super().__call__(prompt, label, max_tokens)
            if label.startswith("review 2"):
                return reply[:reply.index('"changes"')]
            if label.startswith("review 3"):
                return f"# Review 3\n\nNothing to change.\n\n{FENCE}json\n{json.dumps({'key_points': ['Ready'], 'changes': []})}\n{FENCE}"
            return reply

    ctx = _context(tmp_path, CutOff(), "reviews", {**EARLIER, "draft_v2.md": "# Draft\nClaim 1. Claim 2. Claim 3."})
    result = write.reviews(ctx)
    assert [(p["status"], p.get("changes"), p.get("error")) for p in result.content["passes"]] == [
        ("done", 1, None), ("failed", None, "its answer had no readable list of changes"), ("done", 0, None)]
    assert [r["reviewer"] for r in lq.step_changes(ctx.step["id"])] == ["evaluator_1"]
    assert result.summary.splitlines() == ["- External evaluator: 1 change proposed", "- Second independent evaluator: failed",
                                           "- Velocity leadership: 0 changes proposed"]


def test_a_failed_review_pass_lets_the_others_run(ledger_db: str, tmp_path: Path) -> None:
    ctx = _context(tmp_path, Model(fail={"review 2 of 3"}), "reviews", {**EARLIER, "draft_v2.md": "# Draft\nClaim 1. Claim 3."})
    result = write.reviews(ctx)
    assert [p["status"] for p in result.content["passes"]] == ["done", "failed", "done"]
    with pytest.raises(llm.PhaseError, match="every review pass failed"):
        write.reviews(steps.StepContext(**{**ctx.__dict__, "ask": Model(fail={"review "})}))


def test_final_checks_polish_hold_the_opening_fix_dashes_and_scan(ledger_db: str, tmp_path: Path) -> None:
    ctx = _context(tmp_path, Model(), "final", {**EARLIER, "outline.md": "# Outline", "draft_v3.md": "# Edge AI white paper v3"})
    result = write.final(ctx)
    final = (ctx.work_dir / "draft_final.md").read_text(encoding="utf-8")
    assert "[PERSON WRITES:" in final and steps.count_dashes(final) == 0
    assert (ctx.work_dir / "checklist.md").exists() and (ctx.work_dir / "slop_report.md").exists()
    assert result.content["verdict"] == "Not ready: 1 PERSON WRITES; band clean (provisional)"
    assert (result.content["ready"], result.content["dashes_fixed"], result.content["person_writes"]) == (False, 1, 1)
    assert [f["name"] for f in result.files] == ["Final version", "Submission readiness checklist", "AI slop check report",
                                                 "Final compliance re-check"]
    assert "written by AI" not in json.dumps(result.content)


def test_final_checks_apply_the_owners_decided_changes_first(ledger_db: str, tmp_path: Path) -> None:
    ctx = _context(tmp_path, Model(), "final", {**EARLIER, "outline.md": "# Outline",
                                                "draft_v2.md": "# Edge AI white paper\n\nWe will try. Old line. Keep this."})
    reviews_id = _reviews_step(ctx.pursuit["id"])
    ids = lq.add_step_changes(reviews_id, "evaluator_1", [
        {"section": "1", "before": "We will try.", "after": "We will deliver X.", "reason": "Vague"},
        {"section": "1", "before": "Old line.", "after": "New line.", "reason": "Dated"},
        {"section": "1", "before": "Keep this.", "after": "Drop this.", "reason": "Wrong"},
        {"section": "2", "before": "Not in the draft.", "after": "y", "reason": "z"}])
    lq.decide_change(ids[0], "David Wood", "accepted")
    lq.decide_change(ids[1], "David Wood", "edited", edited_text="Edited line.")
    lq.decide_change(ids[2], "David Wood", "rejected")
    lq.decide_change(ids[3], "David Wood", "accepted")
    result = write.final(ctx)
    assert (ctx.work_dir / "draft_v3.md").read_text(encoding="utf-8") == "# Edge AI white paper\n\nWe will deliver X. Edited line. Keep this.\n"
    assert (result.content["changes_applied"], result.content["changes_missed"]) == (2, 1)
    assert "2 changes applied in Draft v3; 1 no longer matched the draft" in result.summary


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
    assert len(asked) == 5
    for label, prompt in asked.items():
        assert write.PLACEHOLDER_RULE in prompt.user, label


def test_final_checks_report_seven_checks_in_words(ledger_db: str, tmp_path: Path) -> None:
    model = Model()
    ctx = _context(tmp_path, model, "final", {**EARLIER, "outline.md": "# Outline", "draft_v3.md": "# Edge AI white paper v3"},
                   target_dates={"submit_by": "2026-11-30"})
    lq.save_checklist(ctx.pursuit["id"], [
        {"part": "documents", "text": "White paper PDF", "done": True},
        {"part": "inputs", "text": "Bios", "owner": "Shaun Jones", "due_date": "2026-11-29", "done": False}], "requirements")
    result = write.final(ctx)
    assert [(c["check"], c["result"], c["ok"]) for c in result.content["checks"]] == [
        ("Formatting check", "done", True),
        ("Final compliance re-check", "1 to fix", False),
        ("Placeholder sweep", "1 left", False),
        ("AI slop check, final pass", "not ready", False),
        ("Submission package check", "not run", None),
        ("Checklist updated", "updated", True),
        ("Final version saved", "saved", True),
    ]
    detail = {c["check"]: c["detail"] for c in result.content["checks"]}
    assert detail["Final compliance re-check"] == "1 to fix, 1 to check; the report is final_compliance.md"
    assert detail["Placeholder sweep"] == "1 PERSON WRITES, for David Wood"
    assert detail["AI slop check, final pass"] == ("Not ready: 1 PERSON WRITES; band clean (provisional). "
                                                   "Dash check passed: no en or em dashes")
    assert detail["Submission package check"].startswith("Runs once Drive is set up")
    assert detail["Checklist updated"] == "1 of 3 done; every open item has an owner and a date"
    assert detail["Final version saved"] == "draft_final.md and its Word file; the numbered drafts are kept"
    final = (ctx.work_dir / "draft_final.md").read_text(encoding="utf-8").splitlines()
    line = next(n for n, text in enumerate(final, start=1) if "[PERSON WRITES" in text)
    [placeholder] = result.content["placeholders"]
    assert (placeholder["kind"], placeholder["line"], placeholder["section"]) == ("PERSON WRITES", line, "Edge AI white paper")
    assert placeholder["text"].startswith("[PERSON WRITES")
    # The re-check reads the final version, asks for its report only, and leaves the final version as it is.
    recheck = model.prompt("final compliance re-check")
    assert final[line - 1][:60] in recheck.user and "Give only the report" in recheck.user
    assert (ctx.work_dir / "final_compliance.md").read_text(encoding="utf-8").startswith("## 1. Keyword Verification")
    assert "Final compliance re-check" in [f["name"] for f in result.files]
    # What is left to fill joins the checklist for the owner, due by the internal submit-by date.
    assert [(i["part"], i["text"], i["owner"], i["due_date"]) for i in lq.checklist(ctx.pursuit["id"]) if i["origin"] == "final"] == [
        ("inputs", "Write the place marked PERSON WRITES in the final version, in your own words", "David Wood", "2026-11-30")]


def test_a_failed_compliance_re_check_says_so_and_the_other_checks_stand(ledger_db: str, tmp_path: Path) -> None:
    ctx = _context(tmp_path, Model(fail={"final compliance re-check"}), "final",
                   {**EARLIER, "outline.md": "# Outline", "draft_v3.md": "# Edge AI white paper v3"})
    result = write.final(ctx)
    recheck = next(c for c in result.content["checks"] if c["check"] == "Final compliance re-check")
    assert (recheck["result"], recheck["ok"]) == ("not run", None)
    assert recheck["detail"] == "did not run: final compliance re-check: the model refused this request"
    assert len(result.content["checks"]) == 7


def test_the_checklist_check_names_open_items_without_an_owner_or_a_date() -> None:
    def item(done: bool, owner: str | None = "David Wood", due: str | None = "2026-11-30") -> dict:
        return {"done": 1 if done else 0, "owner": owner, "due_date": due}

    assert write.checklist_check([]) == {"check": "Checklist updated", "ok": None, "result": "not run", "detail": "no checklist yet"}
    assert write.checklist_check([item(True), item(False)])["detail"] == "1 of 2 done; every open item has an owner and a date"
    missing = write.checklist_check([item(True, None, None), item(False, None), item(False, due=None), item(False)])
    assert (missing["ok"], missing["detail"]) == (False, "1 of 4 done; 2 open items have no owner or no date")
