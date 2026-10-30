"""A made-up 01 Company Reference, shaped like the real files on Drive (PRO-565). Nothing here is a real fact:
the real ones live only in Drive, because the repo is public."""
from __future__ import annotations

EN = chr(0x2013)   # the real files use en dashes; this file may not
FACTS_DOC = r"""# 00 Company Facts, an example

**Handling:** INTERNAL. Items marked **SENSITIVE** need approval before external use.

## 1\. Legal & registration

| ID | Fact | Value | Entity | Source | Last verified | Sensitivity |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| F-01 | Legal name | Example Velocity, Inc. | Velocity | [Signed form](https://example.invalid/form) | 2026-10-30 | internal |
| F-02 | UEI | TESTUEI00001 (matches public data) | Velocity | [Registry](https://example.invalid/uei) | 2026-10-30 | internal |
| F-03 | CAGE | 0TST1 (05 CF-01) | Velocity | [Contract](https://example.invalid/contract) | 2026-10-30 | internal |
| F-06 | Size | WOSB certified (05 CF-14) | Velocity | David | 2026-10-30 | internal |
| F-12 | Facility clearance | Secret FCL granted | Velocity | David | 2026-10-30 | SENSITIVE |
| F-14 | Legal name | EXAMPLE HOVERSLAM LLC | Hoverslam | [Registry](https://example.invalid/hs) | 2026-10-30 | internal |
| F-49 | SAM registration status | Renewal in progress (05 CF-26) | Hoverslam | David | 2026-10-30 | internal |

## 7\. Boilerplate

> Example Velocity builds software for operators \$5 cheaper.

## 8\. Key personnel bios

| Name | Entity | Title/role | Short bio | Source |
| :---- | :---- | :---- | :---- | :---- |
| Pat Former | Velocity | Engineer | Wrote the old system | x |
"""

BRAND_GUIDE = """# Brand Guide

## Names

| Use | Never |
| :---- | :---- |
| Echo, in title case | ECHO |
"""

SHEETS = {
    "past_performance": {"Past Performance": [
        ["pp_id", "entity", "customer_agency", "value_usd", "status", "results_metrics", "evidence_links", "sensitivity"],
        ["PP-01", "Velocity", "Example Space Wing", "100000", "complete", "Cut launch staffing from 20 to 2",
         "https://example.invalid/pp1", "internal"],
        ["PP-02", "Velocity", "Example Corp", "5000", "active", "", "", f"SENSITIVE {EN} commercial pricing; internal only"],
    ]},
    "products": {"Products": [
        ["product_id", "entity", "name", "trl", "trl_source", "notes", "sources"],
        ["PR-01", "Velocity", "Echo", "8", "per David (05 CF-05)", "Write Echo in title case", "https://example.invalid/echo"],
        ["PR-02", "Hoverslam", "Example Audio", "4", "", "", ""],
        ["PR-03", "Velocity", "Example Scout", "5", "05 CF-27", "", ""],
    ]},
    "people": {"People": [
        ["person_id", "name", "entity", "title_role", "clearance_level (SENSITIVE)", "bio_summary", "bio_link"],
        ["PE-01", "Alex Example", "Velocity", "President", "Secret", "Leads design", "https://example.invalid/bio1"],
        ["PE-02", "Pat Former", f"Velocity {EN} FORMER EMPLOYEE (left 2025)", "Engineer", "", "Wrote the old system", ""],
        ["PE-03", "Dr. Robin Partner", f"PARTNER {EN} Example University (not Velocity staff)", "Co-investigator", "", "Speech research", ""],
    ]},
    "conflicts": {"Conflicts": [
        ["conflict_id", "topic", "entity", "status", "recommended_resolution"],
        ["CF-01", "CAGE code", "Velocity", "resolved", "Use 0TST1"],
        ["CF-05", "Echo TRL", "Velocity", "resolved (follow-up: update the deck)", "TRL 8"],
        ["CF-14", "WOSB certification", "Velocity", "confirmed by David, evidence pending", "Get the SBA letter"],
        ["CF-26", "Hoverslam registrations lapsed", "Hoverslam", "in progress (owner: David)", "Renew SAM"],
        ["CF-27", "Scout maturity", "Velocity", "open", "Confirm the TRL"],
    ]},
}


def files() -> dict[str, object]:
    """What facts.read_drive returns: each doc as markdown, each sheet as {tab: rows}."""
    return {"facts": FACTS_DOC, "brand": BRAND_GUIDE, **SHEETS}
