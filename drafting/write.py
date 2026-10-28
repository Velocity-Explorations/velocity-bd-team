"""The steps after Go (PW11 to PW14, PRO-578): Outline, First draft, Compliance check, Reviews, Final checks
and the Submit gate, from Velocity's proposal-drafting workflow (drafting/skills/proposal_drafting.md) and
the reference pipeline's prompts, whose words stay unchanged (drafting/prompts.py).

    RUNNERS["outline"](ctx) -> StepResult

Outline, First draft, Compliance check and the review passes send the reference prompt with a workspace
block after it: the owner's direction and chosen past work, the skill's part for the step, the no-dash
rule, and on a redo the owner's note. Reviews runs the reference pipeline's four review passes until
phase 8 brings the reviewers' changes the owner decides one by one (PW12). Final checks runs the
reference's last phases: the readiness checklist, the formatting pass, the opening held for a person to
write (PRO-494) and the AI slop check (PRO-510), with the dashes replaced before the scan. The Submit
gate checks what the skill asks before the owner submits and writes the packet: each file's portal slot
and the portal's steps (PW14). The owner submits on the portal, then chooses Mark submitted.

Drafts are numbered in the pursuit's folder: draft_v1 (First draft), draft_v2 (Compliance check),
draft_v3 (Reviews) and draft_final (Final checks).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from drafting import llm, pipeline, prompts, slop_gate
from drafting.company import profile
from drafting.inputs import builds_on_text, draft_inputs
from drafting.phases import Phase
from drafting.prompts import Prompt
from drafting.steps import (StepContext, StepResult, bullets, count_dashes, fix_dashes, latest_draft, placeholder_counts,
                            placeholder_line, points, skill_part, split_reply, strings, system_prompt, user_prompt)
from ledger import queries as lq

SKILL = Path(__file__).resolve().parent / "skills" / "proposal_drafting.md"
QUESTIONS = {
    "outline": "Here is the proposed structure, page budget and the evidence it draws on. Does this look right? "
               "Any sections you want weighted differently, or evidence to add or drop?",
    "draft": "Here is the first complete draft. What are your first reactions before the compliance check and the reviews?",
    "compliance": "Here is what the compliance check found and fixed. Approve the fixes and move into the reviews?",
    "reviews": "Here is the draft after four review passes. Approve it for the final checks, or ask for changes.",
    "final": "The final version is saved. Here is the updated checklist, with what is complete and what is still open, "
             "and who owns each item. Tick what people have done, then go to the Submit gate.",
    "submit": "Submit on the portal, then enter the confirmation number and the result expected by date, and choose "
              "Mark submitted.",
}
CORRECTION, WARNING = "❌", "⚠️"   # the reference compliance report's marks for items fixed and items to check
PLACEHOLDER_RULE = ("Keep every open item a person must close in one of three forms: [PERSON WRITES: ...] for text a person "
                    "must write in their own words, [NEEDS INPUT: ...] for facts, files or figures that must come from people, "
                    "and [NEEDS EVIDENCE: ...] for a claim that needs a source. Do not write other bracketed notes such as "
                    "[CONFIRM ...], [UNVERIFIED] or [REVIEW NEEDED: ...], and keep notes to the team out of the document: "
                    "the gates count only these three forms.")
PACKET_TOKENS = 6_000
OUTLINE_SPEC = """{"key_points": ["three to six short points for the step's card"],
 "page_limit": "the page limit, in words, or null when the call sets none",
 "sections": [{"title": "the section's number and title", "criteria": ["each evaluation criterion it answers"],
               "share": "its share of the page limit, for example 4 pages, about 1,800 words",
               "evidence": ["the past work and evidence it draws on"]}],
 "unmapped_criteria": ["each evaluation criterion with no natural home"],
 "evidence": ["the past work and evidence the proposal draws on, for the owner to add to or drop"]}"""
PACKET_SPEC = """{"key_points": ["three to six short points for the step's card"],
 "files": [{"file": "each file to submit", "slot": "the portal slot it goes into, or how it is sent"}],
 "portal_steps": ["each step on the portal, in order"],
 "deadline": "the deadline with its time and time zone, as the call gives it"}"""


def _skill(heading: str) -> str:
    return skill_part(SKILL, heading)


def _workspace(ctx: StepContext, instructions: str = "", spec: str = "", direction: bool = True,
               placeholders: bool = False) -> str:
    """What goes after a reference prompt in the workspace: the owner's direction and chosen past work, the
    skill's part for the step, the placeholder and no-dash rules, the json block to add, and on a redo the
    owner's note."""
    lines = ["", "", "---", "", "FOR THE PROPOSAL WORKSPACE"]
    if direction:
        lines += ["", "The owner's direction, which the proposal follows:",
                  (ctx.pursuit.get("direction") or "").strip() or "(none given)",
                  "", "Past work the owner chose to build on:", builds_on_text(ctx.record)]
    if instructions:
        lines += ["", "Also follow these steps from Velocity's proposal-drafting workflow:", "", instructions]
    if placeholders:
        lines += ["", PLACEHOLDER_RULE]
    lines += ["", "Never use an em dash or an en dash."]
    if spec:
        lines += ["After the document, add one fenced json block with these fields, and nothing after it:", spec]
    return "\n".join(lines) + ctx.redo_block()


def _draft(ctx: StepContext, label: str) -> tuple[Path, str]:
    path = latest_draft(ctx.work_dir)
    if path is None:
        raise llm.PhaseError(f"{label}: there is no draft yet; run the First draft step first")
    return path, path.read_text(encoding="utf-8")


def _alignment(ctx: StepContext) -> str:
    alignment = ctx.earlier("alignment.md")
    return prompts.ALIGNMENT_BLOCK_HEADER + alignment[:15_000] if alignment else ""


# ------------------------------------------------------------------------- Plan and Draft

def _sections(found: Any) -> list[dict[str, Any]]:
    sections = []
    for item in found if isinstance(found, list) else []:
        if isinstance(item, dict) and str(item.get("title") or "").strip():
            sections.append({"title": str(item["title"]).strip(), "criteria": strings(item.get("criteria")),
                             "share": str(item.get("share") or "").strip() or None, "evidence": strings(item.get("evidence"))})
    return sections


def outline(ctx: StepContext) -> StepResult:
    """Step 5 (PW11): the reference outline and compliance plan, with the sections, the criterion each answers,
    its share of the page limit and the evidence it draws on. Approving it locks the direction."""
    d = draft_inputs(ctx.record)
    p = prompts.p5_outline(company=profile(), knowledge_base=d.company_context, rag_context=d.past_experience[:20_000],
                           title=d.title, agency=d.agency, portal=d.portal, opp_type=d.opp_type, due_date=d.due_date,
                           requirements=ctx.earlier("requirements.md"), template=d.template.get("text") or prompts.DEFAULT_SECTIONS,
                           alignment=ctx.earlier("alignment.md", 20_000))
    instructions = _skill("## Phase 1:") + "\n\n" + _skill("## Phase 2:")
    reply = ctx.ask(Prompt(p.system, p.user + _workspace(ctx, instructions, OUTLINE_SPEC)), "building outline",
                    pipeline.MAX_TOKENS["5"])
    document, data = split_reply(reply)
    saved = ctx.save("outline.md", document or reply, "Outline")
    return StepResult(summary=points(data, document), files=[saved],
                      content={"document": document, "sections": _sections(data.get("sections")),
                               "page_limit": str(data.get("page_limit") or "").strip() or None,
                               "unmapped_criteria": strings(data.get("unmapped_criteria")), "evidence": strings(data.get("evidence")),
                               "direction": (ctx.pursuit.get("direction") or "").strip() or None, "question": QUESTIONS["outline"]})


def draft(ctx: StepContext) -> StepResult:
    """Step 6: the reference drafting prompt, section by section from the outline, with the skill's drafting
    principles; the card counts the placeholders a person must fill."""
    d = draft_inputs(ctx.record)
    p = prompts.p6_draft(company=profile(), knowledge_base=d.company_context, rag_context=d.past_experience[:30_000],
                         title=d.title, agency=d.agency, portal=d.portal, opp_type=d.opp_type, due_date=d.due_date,
                         requirements=ctx.earlier("requirements.md"),
                         outline=ctx.earlier("outline.md") or d.template.get("text") or prompts.DEFAULT_SECTIONS,
                         alignment=ctx.earlier("alignment.md", 20_000))
    text = ctx.ask(Prompt(p.system, p.user + _workspace(ctx, _skill("## Phase 3:"), placeholders=True)), "drafting response",
                   pipeline.MAX_TOKENS["6"])
    saved = ctx.save("draft_v1.md", text, "Draft v1")
    document = fix_dashes(text)
    counts, words = placeholder_counts(document), len(document.split())
    return StepResult(summary=bullets([f"{words:,} words", placeholder_line(counts)]), files=[saved],
                      content={"document": document, "words": words, "placeholders": counts, "question": QUESTIONS["draft"]})


# ---------------------------------------------------------------------------------- Review

def compliance(ctx: StepContext) -> StepResult:
    """Step 7: the reference's mechanical check against the requirements' terminology section; its report, and
    the corrected draft as Draft v2."""
    path, current = _draft(ctx, "Compliance check")
    d = draft_inputs(ctx.record)
    p = prompts.p675_compliance(company=profile(), knowledge_base=d.company_context, alignment_context=_alignment(ctx),
                                title=d.title, agency=d.agency, opp_type=d.opp_type, due_date=d.due_date,
                                requirements=ctx.earlier("requirements.md", 25_000), draft=current[:50_000])
    reply = ctx.ask(Prompt(p.system, p.user + _workspace(ctx, direction=False, placeholders=True)), "compliance check",
                    pipeline.MAX_TOKENS["6.75"])
    report, corrected = reply.split(prompts.CORRECTED_DRAFT_SEPARATOR, 1) if prompts.CORRECTED_DRAFT_SEPARATOR in reply else ("", reply)
    files = [ctx.save("compliance_report.md", report.strip(), "Compliance report")] if report.strip() else []
    files.append(ctx.save("draft_v2.md", corrected.strip() or current, "Draft v2"))
    corrections, warnings = report.count(CORRECTION), report.count(WARNING)
    lines = [f"{corrections} {'item' if corrections == 1 else 'items'} corrected in Draft v2",
             f"{warnings} {'warning' if warnings == 1 else 'warnings'} to check"]
    if not report.strip():
        lines = ["The check gave no report; its corrected text is Draft v2"]
    return StepResult(summary=bullets(lines), files=files,
                      content={"document": fix_dashes(report.strip()), "corrections": corrections, "warnings": warnings,
                               "question": QUESTIONS["compliance"]})


def reviews(ctx: StepContext) -> StepResult:
    """Step 8, until phase 8: the reference pipeline's four review passes, each revising the draft the one before
    left, as Draft v3. A pass that fails keeps the draft and the next pass goes on."""
    _, current = _draft(ctx, "Reviews")
    d, company = draft_inputs(ctx.record), profile()
    passes: list[dict[str, Any]] = []
    for n in range(1, len(prompts.REVIEW_PASSES) + 1):
        reviewer = prompts.review_pass_label(n, company)
        p = prompts.p65_review_pass(n, company=company, knowledge_base=d.company_context, rag_context=d.past_experience[:20_000],
                                    title=d.title, agency=d.agency, opp_type=d.opp_type, due_date=d.due_date,
                                    requirements=ctx.earlier("requirements.md", 20_000), alignment_block=_alignment(ctx),
                                    draft=current[:50_000])
        try:
            revised = ctx.ask(Prompt(p.system, p.user + _workspace(ctx, direction=False, placeholders=True)),
                              f"review pass {n}/{len(prompts.REVIEW_PASSES)}: {reviewer}", pipeline.MAX_TOKENS["6.5"])
        except llm.PhaseError as exc:
            passes.append({"pass": n, "reviewer": reviewer, "status": "failed", "error": str(exc)[:300]})
            continue
        passes.append({"pass": n, "reviewer": reviewer, "status": "revised",
                       "words_delta": len(revised.split()) - len(current.split())})
        current = revised
    if not any(p["status"] == "revised" for p in passes):
        raise llm.PhaseError("Reviews: every review pass failed")
    saved = ctx.save("draft_v3.md", current, "Draft v3")
    lines = [f"Pass {p['pass']}, {p['reviewer']}: " + ("revised" if p["status"] == "revised" else "failed, draft kept") for p in passes]
    return StepResult(summary=bullets(lines), files=[saved],
                      content={"document": fix_dashes(current), "passes": passes, "question": QUESTIONS["reviews"]})


# ------------------------------------------------------------------------------- Finalize

class _Quiet:
    """Hooks for the reference phases: the worker reports progress itself."""

    def phase_started(self, phase: Phase) -> None:
        pass

    def phase_finished(self, phase: Phase, status: str, stats: dict[str, Any]) -> None:
        pass


def _pipeline_state(ctx: StepContext, current: str) -> pipeline.State:
    """The reference pipeline's state for its last phases, asking the model through the worker's meter."""

    def generate(prompt: str, system: str = "", model: str | None = None, max_tokens: int = 8000, timeout: float = 600,
                 phase_label: str = "", **_: Any) -> str:
        return ctx.ask(Prompt(system, prompt), phase_label, max_tokens)

    state = pipeline.State(run=pipeline.RunContext(generate=generate, model=None, company=profile(), abort=None))
    state.requirements, state.alignment = ctx.earlier("requirements.md"), ctx.earlier("alignment.md")
    state.outline, state.draft = ctx.earlier("outline.md"), current
    return state


def _undash(path: Path) -> int:
    """Replace the dashes in a saved file; how many there were."""
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8")
    found = count_dashes(text)
    if found:
        path.write_text(fix_dashes(text), encoding="utf-8")
    return found


def final(ctx: StepContext) -> StepResult:
    """Step 9: the readiness checklist, the formatting pass, the opening held for a person to write, the dashes
    replaced, then the AI slop check's verdict on the final version (PW13 lists the checks the page adds)."""
    _, current = _draft(ctx, "Final checks")
    d, hooks = draft_inputs(ctx.record), _Quiet()
    state = _pipeline_state(ctx, current)
    state.stats = {}
    pipeline.phase_7_checklist(d, state, ctx.work_dir, hooks)
    state.stats = {}
    pipeline.phase_75_polish(d, state, ctx.work_dir, hooks)
    final_path = ctx.work_dir / "draft_final.md"
    dashes = _undash(final_path)
    state.draft = final_path.read_text(encoding="utf-8")
    state.stats = {}
    pipeline.phase_76_opening(d, state, ctx.work_dir, hooks)
    person_writes = int(state.stats.get("person_writes") or 0)
    dashes += _undash(final_path)
    _undash(ctx.work_dir / "checklist.md")
    state.stats = {}
    pipeline.phase_77_slop(d, state, ctx.work_dir, hooks)
    scan = dict(state.stats)
    note = str(scan.get("note") or "the scanner did not run").removeprefix("Slop check: ")
    verdict = str(scan.get("verdict") or f"Not checked: {note}")
    document = final_path.read_text(encoding="utf-8")
    files = [ctx.entry("draft_final.md", "Final version"), ctx.entry("checklist.md", "Submission readiness checklist")]
    if (ctx.work_dir / "slop_report.md").exists():
        files.append(ctx.entry("slop_report.md", "AI slop check report"))
    lines = [f"AI slop check: {verdict}", placeholder_line(placeholder_counts(document))]
    if dashes:
        lines.append(f"{dashes} {'dash' if dashes == 1 else 'dashes'} replaced")
    return StepResult(summary=bullets(lines), files=files,
                      content={"document": document, "verdict": verdict, "ready": bool(scan.get("ready")),
                               "band": scan.get("band"), "open_placeholders": scan.get("open_placeholders"),
                               "person_writes": person_writes, "dashes_fixed": dashes, "question": QUESTIONS["final"]})


# --------------------------------------------------------------------------------- Submit

def _check(name: str, ok: bool | None, detail: str) -> dict[str, Any]:
    return {"check": name, "ok": ok, "detail": detail}


def _gate_checks(ctx: StepContext, final_text: str) -> list[dict[str, Any]]:
    """What the skill confirms before the owner submits, each passing, failing, or not known yet."""
    items = lq.checklist(ctx.pursuit["id"])
    still_open = sum(1 for item in items if not item["done"])
    checklist = (_check("Checklist", None, "no checklist yet") if not items
                 else _check("Checklist", still_open == 0, "every item is ticked" if still_open == 0
                             else f"{still_open} {'item is' if still_open == 1 else 'items are'} still open"))
    counts = placeholder_counts(final_text)
    scan_path = ctx.work_dir / "slop_scan.json"
    if scan_path.exists():
        gate = slop_gate.summarize(json.loads(scan_path.read_text(encoding="utf-8")))
        slop = _check("AI slop check", gate.ready, slop_gate.verdict(gate))
    else:
        slop = _check("AI slop check", None, "not run")
    dashes = count_dashes(final_text)
    try:
        submit_by = json.loads(ctx.pursuit.get("target_dates") or "{}").get("submit_by")
    except ValueError:
        submit_by = None
    if submit_by:
        passed = ctx.today.isoformat() > submit_by
        deadline = _check("Internal submit-by date", not passed, f"{submit_by} has passed" if passed else f"by {submit_by}")
    else:
        deadline = _check("Internal submit-by date", None, "not set")
    return [checklist, _check("Placeholders", not any(counts.values()), placeholder_line(counts)), slop,
            _check("Dashes", dashes == 0, "none in the final version" if dashes == 0 else f"{dashes} in the final version"),
            deadline]


def submit(ctx: StepContext) -> StepResult:
    """The Submit gate (PW14): the gate's checks, and the packet the owner submits from: each file's portal slot,
    the portal's steps and the deadline. The owner submits on the portal, never the worker."""
    path = ctx.work_dir / "draft_final.md"
    if not path.exists():
        raise llm.PhaseError("Submit gate: there is no final version yet; run Final checks first")
    final_text = path.read_text(encoding="utf-8")
    checks = _gate_checks(ctx, final_text)
    section = _skill("## Phase 6:")
    instructions = section[:section.index("### After submission")].strip() if "### After submission" in section else section
    said = "\n".join(f"- {c['check']}: {c['detail']}" for c in checks)
    reply = ctx.ask(Prompt(system_prompt("a proposal manager", "the Submit gate", "proposal-drafting", instructions, PACKET_SPEC),
                           user_prompt(ctx, ("THE GATE'S CHECKS, FROM THE WORKER", said),
                                       ("REQUIREMENTS ANALYSIS, FROM STEP 4", ctx.earlier("requirements.md")),
                                       ("SUBMISSION CHECKLIST AND DATES, FROM STEP 4", ctx.earlier("submission_checklist.md")),
                                       ("THE FINAL VERSION", final_text))),
                    "submission packet", PACKET_TOKENS)
    document, data = split_reply(reply)
    saved = ctx.save("submission_packet.md", document or reply, "Submission packet")
    files = [{"file": str(f["file"]).strip(), "slot": str(f.get("slot") or "").strip()}
             for f in data.get("files") or [] if isinstance(f, dict) and str(f.get("file") or "").strip()]
    passing = sum(1 for c in checks if c["ok"])
    lines = [f"{passing} of {len(checks)} checks pass"] + [f"{c['check']}: {c['detail']}" for c in checks if c["ok"] is False]
    return StepResult(summary=bullets(lines), files=[saved],
                      content={"document": document, "checks": checks, "files": files,
                               "portal_steps": strings(data.get("portal_steps")),
                               "deadline": str(data.get("deadline") or "").strip() or ctx.record.call.get("due_date"),
                               "call_page": ctx.record.call.get("url"), "question": QUESTIONS["submit"]})


RUNNERS = {"outline": outline, "draft": draft, "compliance": compliance, "reviews": reviews, "final": final, "submit": submit}
