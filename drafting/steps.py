"""What every workspace step's work has to hand (PRO-577, PRO-578): its context, its result, and the
helpers for prompts, the model's reply and the step's files.

A step is a function `run(ctx: StepContext) -> StepResult`. It asks the model through `ctx.ask`,
which the worker meters and can stop, saves its documents with `ctx.save`, and returns the key
points for the step's card (PW4), the files it saved, and what the page shows beyond them. Every
document is saved with its en and em dashes replaced (David's no-dash rule).
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from drafting import word
from drafting.company import profile
from drafting.inputs import CallRecord, call_facts
from drafting.prompts import Prompt

EARLIER_CHARS = 30_000
JSON_BLOCK = re.compile(r"```json\s*(.*?)```", re.S | re.I)
EN_DASH, EM_DASH = chr(0x2013), chr(0x2014)
DASH = f"[{EN_DASH}{EM_DASH}]"
DRAFTS = ("draft_final.md", "draft_v3.md", "draft_v2.md", "draft_v1.md")   # newest first
PLACEHOLDER = re.compile(r"\[(PERSON WRITES|NEEDS INPUT|NEEDS EVIDENCE)\b[^\]]*\]", re.I)
# Any other bracketed note that opens with a capitalized word, such as [CONFIRM ...], [UNVERIFIED] or [DATE]:
# a model sometimes leaves open items in its own words, and they must not pass a gate as nothing left.
OTHER_NOTE = re.compile(r"\[(?!(?:PERSON WRITES|NEEDS INPUT|NEEDS EVIDENCE)\b)[A-Z]{2,}(?:[ -][A-Z]{2,})*\b[^\]]{0,1000}\](?!\()")

HOW_IT_RUNS = """How this step runs here:
- You cannot open web pages, sign in to portals or download files. Everything known about the call is in the message. Where a task needs a page, a login or a file you do not have, say so plainly and name what the owner should fetch. Never guess what such a page or file says.
- Write the document in Markdown, starting with its heading. The worker saves it in the pursuit's folder and makes the Word file, so leave file names to it.
- The dashboard asks the owner this step's question for you, so do not end with a question.
- Never use an em dash or an en dash.
"""
AFTER_DOCUMENT = "- After the document, add one fenced json block with these fields, and nothing after it:\n"
JSON_ONLY = "- Reply with one fenced json block with these fields and nothing else; the worker writes the document from it:\n"


@dataclass
class StepResult:
    summary: str
    files: list[dict[str, str]] = field(default_factory=list)
    content: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepContext:
    pursuit: dict[str, Any]
    step: dict[str, Any]
    record: CallRecord
    work_dir: Path
    ask: Callable[[Prompt, str, int], str]                 # one metered model call: prompt, label, max tokens
    progress: Callable[[Mapping[str, str]], None]          # task states while the step works (PW6)
    previous: dict[str, Any] | None = None                 # the attempt before this one
    today: date = field(default_factory=date.today)
    word_format: word.Format = word.DEFAULT                # the solicitation's format, from Requirements and checklist

    @property
    def note(self) -> str:
        """What the owner asked to change, on an attempt queued by Ask for changes."""
        return (self.step.get("request_note") or "").strip()

    def earlier(self, name: str, limit: int = EARLIER_CHARS) -> str:
        """A document an earlier step saved in the pursuit's folder, or empty."""
        path = self.work_dir / name
        return path.read_text(encoding="utf-8")[:limit] if path.exists() else ""

    def save(self, name: str, text: str, label: str) -> dict[str, str]:
        """Save a document to the pursuit's folder, dashes replaced; the file entry for pursuit_steps.files."""
        self.work_dir.mkdir(parents=True, exist_ok=True)
        (self.work_dir / name).write_text(fix_dashes(text).rstrip() + "\n", encoding="utf-8")
        return self.entry(name, label)

    def entry(self, name: str, label: str) -> dict[str, str]:
        """A saved file's entry for pursuit_steps.files, with its Word file written beside it in the
        solicitation's format; a rule is a page break in drafts only. Local until Drive (phase 6b), so the
        entry carries the paths under data/drafting/pursuits/."""
        path = self.work_dir / name
        found = {"name": label, "local": f"{self.work_dir.name}/{name}"}
        if path.suffix == ".md" and path.exists():
            saved = word.to_docx(path.read_text(encoding="utf-8"), path.with_suffix(".docx"), self.word_format,
                                 page_breaks=name.startswith("draft"))
            found["word"] = f"{self.work_dir.name}/{saved.name}"
        return found

    def redo_block(self) -> str:
        """For Ask for changes: the owner's note and the version it is about, to go after a prompt."""
        if not self.note:
            return ""
        before = previous_document(self.previous)
        return ("\n\n---\n\nTHE OWNER ASKED FOR CHANGES TO YOUR LAST VERSION\n" + self.note
                + ("\n\nYOUR LAST VERSION\n" + before if before else ""))


def previous_document(previous: Mapping[str, Any] | None) -> str:
    if not previous or not previous.get("content"):
        return ""
    try:
        content = json.loads(previous["content"]) if isinstance(previous["content"], str) else previous["content"]
    except ValueError:
        return ""
    return str(content.get("document") or "")[:EARLIER_CHARS] if isinstance(content, dict) else ""


# ------------------------------------------------------------------------------ prompts

def skill_part(skill: Path, heading: str) -> str:
    """A skill's section, from its heading up to the rule before the next one."""
    text = skill.read_text(encoding="utf-8")
    start = text.index(heading)
    end = text.find("\n---\n", start)
    return text[start:end if end >= 0 else len(text)].strip()


def system_prompt(role: str, label: str, workflow: str, instructions: str, spec: str, json_only: bool = False) -> str:
    """A workspace step's system prompt: who the model is, the skill's part for the step, how the step runs
    here, and the json block the worker reads."""
    company = profile()
    return (f"You are {role} at {company.get('company_name', 'Velocity Explorations')}, "
            f"{company.get('company_description', '')}. You run one step of the proposal workspace on the BD Team "
            f"dashboard, for a call the team chose to pursue: {label}.\n\n"
            f"Your instructions for this step, from Velocity's {workflow} workflow:\n\n"
            f"{instructions}\n\n{HOW_IT_RUNS}{JSON_ONLY if json_only else AFTER_DOCUMENT}{spec}")


def user_prompt(ctx: StepContext, *sections: tuple[str, str]) -> str:
    """The call and the dashboard's record, then each earlier document that has text, then a redo's note."""
    parts = [call_facts(ctx.record, ctx.today)]
    for title, text in sections:
        if text.strip():
            parts += ["", title, text.strip()]
    return "\n".join(parts) + ctx.redo_block()


# ------------------------------------------------------------------------- the reply

def split_reply(text: str) -> tuple[str, dict[str, Any]]:
    """The document and the data the model put in its last fenced json block. A reply that is only JSON
    gives no document; a block that does not parse gives no data and leaves the text alone."""
    found = list(JSON_BLOCK.finditer(text))
    if not found:
        try:
            data = json.loads(text)
        except ValueError:
            return text.strip(), {}
        return "", data if isinstance(data, dict) else {}
    last = found[-1]
    try:
        data = json.loads(last.group(1))
    except ValueError:
        return text.strip(), {}
    document = (text[:last.start()] + text[last.end():]).strip()
    return document, data if isinstance(data, dict) else {}


def bullets(points: Any, limit: int = 6) -> str:
    """The step card's key points as a short list."""
    items = [str(p).strip() for p in points if str(p).strip()] if isinstance(points, list) else []
    return "\n".join(f"- {p}" for p in items[:limit])


def first_lines(document: str, limit: int = 3) -> str:
    """Key points when the model gave none: the document's first lines of prose."""
    lines = [line.strip() for line in document.splitlines() if line.strip() and not line.lstrip().startswith(("#", "|", "-"))]
    return "\n".join(f"- {line}" for line in lines[:limit])


def points(data: Mapping[str, Any], document: str) -> str:
    return bullets(data.get("key_points")) or first_lines(document)


def iso_date(value: Any) -> str | None:
    """A YYYY-MM-DD string, or None."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value.strip()):
        return None
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError:
        return None


def strings(value: Any) -> list[str]:
    return [str(v).strip() for v in value if str(v).strip()] if isinstance(value, list) else []


def choice(value: Any, allowed: tuple[str, ...]) -> str | None:
    return value if isinstance(value, str) and value in allowed else None


# ---------------------------------------------------------------------------- drafts

def fix_dashes(text: str) -> str:
    """En and em dashes replaced: a range of numbers reads "to", a dash opening a line becomes a hyphen,
    and any other becomes a comma."""
    text = re.sub(rf"(\d)\s*{DASH}\s*(\d)", r"\1 to \2", text)
    text = re.sub(rf"^(\s*){DASH}\s*", r"\1- ", text, flags=re.M)
    return re.sub(rf"\s*{DASH}\s*", ", ", text)


def count_dashes(text: str) -> int:
    return len(re.findall(DASH, text))


def latest_draft(work_dir: Path) -> Path | None:
    """The newest draft in the pursuit's folder: the final version, then v3, v2, v1."""
    return next((work_dir / name for name in DRAFTS if (work_dir / name).exists()), None)


def placeholder_counts(text: str) -> dict[str, int]:
    """Open placeholders by kind: PERSON WRITES, NEEDS INPUT, NEEDS EVIDENCE, and other bracketed notes."""
    counts = {"PERSON WRITES": 0, "NEEDS INPUT": 0, "NEEDS EVIDENCE": 0, "other": 0}
    for match in PLACEHOLDER.finditer(text):
        counts[match.group(1).upper()] += 1
    counts["other"] = len(OTHER_NOTE.findall(text))
    return counts


def placeholder_line(counts: Mapping[str, int]) -> str:
    found = [f"{n} {kind}" if kind != "other" else f"{n} other bracketed {'note' if n == 1 else 'notes'}"
             for kind, n in counts.items() if n]
    return f"Placeholders to fill: {', '.join(found)}" if found else "No placeholders left"
