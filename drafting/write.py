"""The steps after Go (PW11 to PW14, PRO-578): Outline, First draft, Compliance check, Reviews, Final checks
and the Submit gate, from Velocity's proposal-drafting workflow (drafting/skills/proposal_drafting.md) and
the reference pipeline's prompts, whose words stay unchanged (drafting/prompts.py).

    RUNNERS["outline"](ctx) -> StepResult

Outline, First draft and Compliance check send the reference prompt with a workspace block after it: the
owner's direction and chosen past work, the skill's part for the step, the no-dash rule, and on a redo the
owner's note. Reviews runs three reviewers in turn, who propose changes the owner decides one by one
(PW12). Final checks puts the decided changes into Draft v3, then runs the reference's last phases: the
readiness checklist, the formatting pass, the opening held for a person to write (PRO-494), the
compliance check once more as a report only, and the AI slop check (PRO-510), with the dashes replaced
before the scan. It reports seven checks in words and adds what is left to fill to the checklist (PW13).
The Submit gate checks what the skill asks before the owner submits and writes the packet: each file's
portal slot and the portal's steps (PW14). The owner submits on the portal, then chooses Mark submitted.

Drafts are numbered in the pursuit's folder: draft_v1 (First draft), draft_v2 (Compliance check),
draft_v3 (the reviewers' decided changes) and draft_final (Final checks).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from drafting import llm, pipeline, prompts, scan, slop_gate
from drafting.company import profile
from drafting.inputs import builds_on_text, draft_inputs
from drafting.phases import Phase
from drafting.prompts import Prompt
from drafting.steps import (OTHER_NOTE, PLACEHOLDER, StepContext, StepResult, bullets, count_dashes, fix_dashes, latest_draft,
                            placeholder_counts, placeholder_line, points, skill_part, split_reply, strings, system_prompt,
                            user_prompt)
from ledger import queries as lq

SKILL = Path(__file__).resolve().parent / "skills" / "proposal_drafting.md"
QUESTIONS = {
    "outline": "Here is the proposed structure, page budget and the evidence it draws on. Does this look right? "
               "Any sections you want weighted differently, or evidence to add or drop?",
    "draft": "Here is the first complete draft. What are your first reactions before the compliance check and the reviews?",
    "compliance": "Here is what the compliance check found and fixed. Approve the fixes and move into the reviews?",
    "reviews": "Here is what the reviews found, as changes to decide. Accept, reject or edit each, then approve the draft.",
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


def _scan(ctx: StepContext, name: str) -> dict[str, Any]:
    """The AI slop check on a new draft (PW12): the worker's own fixes, the scan, kept in slop_scans."""
    return scan.check(ctx.pursuit["id"], ctx.step["id"], ctx.work_dir / name, slop_gate.solicitation_text(draft_inputs(ctx.record)))


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
    ctx.save("draft_v1.md", text, "Draft v1")
    slop = _scan(ctx, "draft_v1.md")
    saved = ctx.entry("draft_v1.md", "Draft v1")
    document = (ctx.work_dir / "draft_v1.md").read_text(encoding="utf-8")
    counts, words = placeholder_counts(document), len(document.split())
    return StepResult(summary=bullets([f"{words:,} words", placeholder_line(counts), f"AI slop check: {slop['verdict']}"]),
                      files=[saved],
                      content={"document": document, "words": words, "placeholders": counts, "slop": slop["verdict"],
                               "question": QUESTIONS["draft"]})


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
    ctx.save("draft_v2.md", corrected.strip() or current, "Draft v2")
    slop = _scan(ctx, "draft_v2.md")
    files.append(ctx.entry("draft_v2.md", "Draft v2"))
    corrections, warnings = report.count(CORRECTION), report.count(WARNING)
    lines = [f"{corrections} {'item' if corrections == 1 else 'items'} corrected in Draft v2",
             f"{warnings} {'warning' if warnings == 1 else 'warnings'} to check"]
    if not report.strip():
        lines = ["The check gave no report; its corrected text is Draft v2"]
    lines.append(f"AI slop check: {slop['verdict']}")
    return StepResult(summary=bullets(lines), files=files,
                      content={"document": fix_dashes(report.strip()), "corrections": corrections, "warnings": warnings,
                               "slop": slop["verdict"], "question": QUESTIONS["compliance"]})


REVIEWERS = [   # code (step_changes.reviewer), name, the role the model takes, the skill's part, whether it rates the criteria
    ("evaluator_1", "External evaluator", "an independent government evaluator scoring proposals against the published criteria",
     "### Review 1:", True),
    ("evaluator_2", "Second independent evaluator", "a second, independent government evaluator", "### Review 2:", True),
    ("leadership", "Velocity leadership", "a member of Velocity Explorations' leadership, who knows what the company can deliver",
     "### Review 3:", False),
]
REVIEW_TOKENS = 16_000
MAX_CHANGES = 25
RATED_SPEC = """{"key_points": ["three to six short points for the step's card"],
 "ratings": [{"criterion": "each evaluation criterion", "rating": "Outstanding, Good, Acceptable, Marginal or Unacceptable, or the call's own scale",
              "strengths": "the strengths an evaluator would note", "weaknesses": "the weaknesses or gaps"}],
 "changes": [{"section": "the section", "now": "the exact text in the draft to change, copied character for character",
              "suggested": "the text to put in its place", "why": "why, in a sentence"}]}
Propose at most 25 changes, the ones that matter most. Each change's now must appear in the draft exactly as written."""
UNRATED_SPEC = RATED_SPEC.replace(""" "ratings": [{"criterion": "each evaluation criterion", "rating": "Outstanding, Good, Acceptable, Marginal or Unacceptable, or the call's own scale",
              "strengths": "the strengths an evaluator would note", "weaknesses": "the weaknesses or gaps"}],
""", "")


def _review_part(heading: str) -> str:
    """One reviewer's part of the skill's Phase 4: from its heading to the next subsection or rule."""
    section = _skill("## Phase 4:")
    start = section.index(heading)
    ends = [i for i in (section.find("\n### ", start + 1), section.find("\n**After each review", start + 1)) if i >= 0]
    return section[start:min(ends) if ends else len(section)].strip()


def _changes(found: Any, draft: str) -> tuple[list[dict[str, Any]], int]:
    """A reviewer's changes whose text is in the draft, so each can be applied as decided; and how many were not."""
    kept, dropped = [], 0
    for item in found if isinstance(found, list) else []:
        now = str(item.get("now") or "") if isinstance(item, dict) else ""
        if not now.strip() or now not in draft:
            dropped += 1
            continue
        kept.append({"section": str(item.get("section") or "").strip() or None, "before": now,
                     "after": str(item.get("suggested") or ""), "reason": str(item.get("why") or "").strip() or None})
    return kept[:MAX_CHANGES], dropped + max(0, len(kept) - MAX_CHANGES)


def _ratings(found: Any) -> list[dict[str, str]]:
    return [{key: str(r.get(key) or "").strip() for key in ("criterion", "rating", "strengths", "weaknesses")}
            for r in found if isinstance(r, dict) and str(r.get("criterion") or "").strip() and str(r.get("rating") or "").strip()
            ] if isinstance(found, list) else []


def reviews(ctx: StepContext) -> StepResult:
    """Step 8 (PW12, PW25): three reviewers in turn (two evaluators who rate each criterion in words, then Velocity's
    leadership) read the newest draft and propose changes, one per row, for the owner to accept, reject or edit.
    The draft changes once the owner has decided; Final checks applies the accepted changes as Draft v3. A
    reviewer sees what the earlier ones proposed, so it does not repeat them."""
    _, current = _draft(ctx, "Reviews")
    passes: list[dict[str, Any]] = []
    files: list[dict[str, str]] = []
    documents: list[str] = []
    proposed: list[str] = []
    for n, (code, name, role, heading, rates) in enumerate(REVIEWERS, start=1):
        system = system_prompt(role, "Reviews", "proposal-drafting", _review_part(heading), RATED_SPEC if rates else UNRATED_SPEC)
        user = user_prompt(ctx, ("REQUIREMENTS ANALYSIS, FROM STEP 4", ctx.earlier("requirements.md")),
                           ("THE DRAFT TO REVIEW", current[:60_000]),
                           ("CHANGES EARLIER REVIEWERS PROPOSED; DO NOT PROPOSE THEM AGAIN", "\n".join(proposed)))
        try:
            reply = ctx.ask(Prompt(system, user + "\n\n" + PLACEHOLDER_RULE), f"review {n} of 3: {name}", REVIEW_TOKENS)
        except llm.PhaseError as exc:
            passes.append({"pass": n, "code": code, "reviewer": name, "status": "failed", "error": str(exc)[:300]})
            continue
        document, data = split_reply(reply)
        changes, dropped = _changes(data.get("changes"), current)
        lq.add_step_changes(ctx.step["id"], code, changes)
        proposed += [f"- {c['section'] or 'the draft'}: change {c['before'][:300]!r} to {c['after'][:300]!r}" for c in changes]
        files.append(ctx.save(f"review_{n}.md", document or reply, f"Review {n}, {name}"))
        documents.append(document)
        passes.append({"pass": n, "code": code, "reviewer": name, "status": "done", "ratings": _ratings(data.get("ratings")) if rates else [],
                       "changes": len(changes), "dropped": dropped, "points": strings(data.get("key_points"))})
    if not any(p["status"] == "done" for p in passes):
        raise llm.PhaseError("Reviews: every review pass failed")
    total = sum(p.get("changes", 0) for p in passes)
    lines = [f"{p['reviewer']}: " + (f"{p['changes']} {'change' if p['changes'] == 1 else 'changes'} proposed" if p["status"] == "done"
                                     else "failed") for p in passes]
    return StepResult(summary=bullets(lines), files=files,
                      content={"document": "\n\n".join(documents), "passes": passes, "changes": total,
                               "question": QUESTIONS["reviews"]})


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


def _apply_changes(ctx: StepContext) -> tuple[str, int, int]:
    """Draft v3: the reviewers' changes the owner accepted or edited (PW12), applied to the draft they reviewed.
    A change whose text no longer matches is counted, not forced. Once Draft v3 exists it stands, so a redo of
    Final checks never applies the changes twice."""
    v3 = ctx.work_dir / "draft_v3.md"
    if v3.exists():
        return v3.read_text(encoding="utf-8"), 0, 0
    base = next((ctx.work_dir / name for name in ("draft_v2.md", "draft_v1.md") if (ctx.work_dir / name).exists()), None)
    if base is None:
        raise llm.PhaseError("Final checks: there is no draft yet; run the First draft step first")
    current = base.read_text(encoding="utf-8")
    applied = missed = 0
    found = lq.latest_steps(ctx.pursuit["id"]).get("reviews")
    for change in lq.step_changes(found["id"]) if found else []:
        if change["state"] not in ("accepted", "edited"):
            continue
        before = change["before_text"] or ""
        if before and before in current:
            current = current.replace(before, (change["edited_text"] if change["state"] == "edited" else change["after_text"]) or "", 1)
            applied += 1
        else:
            missed += 1
    ctx.save("draft_v3.md", current, "Draft v3")
    return (ctx.work_dir / "draft_v3.md").read_text(encoding="utf-8"), applied, missed


def _check(name: str, ok: bool | None, detail: str, result: str | None = None) -> dict[str, Any]:
    """One check's outcome: passing, failing, or not known yet; with the word the page shows when it has one."""
    found = {"check": name, "ok": ok, "detail": detail}
    return found | {"result": result} if result is not None else found


RECHECK_TOKENS = pipeline.MAX_TOKENS["6.75"]   # the model thinks first; a small ceiling leaves no room for the report
REPORT_ONLY = ("\n\nThis is the final version, checked once more before submission. Give only the report, with the same "
               "marks; do not write the corrected draft. The owner fixes what the report finds.")
KIND_TASKS = {"PERSON WRITES": ("Write the place marked PERSON WRITES in the final version, in your own words",
                                "Write the {n} places marked PERSON WRITES in the final version, in your own words"),
              "NEEDS INPUT": ("Fill the NEEDS INPUT placeholder in the final version", "Fill the {n} NEEDS INPUT placeholders in the final version"),
              "NEEDS EVIDENCE": ("Give a source for the claim marked NEEDS EVIDENCE", "Give sources for the {n} claims marked NEEDS EVIDENCE"),
              "other": ("Clear the other bracketed note in the final version", "Clear the {n} other bracketed notes in the final version")}


def placeholder_list(text: str) -> list[dict[str, Any]]:
    """Each open placeholder in a text, in order: its kind, its text, its line and the heading it sits under (PW13)."""
    found = []
    section = ""
    for n, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("#"):
            section = line.strip().lstrip("#").strip()
        for match in PLACEHOLDER.finditer(line):
            found.append({"kind": match.group(1).upper(), "text": match.group(0)[:300], "line": n, "section": section})
        for match in OTHER_NOTE.finditer(line):
            found.append({"kind": "other", "text": match.group(0)[:300], "line": n, "section": section})
    return found


def checklist_check(items: list[dict[str, Any]]) -> dict[str, Any]:
    """Checklist updated (PW13): how much is done, and whether every open item has an owner and a date."""
    if not items:
        return _check("Checklist updated", None, "no checklist yet", "not run")
    done = sum(1 for item in items if item["done"])
    loose = sum(1 for item in items if not item["done"] and not (item["owner"] and item["due_date"]))
    head = f"{done} of {len(items)} done"
    if not loose:
        return _check("Checklist updated", True, f"{head}; every open item has an owner and a date", "updated")
    return _check("Checklist updated", False, f"{head}; {loose} open {'item has' if loose == 1 else 'items have'} no owner or no date",
                  "updated")


def _recheck(ctx: StepContext, text: str) -> tuple[dict[str, Any], dict[str, str] | None]:
    """The compliance check once more on the final version (PW13): its report only; the final version stays as it is."""
    name = "Final compliance re-check"
    d = draft_inputs(ctx.record)
    p = prompts.p675_compliance(company=profile(), knowledge_base=d.company_context, alignment_context=_alignment(ctx),
                                title=d.title, agency=d.agency, opp_type=d.opp_type, due_date=d.due_date,
                                requirements=ctx.earlier("requirements.md", 25_000), draft=text[:50_000])
    try:
        reply = ctx.ask(Prompt(p.system, p.user + _workspace(ctx, direction=False, placeholders=True) + REPORT_ONLY),
                        "final compliance re-check", RECHECK_TOKENS)
    except llm.PhaseError as exc:
        return _check(name, None, f"did not run: {str(exc)[:200]}", "not run"), None
    report = reply.split(prompts.CORRECTED_DRAFT_SEPARATOR, 1)[0].strip()
    if not report:
        return _check(name, None, "the check gave no report", "not run"), None
    saved = ctx.save("final_compliance.md", report, name)
    fix, warn = report.count(CORRECTION), report.count(WARNING)
    if fix:
        return _check(name, False, f"{fix} to fix, {warn} to check; the report is final_compliance.md", f"{fix} to fix"), saved
    if warn:
        return _check(name, True, f"{warn} to check; the report is final_compliance.md", "passed"), saved
    return _check(name, True, "every check from step 7 passes on the final version", "passed"), saved


def _final_checklist(ctx: StepContext, counts: dict[str, int]) -> None:
    """What is left to fill joins the checklist for the owner, due by the internal submit-by date (PW13)."""
    try:
        due = json.loads(ctx.pursuit.get("target_dates") or "{}").get("submit_by")
    except ValueError:
        due = None
    items = [{"part": "inputs", "text": (one if n == 1 else many.format(n=n)), "source": "Final checks", "owner": ctx.pursuit["owner"],
              "due_date": due} for kind, (one, many) in KIND_TASKS.items() if (n := counts.get(kind, 0))]
    lq.save_checklist(ctx.pursuit["id"], items, "final")


def final(ctx: StepContext) -> StepResult:
    """Step 9 (PW13): Draft v3 with the decided changes, the readiness checklist, the formatting pass, the opening held
    for a person to write, the dashes replaced, the compliance check once more, and the AI slop check's verdict on
    the final version; then the seven checks in words, the open placeholders, and the checklist updated."""
    current, applied, missed = _apply_changes(ctx)
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
    recheck, report = _recheck(ctx, final_path.read_text(encoding="utf-8"))
    slop = _scan(ctx, "draft_final.md")
    verdict = slop["verdict"]
    document = final_path.read_text(encoding="utf-8")
    files = [ctx.entry("draft_final.md", "Final version"), ctx.entry("checklist.md", "Submission readiness checklist")]
    if (ctx.work_dir / "slop_report.md").exists():
        files.append(ctx.entry("slop_report.md", "AI slop check report"))
    if report:
        files.append(report)
    counts = placeholder_counts(document)
    _final_checklist(ctx, counts)
    left = sum(counts.values())
    dashes_left = count_dashes(document)
    found = [f"{n} {kind if kind != 'other' else 'other bracketed notes'}" for kind, n in counts.items() if n]
    checks = [
        _check("Formatting check", True, "the formatting pass ran on the final version", "done"),
        recheck,
        _check("Placeholder sweep", not left, f"{', '.join(found)}, for {ctx.pursuit['owner']}" if left else "none left",
               f"{left} left" if left else "none left"),
        _check("AI slop check, final pass", bool(slop["ready"]) if slop["scan_id"] else None,
               f"{verdict}. " + ("Dash check passed: no en or em dashes" if not dashes_left else f"Dash check: {dashes_left} left"),
               ("ready" if slop["ready"] else "not ready") if slop["scan_id"] else "not run"),
        _check("Submission package check", None, "Runs once Drive is set up: file format, names, size limits, markings, PDF "
               "fonts and page count", "not run"),
        checklist_check(lq.checklist(ctx.pursuit["id"])),
        _check("Final version saved", True, "draft_final.md and its Word file; the numbered drafts are kept", "saved"),
    ]
    lines = [f"AI slop check: {verdict}", placeholder_line(counts)]
    if applied or missed:
        lines.insert(0, f"{applied} {'change' if applied == 1 else 'changes'} applied in Draft v3"
                        + (f"; {missed} no longer matched the draft" if missed else ""))
    if dashes:
        lines.append(f"{dashes} {'dash' if dashes == 1 else 'dashes'} replaced")
    passed = sum(1 for c in checks if c["ok"])
    lines.insert(0, f"{passed} of {len(checks)} final checks passed")
    return StepResult(summary=bullets(lines), files=files,
                      content={"document": document, "verdict": verdict, "ready": bool(slop["ready"]), "band": slop["band"],
                               "open_placeholders": slop["placeholders"], "person_writes": person_writes, "dashes_fixed": dashes,
                               "changes_applied": applied, "changes_missed": missed, "checks": checks,
                               "placeholders": placeholder_list(document), "question": QUESTIONS["final"]})


# --------------------------------------------------------------------------------- Submit

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
