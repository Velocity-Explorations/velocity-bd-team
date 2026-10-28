"""What every workspace step's work has to hand (PRO-577): its context, its result, and the helpers
for the model's reply and the step's files.

A step is a function `run(ctx: StepContext) -> StepResult`. It asks the model through `ctx.ask`,
which the worker meters and can stop, saves its documents with `ctx.save`, and returns the key
points for the step's card (PW4), the files it saved, and what the page shows beyond them.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from drafting.inputs import CallRecord
from drafting.prompts import Prompt

EARLIER_CHARS = 30_000
JSON_BLOCK = re.compile(r"```json\s*(.*?)```", re.S | re.I)


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

    @property
    def note(self) -> str:
        """What the owner asked to change, on an attempt queued by Ask for changes."""
        return (self.step.get("request_note") or "").strip()

    def earlier(self, name: str) -> str:
        """A document an earlier step saved in the pursuit's folder, or empty."""
        path = self.work_dir / name
        return path.read_text(encoding="utf-8")[:EARLIER_CHARS] if path.exists() else ""

    def save(self, name: str, text: str, label: str) -> dict[str, str]:
        """Save a document to the pursuit's folder; the file entry for pursuit_steps.files. Local until
        Drive (phase 6), so the entry carries the path under data/drafting/pursuits/."""
        self.work_dir.mkdir(parents=True, exist_ok=True)
        (self.work_dir / name).write_text(text.rstrip() + "\n", encoding="utf-8")
        return {"name": label, "local": f"{self.work_dir.name}/{name}"}

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
