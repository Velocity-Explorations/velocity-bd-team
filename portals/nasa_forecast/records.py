"""One row of NASA's acquisition forecast to one `calls` row. Pure: no network, no ledger.

    rec = build_record(row, now)

A forecast row is a planned buy, not a solicitation: it has no deadline, only the quarters NASA
expects to release the solicitation and to award. The row's own words (AcquisitionStatus,
AwardedOrWithdrawn, AcquisitionPhase) say when it is no longer coming.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

PORTAL = "NASA Forecast"
ID_PREFIX = "nasa-"
PAGE_URL = "https://www.hq.nasa.gov/office/procurement/forecast/NAF.html"   # the forecast, viewable by people
DESCRIPTION_CHARS = 4000
DONE = {"awarded", "withdrawn", "cancelled", "canceled"}


def _get(row: dict[str, Any], name: str) -> str:
    return " ".join(str(row.get(name) or "").split())


def when(quarter: str, year: str) -> str:
    """ "Q3 FY2026", "FY2026", or empty."""
    if not year:
        return ""
    return f"{quarter} FY{year}" if quarter else f"FY{year}"


def is_closed(row: dict[str, Any]) -> bool:
    awarded_or_withdrawn = _get(row, "AwardedOrWithdrawn").lower()
    return (_get(row, "AcquisitionStatus").lower() in DONE or _get(row, "AcquisitionPhase").lower() in DONE
            or awarded_or_withdrawn not in ("", "n/a"))


def _contacts(row: dict[str, Any]) -> list[dict[str, str]] | None:
    found = []
    for name_col, email_col, role in (("Tech POC Name", "TechnicalPOC", "technical"),
                                      ("SmallBusinessSpecialistPOC", "SmallBusinessSpecialistEmail", "small business")):
        name, email = _get(row, name_col), _get(row, email_col)
        if name or email:
            found.append({"name": name, "email": email, "role": role})
    return found or None


def describe(row: dict[str, Any], solicitation: str, award: str) -> str:
    office = _get(row, "BuyingOffice")
    timing = [f"solicitation expected {solicitation}"] if solicitation else []
    timing += [f"award expected {award}"] if award else []
    lead = "A NASA acquisition forecast" + (f" from {office}" if office else "")
    sentences = [lead + (f": {', '.join(timing)}." if timing else ".")]
    value = _get(row, "EstimatedContractValue")
    terms = [_get(row, "NewOrRecompete"), f"estimated value {value}" if value else "", _get(row, "ContractType"),
             _get(row, "ExtentCompeted")]
    if any(terms):
        sentences.append(", ".join(t for t in terms if t) + ".")
    code, naics = _get(row, "NAICS"), _get(row, "NAICS Description")
    if code:
        sentences.append(f"NAICS {code}" + (f" ({naics})." if naics else "."))
    body = [" ".join(sentences)] + [text for text in (_get(row, "Summary"), _get(row, "Description")) if text]
    return "\n\n".join(body)[:DESCRIPTION_CHARS]


def build_record(row: dict[str, Any], now: datetime) -> dict[str, Any]:
    source_id = _get(row, "SourceID")
    if not source_id:
        raise ValueError("the forecast row has no SourceID")
    solicitation = when(_get(row, "QtrSolOrNOFORelease"), _get(row, "FYofSolOrNOFORelease"))
    award = when(_get(row, "Anticipated Qtr of Award"), _get(row, "AnticipatedFYAward"))
    office = _get(row, "BuyingOffice")
    return {
        "id": f"{ID_PREFIX}{source_id}",
        "portal": PORTAL,
        "title": _get(row, "TitleOfRequirement") or f"NASA forecast {source_id}",
        "type": "Forecast",
        "department": f"NASA {office}" if office else "NASA",
        "naics_code": _get(row, "NAICS"),
        "set_aside": _get(row, "SetAsideType"),
        "posted_date": "",
        "due_date": "",
        "description": describe(row, solicitation, award),
        "url": PAGE_URL,
        "source_type": "forecast",
        "extra": {
            "nasa_source_id": source_id,
            "nasa_status": _get(row, "AcquisitionStatus") or None,
            "nasa_phase": _get(row, "AcquisitionPhase") or None,
            "nasa_solicitation_expected": solicitation or None,
            "nasa_award_expected": award or None,
            "nasa_estimated_value": _get(row, "EstimatedContractValue") or None,
            "nasa_requirement": _get(row, "TypeOfRequirement") or None,
            "nasa_contacts": _contacts(row),
            "nasa_no_deadline": True,   # a forecast has no deadline by design
            "nasa_closed": is_closed(row),
        },
    }
