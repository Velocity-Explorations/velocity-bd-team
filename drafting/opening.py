"""Each draft's opening is left for a person to write (PRO-494). Velocity's addition, not the reference's.

    places = find_places(draft)                # the opening paragraph, and the abstract's first three sentences
    prompt = frame_prompt(company, title, agency, requirements, alignment, places)
    points = parse_points(reply, len(places))  # 3 to 5 points per place, or a generic note
    text = render(draft, places, points)       # a marked placeholder and its points in place of each

Agreed with Shaun on 19 Oct 2026: evaluators read dozens of proposals that open the same way, so
the first impression is always written by a person. The model suggests points to land, never
sentences, so the opening is in the person's own words.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass

from drafting.prompts import Prompt

MARK = "[PERSON WRITES:"
WHY = "Evaluators read dozens of proposals that open the same way, so a person writes this."
GENERIC_POINTS = ["the customer's problem, in their own words", "what we offer that others do not",
                  "one proof point from our past work"]
MAX_POINTS = 5
POINT_CHARS = 160
MIN_WORDS = 12   # a shorter line is a label or a caption, not the opening
REQUIREMENTS_CHARS = 6_000
ALIGNMENT_CHARS = 4_000

HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
SKIP_SECTIONS = re.compile(r"\b(table of contents|contents|glossary|acronyms|abbreviations)\b", re.I)
ABSTRACT = re.compile(r"\b(abstract|executive summary)\b", re.I)
SUMMARY = re.compile(r"\bsummary\b", re.I)   # counts as the abstract only when it holds the opening
# Blocks that are never prose: tables, quotes, code, lists, rules, images, comments, bracketed
# instructions such as [NEEDS INPUT: ...] or [DELETE BEFORE SUBMISSION: ...], "**Label**:" and
# "**Label:**" lines, and lines that are only bold, only italic or only a bracketed placeholder.
NOT_PROSE = re.compile(r"^(\||>|```|~~~|[-*+]\s|\d+[.)]\s|-{3,}|\*{3,}|_{3,}|<!--|!\[|\[[A-Z][A-Z ]*[A-Z]:|"
                       r"\*\*[^*]+\*\*\s*:|\*\*[^*]+:\*\*|\*\*[^*]+\*\*\s*$|\*[^*]+\*\s*$|\[[^\]]*\]\s*$)")
ABBREVIATIONS = {"e.g", "i.e", "etc", "vs", "inc", "corp", "co", "ltd", "dr", "mr", "ms", "mrs", "no", "fig",
                 "approx", "u.s", "u.k", "st", "jr", "sr"}


@dataclass(frozen=True)
class Place:
    what: str     # what the person writes, as the placeholder names it
    start: int    # the span of the draft's text it replaces
    end: int
    taken: str    # that text, sent to the framing call and nowhere else


@dataclass(frozen=True)
class _Block:
    start: int
    end: int
    text: str
    heading: str   # the heading line of the section it sits in
    level: int     # that heading's level, 0 before the first heading
    is_heading: bool


def _blocks(draft: str) -> list[_Block]:
    """Runs of non-blank lines with their character spans; each heading line is a block of its own."""
    blocks: list[_Block] = []
    heading, level = "", 0
    start: int | None = None
    end = offset = 0
    for line in draft.splitlines(keepends=True):
        bare = line.rstrip("\r\n")
        line_start = offset
        offset += len(line)
        match = HEADING.match(bare.strip())
        if not bare.strip() or match:
            if start is not None:
                blocks.append(_Block(start, end, draft[start:end], heading, level, False))
                start = None
            if match:
                heading, level = bare.strip(), len(match.group(1))
                blocks.append(_Block(line_start, line_start + len(bare), bare, heading, level, True))
            continue
        if start is None:
            start = line_start
        end = line_start + len(bare)
    if start is not None:
        blocks.append(_Block(start, end, draft[start:end], heading, level, False))
    return blocks


def _prose(block: _Block) -> bool:
    return not block.is_heading and not NOT_PROSE.match(block.text.lstrip())


def _sentence_ends(text: str) -> list[int]:
    """Where each sentence of a paragraph ends; "U.S.", "e.g." and initials do not end one."""
    ends: list[int] = []
    for match in re.finditer(r"[.!?][\"')\]]*(?=\s|$)", text):
        before = re.search(r"([\w.]+)[.!?][\"')\]]*$", text[: match.end()])
        token = before.group(1).lower() if before else ""
        if text[match.start()] == "." and (token in ABBREVIATIONS or re.fullmatch(r"[a-z]", token)
                                           or re.fullmatch(r"(?:[a-z]\.)+[a-z]", token)):
            continue
        ends.append(match.end())
    tail = len(text.rstrip())
    if not ends or ends[-1] < tail:
        ends.append(tail)   # a paragraph that stops without a full stop still ends a sentence
    return ends


def _opening(blocks: list[_Block]) -> _Block | None:
    for block in blocks:
        if _prose(block) and len(block.text.split()) >= MIN_WORDS and not SKIP_SECTIONS.search(block.heading):
            return block
    return None


def _three_sentences(blocks: list[_Block], heading_index: int) -> tuple[int, int] | None:
    """(start, end) of the first three sentences of a section's prose, read across consecutive paragraphs."""
    start: int | None = None
    end = 0
    count = 0
    for nxt in blocks[heading_index + 1:]:
        if nxt.is_heading or (start is not None and not _prose(nxt)):
            break
        if not _prose(nxt):
            continue
        start = nxt.start if start is None else start
        for stop in _sentence_ends(nxt.text):
            count += 1
            end = nxt.start + stop
            if count == 3:
                return start, end
    return (start, end) if start is not None else None


def _abstract(blocks: list[_Block], opening: _Block | None) -> tuple[int, int, str] | None:
    """(start, end, name) of the first three sentences of the first Abstract or Executive Summary section,
    or of a Summary section that holds the opening paragraph."""
    for i, block in enumerate(blocks):
        named = ABSTRACT.search(block.text) if block.is_heading else None
        if named:
            span = _three_sentences(blocks, i)
            return (*span, named.group(1).lower()) if span else None
    if opening is not None and SUMMARY.search(opening.heading):
        heading_index = max(i for i, b in enumerate(blocks) if b.is_heading and b.start < opening.start)
        span = _three_sentences(blocks, heading_index)
        return (*span, "summary") if span else None
    return None


def find_places(draft: str) -> list[Place]:
    """Where a person writes: the opening paragraph, and the abstract's first three sentences when they
    are elsewhere (one place when the draft opens with its abstract). None in a draft already held."""
    if MARK in draft:
        return []
    blocks = _blocks(draft)
    opening = _opening(blocks)
    abstract = _abstract(blocks, opening)
    places: list[Place] = []
    if opening is not None and abstract is not None and abstract[0] == opening.start:
        end = max(opening.end, abstract[1])
        what = f"the opening paragraph and the first three sentences of the {abstract[2]}"
        return [Place(what, opening.start, end, draft[opening.start:end])]
    if opening is not None:
        places.append(Place("the opening paragraph", opening.start, opening.end, opening.text))
    if abstract is not None:
        start, end, name = abstract
        places.append(Place(f"the first three sentences of the {name}", start, end, draft[start:end]))
    return sorted(places, key=lambda p: p.start)


def frame_prompt(company: Mapping[str, str], title: str, agency: str, requirements: str, alignment: str,
                 places: list[Place]) -> Prompt:
    """The one model call of the Opening phase: points to land in each place, never the sentences."""
    name = company.get("company_name") or company.get("short_name") or "the company"
    system = (f"You help {name} prepare proposals. You never write the opening of a proposal: you list the points a "
              f"person should land in it, as short fragments, so the opening is in their own words.")
    blocks = "\n\n".join(f"PLACE {n} ({place.what}). The draft's version, for context only:\n{place.taken}"
                         for n, place in enumerate(places, start=1))
    user = (f"A person at {name} will write the opening of this proposal themselves. For each place below, list 3 to 5 "
            f"points it should land: the customer's problem in their own words, what {name} offers that others do not, "
            f"and one proof point from the draft. Each point is a fragment of at most 15 words, not a sentence to paste.\n\n"
            f"Answer in exactly this form, one block per place, in order:\nPLACE 1:\n- point\n- point\n\n"
            f"OPPORTUNITY: {title} ({agency})\n\n"
            f"REQUIREMENTS (excerpt):\n{requirements[:REQUIREMENTS_CHARS]}\n\n"
            f"ALIGNMENT (excerpt):\n{alignment[:ALIGNMENT_CHARS]}\n\n{blocks}")
    return Prompt(system=system, user=user)


def _bullets(text: str) -> list[str]:
    points = []
    for line in text.splitlines():
        match = re.match(r"^\s*[-*•]\s+(.*\S)", line)
        if match:
            points.append(match.group(1)[:POINT_CHARS])
    return points[:MAX_POINTS]


def parse_points(reply: str, count: int) -> list[list[str]]:
    """Points per place, in order; a place the reply gave none gets the generic points."""
    parts = re.split(r"(?im)^\s*PLACE\s+(\d+)\b.*$", reply or "")
    found: dict[int, list[str]] = {}
    if len(parts) > 1:
        for number, body in zip(parts[1::2], parts[2::2]):
            found.setdefault(int(number), _bullets(body))
    elif count == 1:
        found[1] = _bullets(reply or "")
    return [found.get(n) or list(GENERIC_POINTS) for n in range(1, count + 1)]


def render(draft: str, places: list[Place], points: list[list[str]]) -> str:
    """The draft with each place replaced by its placeholder and the points to land under it."""
    text = draft
    for place, place_points in sorted(zip(places, points), key=lambda pair: pair[0].start, reverse=True):
        note = "\n".join(["> Points to land (not text to use):", *(f"> - {point}" for point in place_points)])
        block = f"{MARK} {place.what}. {WHY}]\n\n{note}"
        after = text[place.end:]
        if after and not after.startswith("\n"):
            after = "\n\n" + after.lstrip(" ")   # the rest of a paragraph the sentences were taken from
        text = text[: place.start] + block + after
    return text
