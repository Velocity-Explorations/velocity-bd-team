"""One SAM.gov notice to one `calls` row, and the checks that cost no request. Pure: no network, no ledger.

    rules = load_rules(SEARCH_PATH)          # NAICS codes, offices, notice types and set-asides from search.yaml
    reason = keep(raw, rules)                # None, or why the notice is dropped
    rec = build_record(raw, now, text)       # dict matching the ledger's calls columns

The search result carries everything but the description, which is a link of its own. Without
`description`, the record leaves that column out, so refreshing a stored notice keeps its text.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

PORTAL = "SAM.gov"
ID_PREFIX = "samgov-"
DESCRIPTION_CHARS = 4000
NO_SET_ASIDE = "NONE"
HERE = Path(__file__).resolve().parent
SEARCH_PATH = HERE / "search.yaml"       # what to ask for and keep
KEYWORDS_PATH = HERE / "keywords.yaml"   # the relevance filter, shared with the pipeline
# SAM.gov's notice types as calls.type. Solicitation and combined synopsis both ask for a response.
TYPES = {
    "Solicitation": "Solicitation",
    "Combined Synopsis/Solicitation": "Solicitation",
    "Presolicitation": "Presolicitation",
    "Sources Sought": "Sources sought",
    "Special Notice": "Special notice",
}


@dataclass(frozen=True)
class Rules:
    naics_codes: list[str]
    notice_types: set[str]
    set_asides: set[str]
    offices: list[str] = field(default_factory=list)   # searched whatever their NAICS codes


def load_rules(path: Path = SEARCH_PATH) -> Rules:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for key in ("naics_codes", "notice_types", "set_asides"):
        if not isinstance(data.get(key), list) or not data[key]:
            raise ValueError(f"{path.name}: '{key}' must be a list")
    offices = data.get("offices") or []
    if not isinstance(offices, list):
        raise ValueError(f"{path.name}: 'offices' must be a list")
    return Rules(naics_codes=[str(c).strip() for c in data["naics_codes"]],
                 notice_types={str(t).strip() for t in data["notice_types"]},
                 set_asides={str(s).strip().upper() for s in data["set_asides"]},
                 offices=[str(o).strip() for o in offices if str(o).strip()])


def notice_id(raw: dict[str, Any]) -> str:
    return str(raw.get("noticeId") or "").strip().lower()


def set_aside_code(raw: dict[str, Any]) -> str:
    return str(raw.get("typeOfSetAside") or "").strip().upper() or NO_SET_ASIDE


def keep(raw: dict[str, Any], rules: Rules) -> str | None:
    """Why this notice is dropped before any request is spent on it, or None to keep it."""
    kind = str(raw.get("type") or "").strip()
    if kind not in rules.notice_types:
        return f"type {kind or 'unknown'}"
    code = set_aside_code(raw)
    if code not in rules.set_asides:
        return f"set-aside {code}"
    return None


def deadline(raw: dict[str, Any]) -> datetime | None:
    """The response deadline; one without an offset is read as UTC."""
    try:
        due = datetime.fromisoformat(str(raw.get("responseDeadLine") or ""))
    except ValueError:
        return None
    return due if due.tzinfo else due.replace(tzinfo=timezone.utc)


def _place(raw: dict[str, Any]) -> str | None:
    pop = raw.get("placeOfPerformance") or {}
    if not isinstance(pop, dict):
        return None
    city = (pop.get("city") or {}).get("name") if isinstance(pop.get("city"), dict) else pop.get("city")
    state = pop.get("state") or {}
    state = (state.get("code") or state.get("name")) if isinstance(state, dict) else state
    return ", ".join(str(p) for p in (city, state) if p) or None


def _contacts(raw: dict[str, Any]) -> list[dict[str, Any]] | None:
    found = []
    for person in raw.get("pointOfContact") or []:
        if isinstance(person, dict):
            found.append({"name": person.get("fullName") or person.get("fullname"), "email": person.get("email"),
                          "phone": person.get("phone"), "role": person.get("type")})
    return found or None


def build_record(raw: dict[str, Any], now: datetime, description: str | None = None) -> dict[str, Any]:
    nid = notice_id(raw)
    if not nid:
        raise ValueError("the notice has no noticeId")
    kind = str(raw.get("type") or "").strip()
    due = deadline(raw)
    closed = str(raw.get("active") or "Yes").strip().lower() != "yes" or (due is not None and due < now)
    extra = {
        "samgov_notice_id": nid,
        "samgov_solicitation_number": raw.get("solicitationNumber"),
        "samgov_type": kind,
        "samgov_base_type": raw.get("baseType"),
        "samgov_set_aside_code": set_aside_code(raw),
        "samgov_classification_code": raw.get("classificationCode"),
        "samgov_naics_codes": raw.get("naicsCodes"),
        "samgov_place_of_performance": _place(raw),
        "samgov_contacts": _contacts(raw),
        "samgov_attachments": [str(link) for link in raw.get("resourceLinks") or []] or None,
        "samgov_additional_info": raw.get("additionalInfoLink"),
        "samgov_closed": closed,
    }
    record: dict[str, Any] = {
        "id": f"{ID_PREFIX}{nid}",
        "portal": PORTAL,
        "title": " ".join(str(raw.get("title") or "").split()) or "(untitled notice)",
        "type": TYPES.get(kind, kind or "Notice"),
        "department": " / ".join(p.strip() for p in str(raw.get("fullParentPathName") or "").split(".") if p.strip()),
        "naics_code": str(raw.get("naicsCode") or ""),
        "set_aside": raw.get("typeOfSetAsideDescription") or "",
        "posted_date": str(raw.get("postedDate") or "")[:10],
        "due_date": str(raw.get("responseDeadLine") or ""),
        "url": raw.get("uiLink") or f"https://sam.gov/opp/{nid}/view",
        "source_type": "api",
        "extra": {k: (v if v not in ("", []) else None) for k, v in extra.items()},
    }
    if description is not None:
        record["description"] = description
    return record
