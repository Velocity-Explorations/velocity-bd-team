"""Tags from a set list on each call (PRO-556).

The list is review/tags.yaml, in four groups: type (exactly one per call), then work, customer and
access (any that apply). Rules tag what a call's own data makes certain; Claude and Grok pick the
rest on the TAGS line of their review answers. Each source's tags are kept apart (call_tags).
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

TAGS_FILE = Path(__file__).with_name("tags.yaml")
GROUPS = ("type", "work", "customer", "access")
SINGLE = "type"   # the group a call gets exactly one tag from
LABELS = {"type": "Type, exactly one", "work": "Work, any that apply",
          "customer": "Customer, any that apply", "access": "Access, any that apply"}


@dataclass(frozen=True)
class TagList:
    groups: dict[str, dict[str, str]]   # group -> {tag: what it covers}, in the file's order

    @property
    def order(self) -> list[str]:
        return [name for group in GROUPS for name in self.groups[group]]

    def group_of(self, name: str) -> str | None:
        return next((group for group in GROUPS if name in self.groups[group]), None)

    def canonical(self, text: str) -> str | None:
        """The listed tag a piece of answer text names, ignoring case and stray punctuation."""
        wanted = text.strip().strip(".;[]\"'").strip().lower()
        return next((name for name in self.order if name.lower() == wanted), None)


def load_tags(path: Path = TAGS_FILE) -> TagList:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    groups: dict[str, dict[str, str]] = {}
    for group in GROUPS:
        entries = data.get(group)
        if not isinstance(entries, dict) or not entries:
            raise ValueError(f"{path.name}: the {group} group needs at least one tag")
        groups[group] = {str(name).strip(): " ".join(str(covers or "").split()) for name, covers in entries.items()}
    names = [name for group in GROUPS for name in groups[group]]
    if len({name.lower() for name in names}) != len(names):
        raise ValueError(f"{path.name}: a tag name is used twice")
    return TagList(groups)


@lru_cache(maxsize=1)
def tag_list() -> TagList:
    """The list in review/tags.yaml, read once per process."""
    return load_tags()


def prompt_block(tags: TagList) -> str:
    """The part of a judge's prompt that lists the tags it may choose."""
    lines = ["Tags: choose only from this list."]
    for group in GROUPS:
        items = "; ".join(f"{name} ({covers})" if covers else name for name, covers in tags.groups[group].items())
        lines.append(f"{LABELS[group]}: {items}.")
    return "\n".join(lines)


def catalog(tags: TagList) -> list[tuple[str, str, str]]:
    """(name, group, what it covers) for every tag, in list order: the ledger's tag_list rows."""
    return [(name, group, covers) for group in GROUPS for name, covers in tags.groups[group].items()]


def ordered(names: set[str], tags: TagList) -> list[str]:
    return [name for name in tags.order if name in names]


def parse_tags(text: str, tags: TagList) -> list[str]:
    """The listed tags on the answer's TAGS line, at most one type (the first named), in list order."""
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line.upper().startswith("TAGS:"):
            continue
        picked: set[str] = set()
        has_type = False
        for part in line.split(":", 1)[1].split(","):
            name = tags.canonical(part)
            if name is None:
                continue
            if tags.group_of(name) == SINGLE:
                if has_type:
                    continue
                has_type = True
            picked.add(name)
        return ordered(picked, tags)
    return []


# ------------------------------------------------------------------------------- rules

# A portal's own type -> the type tag, where that is certain whichever portal wrote it.
TYPE_BY_KIND = {
    "ota prototype": "OTA", "ota opportunity": "OTA",
    "capability demonstration": "Demo or exercise", "tech experimentation": "Demo or exercise",
    "market research": "RFI", "rfi": "RFI", "sources sought": "RFI",
    "prize challenge": "Prize challenge", "challenge": "Prize challenge",
    "far acquisition": "Proposal", "white paper": "White paper", "cso": "White paper", "crada": "Other",
    "industry day": "Event", "webinar": "Event", "conference": "Event", "event": "Event",
    "sbir cycle": "SBIR or STTR", "sttr cycle": "SBIR or STTR", "sbir/sttr cycle": "SBIR or STTR",
    "stratfi": "SBIR or STTR", "tacfi": "SBIR or STTR", "stratfi/tacfi": "SBIR or STTR",
}
TYPE_BY_PORTAL = {"NASA Forecast": "Forecast", "DOE SBIR": "SBIR or STTR"}   # every call on these
SOLICITATION_IS_PROPOSAL = {"SAM.gov", "Space Florida"}   # elsewhere "Solicitation" may be an OT call
CUSTOMER_BY_PORTAL = {"Vulcan SOF": "SOCOM", "NASA Forecast": "NASA", "DOE SBIR": "DOE", "DIU": "DIU",
                      "SpaceWERX": "USSF", "SSC Front Door": "USSF", "AFWERX": "USAF", "Space Florida": "Other buyer"}
CUSTOMER_BY_CONSORTIUM = {"SpEC": "USSF", "S2MARTS": "Navy", "Microelectronics Commons": "OSD"}   # NSTXL's
CUSTOMER_BY_OFFICE = (   # words in an agency path (SAM.gov writes them) -> the customer
    ("DEPT OF THE ARMY", "Army"), ("DEPT OF THE NAVY", "Navy"), ("DEPT OF THE AIR FORCE", "USAF"),
    ("SPACE FORCE", "USSF"), ("SPACE SYSTEMS COMMAND", "USSF"),
    ("SPECIAL OPERATIONS COMMAND", "SOCOM"), ("USSOCOM", "SOCOM"), ("DEFENSE INNOVATION UNIT", "DIU"),
    ("DEFENSE ADVANCED RESEARCH PROJECTS AGENCY", "OSD"), ("TEST RESOURCE MANAGEMENT CENTER", "OSD"),
    ("INTELLIGENCE ADVANCED RESEARCH PROJECTS ACTIVITY", "Intelligence community"),
    ("DIRECTOR OF NATIONAL INTELLIGENCE", "Intelligence community"),
    ("NATIONAL AERONAUTICS AND SPACE ADMINISTRATION", "NASA"), ("ENERGY, DEPARTMENT OF", "DOE"),
)
BRANCHES = {"Air Force": "USAF", "Space Force": "USSF"}   # AFWERX's and SpaceWERX's service badges
SMALL_BUSINESS = re.compile(r"small business|\b8\(?a\)?|sdvosb|service-disabled|wosb|women-owned|hubzone", re.IGNORECASE)
PHASE_II_ONLY = {"stratfi", "tacfi", "stratfi/tacfi"}
SPONSOR_PORTALS = {"APFIT"}
ACCESS_TAGS = {"Members only", "Small business set-aside", "Phase II holders only", "Sponsor needed"}


def _extra(row: Mapping[str, Any]) -> dict[str, Any]:
    raw = row.get("extra")
    if isinstance(raw, Mapping):
        return dict(raw)
    try:
        data = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _customers(portal: str, office: str, extra: Mapping[str, Any]) -> set[str]:
    found = {CUSTOMER_BY_PORTAL[portal]} if portal in CUSTOMER_BY_PORTAL else set()
    if office in CUSTOMER_BY_CONSORTIUM:
        found.add(CUSTOMER_BY_CONSORTIUM[office])
    by_office = {customer for words, customer in CUSTOMER_BY_OFFICE if words in office.upper()}
    if "USSF" in by_office:
        by_office.discard("USAF")   # the Space Force's offices sit under the Department of the Air Force
    branches = extra.get(f"{portal.lower()}_branches")
    if isinstance(branches, list) and branches:
        found.discard("USAF")       # the badges say which services a cycle covers
        found |= {BRANCHES[b] for b in branches if b in BRANCHES}
    return found | by_office


def rule_tags(row: Mapping[str, Any], tags: TagList) -> list[str]:
    """The tags a call's own data makes certain, in list order. Never a work tag: that takes judgment."""
    portal = str(row.get("portal") or "")
    kind = " ".join(str(row.get("type") or "").split()).lower()
    office = " ".join(str(row.get("department") or "").split())
    extra = _extra(row)
    found: set[str] = set()
    if portal in TYPE_BY_PORTAL:
        found.add(TYPE_BY_PORTAL[portal])
    elif kind == "solicitation":
        if portal in SOLICITATION_IS_PROPOSAL:
            found.add("Proposal")
    elif kind in TYPE_BY_KIND:
        found.add(TYPE_BY_KIND[kind])
    found |= _customers(portal, office, extra)
    if extra.get("nstxl_members_only") is True:
        found.add("Members only")
    aside = str(row.get("set_aside") or "")
    if SMALL_BUSINESS.search(aside) and not aside.lower().startswith("no "):
        found.add("Small business set-aside")
    if kind in PHASE_II_ONLY:
        found.add("Phase II holders only")
    if portal in SPONSOR_PORTALS:
        found.add("Sponsor needed")
    return ordered(found, tags)


def rule_tag_names() -> set[str]:
    """Every tag a rule can set, so a test can check each is on the list."""
    return (set(TYPE_BY_KIND.values()) | set(TYPE_BY_PORTAL.values()) | {"Proposal"} | set(CUSTOMER_BY_PORTAL.values())
            | set(CUSTOMER_BY_CONSORTIUM.values()) | {customer for _, customer in CUSTOMER_BY_OFFICE}
            | set(BRANCHES.values()) | ACCESS_TAGS)
