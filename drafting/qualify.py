"""The Qualify stage's steps (PW6 to PW10, PRO-577), from Velocity's opportunity-assessment workflow as
adapted to the workspace (drafting/skills/opportunity_assessment.md).

    RUNNERS["discovery"](ctx) -> StepResult

Each step gives the model its part of the skill, the call and the dashboard's record
(drafting/inputs.py), the documents earlier steps saved, and on a redo the owner's note with the
last version. The model writes the document in Markdown and ends with a fenced json block of what
the page shows beyond it. Requirements and checklist runs the reference pipeline's requirements
prompt unchanged, then a second call for the checklist, whose rows, internal submit-by date and
milestones go into the ledger. The skill's check-ins are the dashboard's approvals, so each step's
question for the owner (QUESTIONS) is shown on its card rather than asked by the model.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from drafting import prompts
from drafting.company import profile
from drafting.dates import business_day_before, deadline_day
from drafting.inputs import call_facts, clashes_text, draft_inputs
from drafting.pipeline import MAX_TOKENS as PIPELINE_MAX_TOKENS
from drafting.prompts import Prompt
from drafting.steps import StepContext, StepResult, bullets, first_lines, split_reply
from ledger import queries as lq

SKILL = Path(__file__).resolve().parent / "skills" / "opportunity_assessment.md"
PHASES = {"discovery": 1, "summary": 2, "alignment": 3, "requirements": 4, "go_no_go": 5}
QUESTIONS = {
    "discovery": "Anything else to look at, or anything that needs a login?",
    "summary": "Worth digging deeper?",
    "alignment": "Does this match your read? Are there capabilities or past work I am missing?",
    "requirements": "The items that need your input are in 2.3, and any open eligibility actions are in 1.4. "
                    "Anything to add or correct before we make the go or no-go call?",
    "go_no_go": "Here is the decision brief and my recommendation. Do we go, go with conditions, or pass?",
}
TASKS = {
    "call_page": "Re-check the call page",
    "attachments": "Download every attachment",
    "parent_instructions": "Find the parent instructions",
    "key_facts": "Pull out the key facts",
    "past_work": "Compare with past work",
    "clashes": "Check for clashes",
    "record": "Bring in the dashboard's record",
    "summary": "Write the Discovery summary",
}
TASK_STATES = ("done", "for_owner")
FITS = ("Strong fit", "Moderate fit", "Stretch fit", "Poor fit")
RECOMMENDATIONS = ("go", "go_with_conditions", "no_go")
WORTH_IT = ("yes", "no", "unsure")
MILESTONES = ("outline", "draft", "compliance", "reviews", "final")
PART_TITLES = {
    "registrations": "2.1 Registrations and eligibility",
    "documents": "2.2 Required documents and volumes",
    "inputs": "2.3 Inputs needed from the owner and the team",
    "formatting": "2.4 Formatting and packaging",
    "reviews": "2.5 Reviews and approvals",
    "submission": "2.6 Submission",
}
MAX_TOKENS = {"discovery": 8_000, "summary": 4_000, "alignment": 8_000, "checklist": 12_000, "go_no_go": 6_000}
RESULT_DAYS = 90
DEFAULT_SOURCE = "default, 90 days after the deadline"
OWNER_WORDS = ("owner", "the owner", "proposal owner", "the proposal owner")

HOW_IT_RUNS = """How this step runs here:
- You cannot open web pages, sign in to portals or download files. Everything known about the call is in the message. Where a task needs a page, a login or a file you do not have, say so plainly and name what the owner should fetch. Never guess what such a page or file says.
- Write the document in Markdown, starting with its heading. The worker saves it in the pursuit's folder and makes the Word file, so leave file names to it.
- The dashboard asks the owner this step's question for you, so do not end with a question.
- Never use an em dash or an en dash.
"""
AFTER_DOCUMENT = "- After the document, add one fenced json block with these fields, and nothing after it:\n"
JSON_ONLY = "- Reply with one fenced json block with these fields and nothing else; the worker writes the document from it:\n"

DISCOVERY_SPEC = """{"key_points": ["three to six short points for the step's card"],
 "tasks": {"call_page": "done or for_owner", "attachments": "done or for_owner", "parent_instructions": "done or for_owner",
           "key_facts": "done or for_owner", "past_work": "done or for_owner", "clashes": "done or for_owner",
           "record": "done or for_owner", "summary": "done"},
 "owner_fetch": ["each page or file the owner should fetch, and why"],
 "result_expected": {"date": "YYYY-MM-DD, or null when nothing says", "words": "the call's own words, quoted", "where": "where you found them"}}
A task is done when you did it with what you have, and for_owner when it needs a page, a login or a file you do not have."""
SUMMARY_SPEC = """{"key_points": ["three to six short points for the step's card"], "worth_it": "yes, no or unsure"}"""
ALIGNMENT_SPEC = """{"key_points": ["three to six short points for the step's card"],
 "verdict": "the one-line verdict on the fit",
 "angle": "the angle you propose: what to lead with, and how to close each gap",
 "comparison": "where your angle and the owner's direction agree and differ, or that the owner gave none"}"""
CHECKLIST_SPEC = """{"key_points": ["three to six short points for the step's card"],
 "checklist": [{"part": "registrations, documents, inputs, formatting, reviews or submission",
                "text": "the item, specific to this call", "source": "where the call asks for it, or null",
                "owner": "Claude, the owner's name, or another named person", "due": "YYYY-MM-DD or null",
                "done": "true only when it is already met"}],
 "submit_by": "YYYY-MM-DD, the internal submit-by date, at least one business day before the deadline",
 "milestones": {"outline": "YYYY-MM-DD", "draft": "YYYY-MM-DD", "compliance": "YYYY-MM-DD", "reviews": "YYYY-MM-DD", "final": "YYYY-MM-DD"},
 "questions": [{"question": "the question as you would submit it", "deadline": "the Q&A deadline", "channel": "how to send it"}],
 "sources": [{"name": "the document", "what": "what it is", "version": "its version or amendment date"}]}
The parts are the six subsections of Section 2; leave out parts this call does not need. The milestones are Section 3.1's internal milestones, worked back from the submit-by date."""
GO_NO_GO_SPEC = """{"key_points": ["three to six short points for the step's card"],
 "fit": "Strong fit, Moderate fit, Stretch fit or Poor fit",
 "recommendation": "go, go_with_conditions or no_go",
 "conditions": ["each condition, one per item, when you recommend go with conditions"]}"""


# ------------------------------------------------------------------------- the skill

def _skill() -> str:
    return SKILL.read_text(encoding="utf-8")


def skill_section(step: str) -> str:
    """The skill's part for a step: its "## Phase N:" section, up to the rule before the next."""
    text = _skill()
    start = text.index(f"## Phase {PHASES[step]}:")
    end = text.find("\n---\n", start)
    return text[start:end if end >= 0 else len(text)].strip()


def checklist_instructions() -> str:
    """Phase 4's Sections 2 and 3: the checklist, the dates, the questions and the source documents."""
    section = skill_section("requirements")
    start = section.index("**Section 2, submission checklist:**")
    end = section.find("### Finishing the document", start)
    return section[start:end if end >= 0 else len(section)].strip()


def _system(step: str, label: str, spec: str, instructions: str | None = None, json_only: bool = False) -> str:
    company = profile()
    return (f"You are a senior BD analyst at {company.get('company_name', 'Velocity Explorations')}, "
            f"{company.get('company_description', '')}. You run one step of the proposal workspace on the BD Team "
            f"dashboard, for a call the team chose to pursue: {label}.\n\n"
            "Your instructions for this step, from Velocity's opportunity-assessment workflow:\n\n"
            f"{instructions or skill_section(step)}\n\n{HOW_IT_RUNS}{JSON_ONLY if json_only else AFTER_DOCUMENT}{spec}")


def _user(ctx: StepContext, *sections: tuple[str, str]) -> str:
    parts = [call_facts(ctx.record, ctx.today)]
    for title, text in sections:
        if text.strip():
            parts += ["", title, text.strip()]
    return "\n".join(parts) + ctx.redo_block()


# ----------------------------------------------------------------------- the checks

def _date(value: Any) -> str | None:
    """A YYYY-MM-DD string, or None."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        return None
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError:
        return None


def _strings(value: Any) -> list[str]:
    return [str(v).strip() for v in value if str(v).strip()] if isinstance(value, list) else []


def _points(data: Mapping[str, Any], document: str) -> str:
    return bullets(data.get("key_points")) or first_lines(document)


def _choice(value: Any, allowed: tuple[str, ...]) -> str | None:
    return value if isinstance(value, str) and value in allowed else None


def _tasks(found: Any) -> dict[str, str]:
    """Each Discovery task's state: done or for the owner. Anything else is left for the owner, and the
    summary is done, since this step wrote it."""
    found = found if isinstance(found, dict) else {}
    states = {task: found.get(task) if found.get(task) in TASK_STATES else "for_owner" for task in TASKS}
    states["summary"] = "done"
    return states


def _result_expected(ctx: StepContext, found: Any) -> dict[str, str | None]:
    """When the result is expected (P4): the date the call gives, with its words and where they are;
    else 90 days after the deadline, when the deadline is a date."""
    found = found if isinstance(found, dict) else {}
    when, source = _date(found.get("date")), None
    if when:
        words, where = str(found.get("words") or "").strip(), str(found.get("where") or "").strip()
        source = f'"{words}" ({where})' if words and where else (words or where or "the call")
    else:
        day = deadline_day(ctx.record.call.get("due_date"))
        if day:
            when, source = (day + timedelta(days=RESULT_DAYS)).isoformat(), DEFAULT_SOURCE
    if when and source:
        lq.set_result_expected(ctx.pursuit["id"], when, source)
    return {"date": when, "source": source}


# ------------------------------------------------------------------------- the steps

def discovery(ctx: StepContext) -> StepResult:
    """Step 1 (PW6): the eight tasks with their states, and when the result is expected."""
    ctx.progress({task: "working" for task in TASKS})
    reply = ctx.ask(Prompt(_system("discovery", "Discovery", DISCOVERY_SPEC),
                           _user(ctx, ("CLASH CHECK, FROM THE LEDGER", clashes_text(ctx.record)))),
                    "discovery", MAX_TOKENS["discovery"])
    document, data = split_reply(reply)
    tasks = _tasks(data.get("tasks"))
    ctx.progress(tasks)
    expected = _result_expected(ctx, data.get("result_expected"))
    saved = ctx.save("discovery.md", document or reply, "Discovery summary")
    return StepResult(summary=_points(data, document), files=[saved],
                      content={"document": document, "tasks": tasks, "owner_fetch": _strings(data.get("owner_fetch")),
                               "result_expected": expected, "question": QUESTIONS["discovery"]})


def summary(ctx: StepContext) -> StepResult:
    """Step 2 (PW7): the call in two minutes' reading, and a first word on the fit."""
    reply = ctx.ask(Prompt(_system("summary", "Opportunity summary", SUMMARY_SPEC),
                           _user(ctx, ("DISCOVERY SUMMARY, FROM STEP 1", ctx.earlier("discovery.md")))),
                    "opportunity summary", MAX_TOKENS["summary"])
    document, data = split_reply(reply)
    saved = ctx.save("opportunity_summary.md", document or reply, "Opportunity summary")
    return StepResult(summary=_points(data, document), files=[saved],
                      content={"document": document, "worth_it": _choice(data.get("worth_it"), WORTH_IT),
                               "question": QUESTIONS["summary"]})


def alignment(ctx: StepContext) -> StepResult:
    """Step 3 (PW8): the verdict, and Claude's angle beside the owner's direction."""
    reply = ctx.ask(Prompt(_system("alignment", "Alignment", ALIGNMENT_SPEC),
                           _user(ctx, ("DISCOVERY SUMMARY, FROM STEP 1", ctx.earlier("discovery.md")),
                                 ("OPPORTUNITY SUMMARY, FROM STEP 2", ctx.earlier("opportunity_summary.md")))),
                    "alignment", MAX_TOKENS["alignment"])
    document, data = split_reply(reply)
    saved = ctx.save("alignment.md", document or reply, "Alignment")
    return StepResult(summary=_points(data, document), files=[saved],
                      content={"document": document, "verdict": str(data.get("verdict") or "").strip() or None,
                               "angle": str(data.get("angle") or "").strip() or None,
                               "comparison": str(data.get("comparison") or "").strip() or None,
                               "direction": (ctx.pursuit.get("direction") or "").strip() or None,
                               "question": QUESTIONS["alignment"]})


def _checklist_items(ctx: StepContext, found: Any) -> list[dict[str, Any]]:
    """The model's checklist, kept to the six parts, each item with an owner and a real date or none."""
    owner = ctx.pursuit["owner"]
    items = []
    for item in found if isinstance(found, list) else []:
        if not isinstance(item, dict) or item.get("part") not in lq.CHECKLIST_PARTS or not str(item.get("text") or "").strip():
            continue
        who = str(item.get("owner") or "").strip()
        items.append({"part": item["part"], "text": str(item["text"]).strip(), "source": str(item.get("source") or "").strip() or None,
                      "owner": owner if not who or who.lower() in OWNER_WORDS else who,
                      "due_date": _date(item.get("due")), "done": item.get("done") is True})
    return items


def _target_dates(ctx: StepContext, data: Mapping[str, Any]) -> dict[str, str]:
    """The internal submit-by date, at least one business day before the deadline, and the milestones
    that fall on or before it (PW9)."""
    deadline = deadline_day(ctx.record.call.get("due_date"))
    submit_by = _date(data.get("submit_by"))
    if deadline and (submit_by is None or submit_by > business_day_before(deadline).isoformat()):
        submit_by = business_day_before(deadline).isoformat()
    if not submit_by:
        return {}
    found = data.get("milestones") if isinstance(data.get("milestones"), dict) else {}
    dates = {"submit_by": submit_by}
    for step in MILESTONES:
        when = _date(found.get(step))
        if when and when <= submit_by:
            dates[step] = when
    return dates


def _cell(text: Any) -> str:
    return str(text or "").replace("|", "/").replace("\n", " ").strip()


def _question(q: Mapping[str, Any]) -> str:
    """A question for the government, with when and how to send it."""
    when = ", ".join(x for x in (f"by {_cell(q.get('deadline'))}" if q.get("deadline") else "", _cell(q.get("channel"))) if x)
    return f"- {_cell(q['question'])}" + (f" ({when})" if when else "")


def render_checklist(items: list[dict[str, Any]], dates: Mapping[str, str], data: Mapping[str, Any]) -> str:
    """Sections 2 and 3 of the requirements document, as checkbox tables and lists."""
    lines = ["## Section 2: Submission checklist"]
    for part, title in PART_TITLES.items():
        mine = [i for i in items if i["part"] == part]
        if not mine:
            continue
        lines += ["", f"### {title}", "", "| | Item | Owner | Due | Source |", "|---|---|---|---|---|"]
        lines += [f"| {'☑' if i['done'] else '☐'} | {_cell(i['text'])} | {_cell(i['owner'])} | {i['due_date'] or ''} | "
                  f"{_cell(i['source'])} |" for i in items if i["part"] == part]
    lines += ["", "## Section 3: Timeline, questions and source documents", "", "### 3.1 Key dates and internal milestones", ""]
    if dates:
        lines += ["| Milestone | Target |", "|---|---|", f"| Internal submit-by | {dates['submit_by']} |"]
        lines += [f"| {lq.STEP_LABELS[step]} | {dates[step]} |" for step in MILESTONES if step in dates]
    else:
        lines.append("The deadline is not a date, so there is no internal submit-by date or milestones.")
    questions = [q for q in data.get("questions") or [] if isinstance(q, dict) and str(q.get("question") or "").strip()]
    lines += ["", "### 3.2 Questions for the government", ""]
    lines += [_question(q) for q in questions] or ["None found."]
    sources = [s for s in data.get("sources") or [] if isinstance(s, dict) and str(s.get("name") or "").strip()]
    lines += ["", "### 3.3 Source documents", ""]
    lines += [f"- {_cell(s['name'])}: {_cell(s.get('what'))}" + (f" ({_cell(s.get('version'))})" if s.get("version") else "")
              for s in sources] or ["None saved yet."]
    return "\n".join(lines)


def requirements(ctx: StepContext) -> StepResult:
    """Step 4 (PW9): the reference pipeline's requirements analysis, then the six-part checklist as rows,
    the internal submit-by date and the milestones."""
    draft = draft_inputs(ctx.record)
    analysis = prompts.p4_requirements(company=profile(), knowledge_base=draft.company_context,
                                       rag_context=draft.past_experience[:20_000], title=draft.title, agency=draft.agency,
                                       portal=draft.portal, opp_type=draft.opp_type, due_date=draft.due_date,
                                       listing_text=draft.listing_text[:80_000], attachment_text="")
    text = ctx.ask(Prompt(analysis.system, analysis.user + ctx.redo_block()), "analyzing requirements", PIPELINE_MAX_TOKENS["4"])
    first = ctx.save("requirements.md", text, "Requirements analysis")
    reply = ctx.ask(Prompt(_system("requirements", "Requirements and checklist", CHECKLIST_SPEC, checklist_instructions(),
                                   json_only=True),
                           _user(ctx, ("REQUIREMENTS ANALYSIS, FROM THE FIRST HALF OF THIS STEP", text),
                                 ("DISCOVERY SUMMARY, FROM STEP 1", ctx.earlier("discovery.md")))),
                    "submission checklist", MAX_TOKENS["checklist"])
    _, data = split_reply(reply)
    items = _checklist_items(ctx, data.get("checklist"))
    dates = _target_dates(ctx, data)
    lq.save_checklist(ctx.pursuit["id"], items, "requirements")
    if dates:
        lq.set_target_dates(ctx.pursuit["id"], dates)
    checklist = render_checklist(items, dates, data)
    second = ctx.save("submission_checklist.md", "# Requirements and submission checklist\n\n" + checklist,
                      "Requirements and submission checklist")
    return StepResult(summary=_points(data, text), files=[first, second],
                      content={"document": text.rstrip() + "\n\n" + checklist, "checklist_items": len(items),
                               "submit_by": dates.get("submit_by"), "milestones": {k: v for k, v in dates.items() if k != "submit_by"},
                               "question": QUESTIONS["requirements"]})


def go_no_go(ctx: StepContext) -> StepResult:
    """The Go or no-go gate (PW10): the decision brief and a recommendation. The owner decides."""
    reply = ctx.ask(Prompt(_system("go_no_go", "the Go or no-go gate", GO_NO_GO_SPEC),
                           _user(ctx, ("OPPORTUNITY SUMMARY, FROM STEP 2", ctx.earlier("opportunity_summary.md")),
                                 ("ALIGNMENT, FROM STEP 3", ctx.earlier("alignment.md")),
                                 ("REQUIREMENTS ANALYSIS, FROM STEP 4", ctx.earlier("requirements.md")),
                                 ("SUBMISSION CHECKLIST AND DATES, FROM STEP 4", ctx.earlier("submission_checklist.md")))),
                    "go or no-go brief", MAX_TOKENS["go_no_go"])
    document, data = split_reply(reply)
    saved = ctx.save("go_no_go_brief.md", document or reply, "Go or no-go brief")
    return StepResult(summary=_points(data, document), files=[saved],
                      content={"document": document, "fit": _choice(data.get("fit"), FITS),
                               "recommendation": _choice(data.get("recommendation"), RECOMMENDATIONS),
                               "conditions": _strings(data.get("conditions")), "question": QUESTIONS["go_no_go"]})


RUNNERS = {"discovery": discovery, "summary": summary, "alignment": alignment, "requirements": requirements,
           "go_no_go": go_no_go}
