"""Velocity's facts for the Writer, read from 01 Company Reference in the BD Proposal Library on Drive (PRO-565).

    found = load()                                  # fresh from Drive; the copy saved here stands in for 24 hours
    text = found.block(hoverslam=False)             # the prompt section: how to use the facts, then each one by its id
    notes = found.notes(used, unsupported, "Draft v1", hoverslam=False, needs_fact=2)   # a draft's Facts used

The six files are named by their Drive ids in .env (SOURCES, docs/RUNBOOK.md). What they hold is never kept in the
repo, which is public: people edit the facts in Drive, and every step reads them again. The rules the files carry
are applied here rather than left to the model: a FORMER EMPLOYEE in 03 People is left out, Hoverslam's facts
appear only for a Hoverslam bid, and each item is marked when it is SENSITIVE or rests on a question 05 Conflicts
has not settled. Source links stay in the files; the Writer gets the facts without them.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from config import get
from drafting import drive, llm
from drafting.prompts import Prompt

CACHE = Path(__file__).resolve().parent.parent / "data" / "drafting" / "facts" / "company_reference.json"
MAX_AGE = timedelta(hours=24)
SOURCES = {   # name: (the .env key holding the file's Drive id, the file's name in 01 Company Reference, how it is read)
    "facts": ("COMPANY_FACTS_DOC_ID", "00 Company Facts", "doc"),
    "past_performance": ("PAST_PERFORMANCE_SHEET_ID", "01 Past Performance Register", "sheet"),
    "products": ("PRODUCTS_SHEET_ID", "02 Products & Capabilities", "sheet"),
    "people": ("PEOPLE_SHEET_ID", "03 People", "sheet"),
    "brand": ("BRAND_GUIDE_DOC_ID", "Brand Guide", "doc"),
    "conflicts": ("FACT_CONFLICTS_SHEET_ID", "05 Conflicts & Open Questions", "sheet"),
}
RESOLVED, PENDING, OPEN = "resolved", "evidence pending", "open"
FACT_ID = re.compile(r"^F-\d+[a-z]?$", re.I)
CONFLICT_ID = re.compile(r"\bCF-\d+\b")
ESCAPE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!$|<>~&=:])")   # what a Docs markdown export escapes
LINK = re.compile(r"\[([^\]]*)\]\((?:https?|mailto):[^)]*\)")
URL = re.compile(r"https?://\S+")
SEPARATOR = re.compile(r":?-+:?")
LEFT_OUT = {"source", "sources", "last verified", "last_verified", "evidence_links", "bio_link", "quad_chart_slide_links",
            "poc_contact_found"}   # links and bookkeeping the Writer has no use for
FORMER = "FORMER EMPLOYEE"
RULES = (
    "These files are the only source for any claim about the company: its past performance, contracts and their values, "
    "certifications, clearances, products and their TRL, results, customers, people and bios. State a company fact only "
    "as it is written here. When the text needs one that is not here, write [NEEDS FACT: what is missing] instead of a "
    "guess.",
    "- A field written [F-nn: ...] in a template or prompt takes its value from that fact: write the value, not the id.",
    "- Items marked [SENSITIVE] are used only when the solicitation requires them.",
    "- Items marked [OPEN: CF-nn] rest on a question 05 Conflicts has not settled. Never state one as settled; where the "
    "text needs it, write [NEEDS FACT: settle CF-nn, and what it is].",
    "- Items marked [EVIDENCE PENDING: CF-nn] were confirmed by David and may be used.",
    "- People: only the staff in 03 People below, all of them current staff. A partner is named as a partner.",
    "- Write names and spelling as the Brand Guide below says.",
)
VELOCITY = ("- The proposing company is Velocity Explorations: its legal name, UEI and CAGE are in 00 Company Facts below. "
            "Hoverslam Designs LLC is not part of this bid.")
HOVERSLAM = ("- This bid is for Hoverslam Designs LLC: wherever the text names the proposing company, its registration or "
             "its codes, use Hoverslam's facts below, not Velocity's. Its SAM renewal must be confirmed before submitting.")
TRACE_SPEC = """{"used": [{"id": "the fact's id, such as F-02, PP-01, PE-03 or PE-03.clearance_level", "claims": ["each place the draft relies on it, in a few words"]}],
 "unsupported": ["each claim about the company that rests on no fact here, quoted or summed up in a few words"]}"""


class FactsUnavailable(llm.PhaseError):
    """The facts could not be read from Drive, and no copy from the last 24 hours stands in."""


@dataclass(frozen=True)
class Item:
    """One fact or register row the Writer may cite by its id."""
    id: str
    source: str            # the file it comes from
    text: str              # what the Writer reads
    entity: str            # Velocity, Hoverslam, or a partner
    sensitive: bool = False
    conflicts: tuple[str, ...] = ()   # the 05 Conflicts ids it names


@dataclass(frozen=True)
class Question:
    """One row of 05 Conflicts & Open Questions."""
    standing: str          # resolved, evidence pending or open
    topic: str
    text: str
    entity: str


@dataclass
class Facts:
    items: dict[str, Item]
    questions: dict[str, Question]
    other_text: str        # 00 Company Facts outside its tables: handling, boilerplate, open items
    brand: str
    read_at: datetime
    note: str = ""         # why a saved copy stands in for Drive

    def marks(self, item: Item) -> list[str]:
        found = ["SENSITIVE"] if item.sensitive else []
        for cf in item.conflicts:
            standing = self.questions[cf].standing if cf in self.questions else OPEN
            if standing != RESOLVED:
                found.append(f"{'OPEN' if standing == OPEN else 'EVIDENCE PENDING'}: {cf}")
        return found

    def _line(self, item: Item) -> str:
        return f"{item.id}{''.join(f' [{m}]' for m in self.marks(item))} | {item.text}"

    def _when(self) -> str:
        return f"Read from 01 Company Reference on Drive at {self.read_at:%Y-%m-%d %H:%M} UTC." + (f" {self.note}" if self.note else "")

    def block(self, hoverslam: bool) -> str:
        """The section every Writer step reads: how to use the facts, then each one by its id."""
        lines = ["VELOCITY FACTS", self._when(), *RULES, HOVERSLAM if hoverslam else VELOCITY]
        for name, (_, title, _) in SOURCES.items():
            shown = [i for i in self.items.values() if i.source == title and (hoverslam or not _hoverslam(i.entity))]
            if shown:
                lines += ["", title.upper(), *(self._line(i) for i in shown)]
            if name == "facts" and self.other_text:
                lines += ["", "THE REST OF 00 COMPANY FACTS", self.other_text]
        unsettled = [f"{cf} [{q.standing}] | {q.text}" for cf, q in self.questions.items()
                     if q.standing != RESOLVED and (hoverslam or not _hoverslam(q.entity))]
        if unsettled:
            lines += ["", "05 CONFLICTS & OPEN QUESTIONS, NOT YET RESOLVED", *unsettled]
        if self.brand:
            lines += ["", "BRAND GUIDE", self.brand]
        from drafting.steps import fix_dashes   # here, not at the top: steps reads the facts through inputs

        return fix_dashes("\n".join(lines))   # the files use dashes; no prompt may carry one

    def trace_prompt(self, text: str, hoverslam: bool) -> Prompt:
        """The check that lists the facts a draft rests on, for its Facts used notes."""
        system = ("You check a proposal draft against Velocity's facts. List every claim the draft makes about the company "
                  "(the proposing company, its people, past performance, contracts and their values, certifications, "
                  "clearances, products and their TRL, results, customers and capabilities) with the ids of the facts it "
                  "rests on, and every such claim that rests on none. A [NEEDS FACT: ...] placeholder is not a claim. "
                  "Answer with one fenced json block and nothing else:\n" + TRACE_SPEC)
        return Prompt(system, f"{self.block(hoverslam)}\n\nTHE DRAFT\n{text}")

    def to_review(self, used: Sequence[Mapping[str, Any]]) -> list[str]:
        """The ids a draft relies on that need a person's look: SENSITIVE, or resting on a question not resolved."""
        return [str(u["id"]) for u in used if (item := self.items.get(str(u["id"]))) is not None and self.marks(item)]

    def notes(self, used: Sequence[Mapping[str, Any]], unsupported: Sequence[str], title: str, hoverslam: bool,
              needs_fact: int) -> str:
        """A draft's Facts used notes: each id it relies on and where, what to review, and claims with no fact."""
        known = [u for u in used if str(u["id"]) in self.items or str(u["id"]) in self.questions]
        lines = [f"# Facts used, {title}", "", self._when()]
        if known:
            lines += ["", "| ID | What the draft says |", "|---|---|"]
            lines += [f"| {u['id']} | {'; '.join(_claims(u)).replace('|', '/')} |" for u in known]
        review = []
        for u in known:
            item = self.items.get(str(u["id"]))
            if item is None:
                continue
            if item.sensitive:
                review.append(f"- {item.id} is SENSITIVE: get approval before it goes outside Velocity.")
            for cf in item.conflicts:
                question = self.questions.get(cf)
                topic = f" ({question.topic})" if question else ""
                if question is not None and question.standing == PENDING:
                    review.append(f"- {item.id} rests on {cf}{topic}, confirmed by David, evidence pending.")
                elif question is None or question.standing == OPEN:
                    review.append(f"- {item.id} rests on {cf}{topic}, which is still open: the draft must not state it as settled.")
        if hoverslam:
            review.append("- This is a Hoverslam bid: confirm Hoverslam Designs LLC's SAM renewal before submitting.")
        if review:
            lines += ["", "## To review before it goes out", *review]
        if unsupported:
            lines += ["", "## Claims with no fact behind them", "Each should rest on a fact, or be a [NEEDS FACT] placeholder.",
                      *(f"- {claim}" for claim in unsupported)]
        unknown = [u for u in used if u not in known]
        if unknown:
            lines += ["", "## Ids cited but not in 01 Company Reference", *(f"- {u['id']}: {'; '.join(_claims(u))}" for u in unknown)]
        lines += ["", f"{needs_fact} [NEEDS FACT] placeholder{'' if needs_fact == 1 else 's'} left in the draft."]
        return "\n".join(lines) + "\n"


def _hoverslam(entity: str) -> bool:
    return entity.strip().lower().startswith("hoverslam")


def _claims(used: Mapping[str, Any]) -> list[str]:
    found = used.get("claims") or used.get("claim") or []
    return [str(c).strip() for c in (found if isinstance(found, list) else [found]) if str(c).strip()]


def _clean(text: Any) -> str:
    """A cell as the Writer reads it: the export's escapes undone, a link reduced to its words, no bare addresses."""
    return " ".join(URL.sub("", ESCAPE.sub(r"\1", LINK.sub(r"\1", str(text)))).split())


def _standing(status: str) -> str:
    found = status.strip().lower()
    return RESOLVED if found.startswith(RESOLVED) else PENDING if PENDING in found else OPEN


def _cells(line: str) -> list[str]:
    inner = line.strip().removeprefix("|")
    inner = inner[:-1] if inner.endswith("|") and not inner.endswith("\\|") else inner
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", inner)]


def _tables(markdown: str) -> tuple[list[tuple[list[str], list[list[str]]]], list[str]]:
    """A doc's tables, each a header and its rows, and its lines outside them."""
    tables: list[tuple[list[str], list[list[str]]]] = []
    other: list[str] = []
    block: list[list[str]] = []
    for line in [*markdown.splitlines(), ""]:
        if line.lstrip().startswith("|"):
            block.append(_cells(line))
            continue
        if block:
            tables.append((block[0], [r for r in block[1:] if not all(SEPARATOR.fullmatch(c) for c in r if c)]))
            block = []
        other.append(line)
    return tables, other


def _doc_facts(markdown: str, title: str) -> tuple[list[Item], str]:
    """00 Company Facts: each F-numbered row, and the text outside the tables. A table without ids, such as the bios
    summary, is left out: 03 People holds the same people by id."""
    tables, other = _tables(markdown)
    items = []
    for header, rows in tables:
        names = [h.strip().lower() for h in header]
        if "id" not in names:
            continue
        for row in rows:
            cell = dict(zip(names, row))
            if not FACT_ID.match(cell.get("id", "")):
                continue
            sensitivity = _clean(cell.get("sensitivity", ""))
            entity = _clean(cell.get("entity", ""))
            text = f"{_clean(cell.get('fact', ''))}: {_clean(cell.get('value', ''))} ({entity}; {sensitivity})"
            items.append(Item(cell["id"], title, text, entity, sensitivity.upper().startswith("SENSITIVE"),
                              tuple(dict.fromkeys(CONFLICT_ID.findall(" ".join(row))))))
    text = "\n".join(ESCAPE.sub(r"\1", LINK.sub(r"\1", line)).rstrip() for line in other)
    return items, re.sub(r"\n{3,}", "\n\n", text).strip()


def _rows(tabs: Mapping[str, Sequence[Sequence[Any]]]) -> list[dict[str, str]]:
    found = []
    for rows in tabs.values():
        if not rows:
            continue
        header = [str(h).strip() for h in rows[0]]
        found += [{header[i]: str(row[i]).strip() for i in range(min(len(header), len(row))) if header[i]} for row in rows[1:]]
    return found


def _sheet_items(rows: list[dict[str, str]], title: str, people: bool) -> list[Item]:
    """A register's rows by their ids. A column marked SENSITIVE, such as a clearance, becomes its own item."""
    items = []
    for row in rows:
        key = next((k for k in row if k.lower() == "id" or k.lower().endswith("_id")), None)
        if key is None or not row.get(key):
            continue
        if people and FORMER in " ".join(row.values()).upper():
            continue   # only current staff go into bios and key personnel
        rid, entity = row[key], _clean(row.get("entity", ""))
        conflicts = tuple(dict.fromkeys(CONFLICT_ID.findall(" ".join(row.values()))))
        shown = {k: _clean(v) for k, v in row.items()
                 if v and k != key and k.lower() not in LEFT_OUT and "SENSITIVE" not in k.upper()}
        items.append(Item(rid, title, "; ".join(f"{k}: {v}" for k, v in shown.items() if v), entity,
                          "SENSITIVE" in row.get("sensitivity", "").upper(), conflicts))
        for k, v in row.items():
            if v and "SENSITIVE" in k.upper():
                column = re.sub(r"\s*\(SENSITIVE\)\s*", "", k, flags=re.I).strip()
                items.append(Item(f"{rid}.{column}", title, f"{_clean(row.get('name') or rid)}: {_clean(v)}", entity, True, conflicts))
    return items


def parse(files: Mapping[str, Any], read_at: datetime, note: str = "") -> Facts:
    """The six files, as read_drive gives them, made into the facts the Writer may use."""
    items: list[Item] = []
    other = ""
    for name, (_, title, kind) in SOURCES.items():
        if name == "facts":
            items, other = _doc_facts(str(files.get(name) or ""), title)
        elif kind == "sheet" and name != "conflicts":
            items += _sheet_items(_rows(files.get(name) or {}), title, people=name == "people")
    questions = {}
    for row in _rows(files.get("conflicts") or {}):
        cf = row.get("conflict_id", "")
        if CONFLICT_ID.fullmatch(cf):
            text = "; ".join(_clean(row[k]) for k in ("topic", "recommended_resolution") if row.get(k))
            questions[cf] = Question(_standing(row.get("status", "")), _clean(row.get("topic", "")), text,
                                     _clean(row.get("entity", "")))
    brand = "\n".join(ESCAPE.sub(r"\1", LINK.sub(r"\1", line)).rstrip() for line in str(files.get("brand") or "").splitlines())
    return Facts({i.id: i for i in items}, questions, other, brand.strip(), read_at, note)


def read_drive() -> dict[str, Any]:
    """Each file straight from Drive: a doc as markdown, a sheet as {tab: rows}."""
    ids = {name: (get(key) or "").strip() for name, (key, _, _) in SOURCES.items()}
    missing = [SOURCES[name][0] for name, found in ids.items() if not found]
    if missing:
        raise FactsUnavailable(f"Company facts: set {', '.join(missing)} in .env (docs/RUNBOOK.md, Company facts)")
    files, sheets = drive.client(), drive.sheets_client()
    if files is None or sheets is None:
        raise FactsUnavailable("Company facts: Drive is not set up on this PC (docs/RUNBOOK.md, Google Drive and Sheets)")
    return {name: files.export(ids[name], "text/markdown") if kind == "doc"
            else {tab: sheets.values(ids[name], tab) for tab in sheets.tabs(ids[name])}
            for name, (_, _, kind) in SOURCES.items()}


def _saved() -> tuple[datetime, dict[str, Any]] | None:
    try:
        found = json.loads(CACHE.read_text(encoding="utf-8"))
        return datetime.fromisoformat(found["read_at"]), found["files"]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def load(now: datetime | None = None) -> Facts:
    """The facts fresh from Drive, kept as the copy that stands in for up to 24 hours when Drive cannot be read."""
    now = now or datetime.now(timezone.utc)
    try:
        files = read_drive()
    except (drive.DriveError, FactsUnavailable) as exc:
        saved = _saved()
        if saved is None or now - saved[0] > MAX_AGE:
            raise FactsUnavailable(f"{exc}, and there is no copy from the last 24 hours") from exc
        return parse(saved[1], saved[0], note=f"Drive could not be read ({exc}), so this is the copy read then.")
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps({"read_at": now.isoformat(), "files": files}), encoding="utf-8")
    return parse(files, now)
