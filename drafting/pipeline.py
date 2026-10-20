"""The drafting pipeline: the reference's phases, in order, from inputs to six documents (Writer W0).

    outputs = run_pipeline(DraftInputs.load("inputs.json"), Path("data/drafting/sample"), PrintHooks())

Each phase is a function phase_xx(inputs, state, out_dir, hooks) -> state, with the
reference's prompts (drafting/prompts.py), truncation limits and file names. A phase that
fails is recorded and the run carries on with the best draft so far, as the reference did
(draft_final, then draft_v3, draft_v2, draft). DraftCancelled is never caught: it ends the
run. With from_phase, earlier phases load their saved files instead of running; with
to_phase, later phases do not run. No ledger, Proposal Library, Drive or Slack in this phase.
"""
from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Protocol

from drafting import llm, prompts
from drafting.company import profile
from drafting.phases import PHASES, Phase, index
from drafting.templates import select_template

log = logging.getLogger("drafting.pipeline")

PHASE_TIMEOUT_S = 1800          # the reference's safety net per model call
MAX_TOKENS = {"4": 32_000, "4.5": 16_000, "5": 24_000, "6": 48_000, "6.5": 48_000, "6.75": 64_000,
              "7": 16_000, "7.5": 48_000}
OUTPUTS = {"4": ["requirements.md"], "4.5": ["alignment.md"], "5": ["outline.md"], "6": ["draft.md"],
           "6.5": [f"draft_review_pass{n}.md" for n in range(1, 5)] + ["draft_v2.md"],
           "6.75": ["compliance_report.md", "draft_v3.md"], "7": ["checklist.md"], "7.5": ["draft_final.md"]}
FINAL_CHAIN = ["draft_final.md", "draft_v3.md", "draft_v2.md", "draft.md"]
DOCUMENTS = {"requirements": "requirements.md", "alignment": "alignment.md", "outline": "outline.md",
             "compliance": "compliance_report.md", "checklist": "checklist.md"}


# ------------------------------------------------------------------------------ inputs

@dataclass
class DraftInputs:
    title: str
    portal: str
    opp_type: str
    agency: str
    due_date: str
    url: str = ""
    description: str = ""
    listing_text: str = ""
    attachments: list[dict[str, str]] = field(default_factory=list)
    past_experience: str = ""
    company_context: str = ""
    team_notes: str = ""
    template: dict[str, str] = field(default_factory=dict)   # {"name": ..., "text": ...}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DraftInputs":
        known = {f.name for f in fields(cls)}
        inputs = cls(**{k: v for k, v in data.items() if k in known})
        if not inputs.template.get("text"):
            name, text, is_fallback = select_template(inputs.opp_type)
            inputs.template = {"name": name, "text": text}
            if is_fallback:
                log.warning("No template for opportunity type %r; using %s", inputs.opp_type, name)
        return inputs

    @classmethod
    def load(cls, path: Path) -> "DraftInputs":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def save(self, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


@dataclass
class DraftOutputs:
    out_dir: Path
    final_draft: Path | None
    documents: dict[str, Path]
    phases: dict[str, dict[str, Any]]


class Hooks(Protocol):
    def phase_started(self, phase: Phase) -> None: ...

    def phase_finished(self, phase: Phase, status: str, stats: dict[str, Any]) -> None: ...


class PrintHooks:
    """Progress to stdout, one line per phase start and finish."""

    def phase_started(self, phase: Phase) -> None:
        print(f"start  {phase.id:>5} {phase.name}", flush=True)

    def phase_finished(self, phase: Phase, status: str, stats: dict[str, Any]) -> None:
        detail = f" in {stats['seconds']:.0f}s" if "seconds" in stats else ""
        if stats.get("error"):
            detail += f": {stats['error']}"
        print(f"finish {phase.id:>5} {phase.name}: {status}{detail}", flush=True)


# ------------------------------------------------------------------------------- state

@dataclass
class RunContext:
    generate: Callable[..., str]
    model: str | None
    company: dict[str, str]
    abort: llm.AbortToken | None


@dataclass
class State:
    run: RunContext
    listing_text: str = ""
    attachments: list[dict[str, str]] = field(default_factory=list)
    rag_context: str = ""
    requirements: str = ""
    alignment: str = ""
    outline: str = ""
    draft: str = ""                                   # the best draft so far
    stats: dict[str, Any] = field(default_factory=dict)  # the running phase's stats


def _write(out_dir: Path, name: str, text: str) -> None:
    (out_dir / name).write_text(text, encoding="utf-8")
    log.info("wrote %s (%d words)", name, len(text.split()))


def _read(out_dir: Path, name: str) -> str:
    path = out_dir / name
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _ask(state: State, phase_id: str, prompt: prompts.Prompt, label: str) -> str:
    """One model call for the running phase, with its characters and tokens added to the phase's stats."""
    stats = state.stats
    calls = stats.setdefault("calls", [])

    def record(usage: llm.Usage) -> None:
        calls.append({"label": usage.phase_label, "input_tokens": usage.input_tokens,
                      "output_tokens": usage.output_tokens, "seconds": usage.seconds,
                      "truncated": usage.truncated})

    stats["chars_in"] = stats.get("chars_in", 0) + len(prompt.system) + len(prompt.user)
    text = state.run.generate(prompt.user, prompt.system, model=state.run.model, max_tokens=MAX_TOKENS[phase_id],
                              timeout=PHASE_TIMEOUT_S, phase_label=label, abort=state.run.abort, on_usage=record)
    stats["chars_out"] = stats.get("chars_out", 0) + len(text)
    return text


def _skip(state: State, why: str) -> State:
    state.stats["status"] = "skipped"
    state.stats["note"] = why
    log.warning(why)
    return state


def _alignment_block(alignment: str) -> str:
    return prompts.ALIGNMENT_BLOCK_HEADER + alignment[:15_000] if alignment else ""


# ------------------------------------------------------------------------------ phases

def phase_1_listing(inputs: DraftInputs, state: State, out_dir: Path, hooks: Hooks) -> State:
    """The listing text. W1 fetches it through the portal; here it comes from the inputs."""
    state.listing_text = inputs.listing_text or inputs.description
    state.stats["chars_out"] = len(state.listing_text)
    return state


def phase_2_attachments(inputs: DraftInputs, state: State, out_dir: Path, hooks: Hooks) -> State:
    state.attachments = [dict(a) for a in inputs.attachments]
    state.stats.update(documents=len(state.attachments), with_text=sum(1 for a in state.attachments if a.get("text")))
    return state


def phase_3_past_experience(inputs: DraftInputs, state: State, out_dir: Path, hooks: Hooks) -> State:
    """Past submissions for context. W1 takes them from the Proposal Library; here from the inputs."""
    state.rag_context = inputs.past_experience
    state.stats["chars_out"] = len(state.rag_context)
    return state


def phase_4_requirements(inputs: DraftInputs, state: State, out_dir: Path, hooks: Hooks) -> State:
    attachment_text = "\n\n---\n\n".join(f"[{a['name']}]\n{a['text']}" for a in state.attachments if a.get("text"))
    if not state.listing_text and not attachment_text:
        return _skip(state, "Requirements: no listing or document text to analyze")
    prompt = prompts.p4_requirements(company=state.run.company, knowledge_base=inputs.company_context,
                                     rag_context=state.rag_context[:20_000], title=inputs.title,
                                     agency=inputs.agency, portal=inputs.portal, opp_type=inputs.opp_type,
                                     due_date=inputs.due_date, listing_text=state.listing_text[:80_000],
                                     attachment_text=attachment_text[:80_000])
    state.requirements = _ask(state, "4", prompt, "analyzing requirements")
    _write(out_dir, "requirements.md", state.requirements)
    return state


def phase_45_alignment(inputs: DraftInputs, state: State, out_dir: Path, hooks: Hooks) -> State:
    prompt = prompts.p45_alignment(company=state.run.company, knowledge_base=inputs.company_context,
                                   rag_context=state.rag_context[:20_000], title=inputs.title, agency=inputs.agency,
                                   portal=inputs.portal, opp_type=inputs.opp_type, due_date=inputs.due_date,
                                   requirements=state.requirements[:30_000])
    state.alignment = _ask(state, "4.5", prompt, "assessing alignment")
    _write(out_dir, "alignment.md", state.alignment)
    return state


def phase_5_outline(inputs: DraftInputs, state: State, out_dir: Path, hooks: Hooks) -> State:
    prompt = prompts.p5_outline(company=state.run.company, knowledge_base=inputs.company_context,
                                rag_context=state.rag_context[:20_000], title=inputs.title, agency=inputs.agency,
                                portal=inputs.portal, opp_type=inputs.opp_type, due_date=inputs.due_date,
                                requirements=state.requirements[:30_000],
                                template=inputs.template.get("text") or prompts.DEFAULT_SECTIONS,
                                alignment=state.alignment[:20_000])
    state.outline = _ask(state, "5", prompt, "building outline")
    _write(out_dir, "outline.md", state.outline)
    return state


def phase_6_draft(inputs: DraftInputs, state: State, out_dir: Path, hooks: Hooks) -> State:
    outline = state.outline
    if not outline:
        log.warning("Draft: no outline available, falling back to the raw template")
        outline = inputs.template.get("text") or prompts.DEFAULT_SECTIONS
    prompt = prompts.p6_draft(company=state.run.company, knowledge_base=inputs.company_context,
                              rag_context=state.rag_context[:30_000], title=inputs.title, agency=inputs.agency,
                              portal=inputs.portal, opp_type=inputs.opp_type, due_date=inputs.due_date,
                              requirements=state.requirements[:30_000], outline=outline[:30_000],
                              alignment=state.alignment[:20_000])
    state.draft = _ask(state, "6", prompt, "drafting response")
    _write(out_dir, "draft.md", state.draft)
    state.stats["needs_input"] = state.draft.count("[NEEDS INPUT:")
    return state


def phase_65_review(inputs: DraftInputs, state: State, out_dir: Path, hooks: Hooks) -> State:
    """Four review passes, each revising the draft the last one left. A failed pass keeps the draft."""
    if not state.draft:
        return _skip(state, "Review: no draft to review")
    current = state.draft
    passes = state.stats.setdefault("passes", [])
    for n in range(1, len(prompts.REVIEW_PASSES) + 1):
        label = prompts.review_pass_label(n, state.run.company)
        prompt = prompts.p65_review_pass(n, company=state.run.company, knowledge_base=inputs.company_context,
                                         rag_context=state.rag_context[:20_000], title=inputs.title,
                                         agency=inputs.agency, opp_type=inputs.opp_type, due_date=inputs.due_date,
                                         requirements=state.requirements[:20_000],
                                         alignment_block=_alignment_block(state.alignment), draft=current[:50_000])
        try:
            revised = _ask(state, "6.5", prompt, f"review pass {n}/4: {label}")
        except llm.PhaseError as exc:
            log.error("Review pass %d/4 (%s) failed, keeping the current draft: %s", n, label, exc)
            passes.append({"pass": n, "label": label, "status": "failed", "error": str(exc)[:300]})
            continue
        _write(out_dir, f"draft_review_pass{n}.md", revised)
        passes.append({"pass": n, "label": label, "status": "completed",
                       "words_delta": len(revised.split()) - len(current.split())})
        current = revised
    _write(out_dir, "draft_v2.md", current)
    state.stats["words_delta"] = len(current.split()) - len(state.draft.split())
    state.draft = current
    return state


def phase_675_compliance(inputs: DraftInputs, state: State, out_dir: Path, hooks: Hooks) -> State:
    if not state.draft:
        return _skip(state, "Compliance: no draft to check")
    prompt = prompts.p675_compliance(company=state.run.company, knowledge_base=inputs.company_context,
                                     alignment_context=_alignment_block(state.alignment), title=inputs.title,
                                     agency=inputs.agency, opp_type=inputs.opp_type, due_date=inputs.due_date,
                                     requirements=state.requirements[:25_000], draft=state.draft[:50_000])
    result = _ask(state, "6.75", prompt, "compliance check")
    if prompts.CORRECTED_DRAFT_SEPARATOR in result:
        report, corrected = result.split(prompts.CORRECTED_DRAFT_SEPARATOR, 1)
        corrected = corrected.strip()
    else:
        log.warning("Compliance: no separator found, treating the whole output as the corrected draft")
        report, corrected = "", result
    if report.strip():
        _write(out_dir, "compliance_report.md", report.strip())
    state.stats.update(open_items=report.count("❌"), warnings=report.count("⚠️"))
    if not corrected:
        log.warning("Compliance: the corrected draft was empty, keeping the previous draft")
        return state
    _write(out_dir, "draft_v3.md", corrected)
    state.draft = corrected
    return state


def phase_7_checklist(inputs: DraftInputs, state: State, out_dir: Path, hooks: Hooks) -> State:
    prompt = prompts.p7_checklist(company=state.run.company, title=inputs.title, agency=inputs.agency,
                                  due_date=inputs.due_date, requirements=state.requirements[:20_000],
                                  outline=state.outline[:15_000], draft=state.draft[:30_000])
    _write(out_dir, "checklist.md", _ask(state, "7", prompt, "building checklist"))
    state.stats["needs_input"] = state.draft.count("[NEEDS INPUT")
    return state


def phase_75_polish(inputs: DraftInputs, state: State, out_dir: Path, hooks: Hooks) -> State:
    if not state.draft:
        return _skip(state, "Polish: no draft to format")
    formatted = _ask(state, "7.5", prompts.p75_polish(draft=state.draft[:50_000]), "formatting document")
    _write(out_dir, "draft_final.md", formatted)
    state.draft = formatted
    return state


def phase_8_deliver(inputs: DraftInputs, state: State, out_dir: Path, hooks: Hooks) -> State:
    """Picks the final draft by the reference's fallback chain. W3 uploads to Drive; here it stays local."""
    final = final_draft(out_dir)
    state.stats["final_draft"] = final.name if final else None
    return state


PHASE_FUNCTIONS: dict[str, Callable[[DraftInputs, State, Path, Hooks], State]] = {
    "1": phase_1_listing, "2": phase_2_attachments, "3": phase_3_past_experience, "4": phase_4_requirements,
    "4.5": phase_45_alignment, "5": phase_5_outline, "6": phase_6_draft, "6.5": phase_65_review,
    "6.75": phase_675_compliance, "7": phase_7_checklist, "7.5": phase_75_polish, "8": phase_8_deliver,
}


def final_draft(out_dir: Path) -> Path | None:
    """The best draft on disk: draft_final, then draft_v3, draft_v2, draft."""
    return next((out_dir / name for name in FINAL_CHAIN if (out_dir / name).exists()), None)


def _load(phase_id: str, inputs: DraftInputs, state: State, out_dir: Path, hooks: Hooks) -> None:
    """What an earlier phase left, for a run that starts after it."""
    if phase_id in ("1", "2", "3"):
        PHASE_FUNCTIONS[phase_id](inputs, state, out_dir, hooks)
    elif phase_id == "4":
        state.requirements = _read(out_dir, "requirements.md")
    elif phase_id == "4.5":
        state.alignment = _read(out_dir, "alignment.md")
    elif phase_id == "5":
        state.outline = _read(out_dir, "outline.md")
    elif phase_id in ("6", "6.5", "6.75", "7.5"):
        name = {"6": "draft.md", "6.5": "draft_v2.md", "6.75": "draft_v3.md", "7.5": "draft_final.md"}[phase_id]
        state.draft = _read(out_dir, name) or state.draft


def run_pipeline(inputs: DraftInputs, out_dir: Path, hooks: Hooks, from_phase: str | None = None,
                 to_phase: str | None = None, *, generate: Callable[..., str] | None = None,
                 model: str | None = None, company: dict[str, str] | None = None,
                 abort: llm.AbortToken | None = None) -> DraftOutputs:
    """Run the phases from from_phase (default the first) to to_phase (default the last)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    first = index(from_phase) if from_phase else 0
    last = index(to_phase) if to_phase else len(PHASES) - 1
    state = State(run=RunContext(generate=generate or llm.generate, model=model,
                                 company=company if company is not None else profile(), abort=abort))
    results: dict[str, dict[str, Any]] = {}
    for i, ph in enumerate(PHASES):
        hooks.phase_started(ph)
        state.stats = {}
        if i < first:
            _load(ph.id, inputs, state, out_dir, hooks)
            status = "loaded"
        elif i > last:
            status = "not run"
        else:
            for name in OUTPUTS.get(ph.id, []):
                (out_dir / name).unlink(missing_ok=True)   # never leave a stale file from an earlier run
            started = time.monotonic()
            try:
                PHASE_FUNCTIONS[ph.id](inputs, state, out_dir, hooks)
                status = state.stats.pop("status", "completed")
            except llm.DraftCancelled:
                state.stats["seconds"] = round(time.monotonic() - started, 1)
                hooks.phase_finished(ph, "cancelled", state.stats)
                raise
            except Exception as exc:   # noqa: BLE001 (a failed phase is recorded and the run carries on)
                status = "failed"
                state.stats["error"] = str(exc)[:300]
                log.error("Phase %s (%s) failed: %s", ph.id, ph.name, exc)
            state.stats["seconds"] = round(time.monotonic() - started, 1)
        stats = dict(state.stats, status=status)
        results[ph.id] = stats
        hooks.phase_finished(ph, status, stats)
    final = final_draft(out_dir)
    documents = {key: out_dir / name for key, name in DOCUMENTS.items() if (out_dir / name).exists()}
    if final is not None:
        documents["draft"] = final
    return DraftOutputs(out_dir=out_dir, final_draft=final, documents=documents, phases=results)
