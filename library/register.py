"""The Proposal Register: the hand-built sheet of past submissions, synced into the ledger (Library Phase A).

    valid, problems = parse_rows(header, rows)   # each sheet row checked; problems name the row and why
    report = sync(header, rows, folders)         # valid rows upserted into proposals, plus a reconciliation
    python -m library.register sync --rows data/library/register_rows.json --folders data/library/folders.json

The sheet "00 Proposal Register" lives in the BD Proposal Library Drive folder (LIBRARY_DRIVE_FOLDER_ID).
Until gog or a service account can read it from here, Claude reads the sheet and the Submissions folder
names through David's Google connectors and writes them to the two files above; read_rows_file() and
read_folders_file() are the only places that know where the data comes from. A row with a problem is
skipped, so its ledger row keeps its last good values. Conventions: docs/LIBRARY_CONVENTIONS.md.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ledger.queries import upsert_proposal

COLUMNS = ("submission_id", "title", "portal", "agency", "solicitation_id", "type", "role", "partners",
           "submitted_date", "due_date", "requested_value", "outcome", "outcome_date", "award_value",
           "strength_rating", "strength_reason", "why_won_or_lost", "use_as_exemplar", "themes", "drive_link")
PORTALS = ("vulcan-sof", "ssc-front-door", "sam-gov", "nstxl", "diu", "afwerx", "iarpa", "space-force", "doe-sbir",
           "bidnet-co", "bidnet-fl", "other")
TYPES = ("sbir_1", "sbir_2", "sbir_3", "sttr", "rfi", "white_paper", "baa", "pitch", "rfp", "ota", "other")
OUTCOMES = ("won", "lost", "no_award", "pending", "withdrawn", "shortlisted")
CHOICES = {"portal": PORTALS, "type": TYPES, "outcome": OUTCOMES}
DATES = ("submitted_date", "due_date", "outcome_date")
SUBMISSION_ID = re.compile(r"^\d{4}-\d{2}-\d{2}_[a-z-]+_[a-z0-9-]+$")
TEXT = ("title", "agency", "solicitation_id", "role", "partners", "requested_value", "award_value",
        "strength_reason", "why_won_or_lost", "drive_link")


class RegisterError(ValueError):
    """The sheet cannot be read at all, for example a header column is missing or renamed."""


@dataclass(frozen=True)
class Problem:
    row: int        # the sheet's row number; the header is row 1
    submission_id: str
    reason: str


@dataclass
class Report:
    synced: int = 0
    new: int = 0
    problems: list[Problem] = field(default_factory=list)
    folders_without_rows: list[str] = field(default_factory=list)
    rows_without_folders: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        out = [f"{self.synced} row{'' if self.synced == 1 else 's'} synced ({self.new} new), "
               f"{len(self.problems)} problem{'' if len(self.problems) == 1 else 's'}"]
        out += [f"  row {p.row} ({p.submission_id or 'no id'}): {p.reason}" for p in self.problems]
        out += [f"Submissions folder with no Register row: {name}" for name in self.folders_without_rows]
        out += [f"Register row with no Submissions folder: {sid}" for sid in self.rows_without_folders]
        return out


def _date(value: str) -> str:
    for pattern in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, pattern).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(value)


def _check(cells: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
    """One row's values as ledger columns, and what is wrong with it."""
    reasons: list[str] = []
    rec: dict[str, Any] = {"submission_id": cells.get("submission_id", "")}
    if not SUBMISSION_ID.match(rec["submission_id"]):
        reasons.append("submission_id must look like YYYY-MM-DD_portal_short-title, lower case")
    for name, allowed in CHOICES.items():
        value = cells.get(name, "")
        if value and value not in allowed:
            reasons.append(f"{name} '{value}' is not one of {', '.join(allowed)}")
        rec[name] = value or None
    for name in DATES:
        value = cells.get(name, "")
        try:
            rec[name] = _date(value) if value else None
        except ValueError:
            reasons.append(f"{name} '{value}' is not a date (YYYY-MM-DD)")
    rating = cells.get("strength_rating", "")
    rec["strength_rating"] = None
    if rating:
        if rating.isdigit() and 1 <= int(rating) <= 5:
            rec["strength_rating"] = int(rating)
        else:
            reasons.append(f"strength_rating '{rating}' must be 1 to 5")
    exemplar = cells.get("use_as_exemplar", "").lower()
    if exemplar not in ("", "yes", "no"):
        reasons.append(f"use_as_exemplar '{cells.get('use_as_exemplar')}' must be yes or no")
    rec["use_as_exemplar"] = 1 if exemplar == "yes" else 0
    themes = cells.get("themes", "")
    rec["themes"] = [t.strip() for t in themes.split(",") if t.strip()] if themes else None
    for name in TEXT:
        rec[name] = cells.get(name, "") or None
    return rec, reasons


def parse_rows(header: Sequence[str], rows: Sequence[Sequence[str]]) -> tuple[list[dict[str, Any]], list[Problem]]:
    """The rows the ledger can take, and a problem for each one it can't. Columns are found by name."""
    names = [str(h).strip() for h in header]
    missing = [column for column in COLUMNS if column not in names]
    if missing:   # a renamed column would otherwise blank its value in every ledger row
        raise RegisterError(f"the Register's header is missing {', '.join(missing)}; "
                            "the sync finds each column by its name")
    valid: list[dict[str, Any]] = []
    problems: list[Problem] = []
    for number, values in enumerate(rows, start=2):
        cells = {name: str(values[i]).strip() if i < len(values) else "" for i, name in enumerate(names)}
        if not any(cells.values()):
            continue
        rec, reasons = _check(cells)
        if reasons:
            problems.append(Problem(number, rec["submission_id"], "; ".join(reasons)))
        else:
            valid.append(rec)
    return valid, problems


def sync(header: Sequence[str], rows: Sequence[Sequence[str]], folders: Sequence[str]) -> Report:
    """Upsert every valid row into proposals and reconcile the Register with the Submissions folders."""
    valid, problems = parse_rows(header, rows)
    report = Report(problems=problems)
    for rec in valid:
        report.synced += 1
        report.new += upsert_proposal(rec)
    ids = {rec["submission_id"] for rec in valid} | {p.submission_id for p in problems if p.submission_id}
    report.folders_without_rows = sorted(set(folders) - ids)
    report.rows_without_folders = sorted(ids - set(folders))
    return report


def read_rows_file(path: Path) -> tuple[list[str], list[list[str]]]:
    """The sheet as the Sheets API returns it: {"values": [header, row, ...]}."""
    values = json.loads(path.read_text(encoding="utf-8")).get("values") or []
    if not values:
        raise RegisterError(f"{path.name} holds no rows")
    return [str(v) for v in values[0]], [[str(v) for v in r] for r in values[1:]]


def read_folders_file(path: Path) -> list[str]:
    """The Submissions folder names: {"folders": [name, ...]}."""
    return [str(name) for name in json.loads(path.read_text(encoding="utf-8")).get("folders") or []]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m library.register", description="Sync the Proposal Register")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("sync", help="validate the Register and upsert its rows into the ledger")
    run.add_argument("--rows", required=True, type=Path, help='the sheet as JSON: {"values": [header, row, ...]}')
    run.add_argument("--folders", required=True, type=Path, help='Submissions folder names as JSON: {"folders": [...]}')
    args = parser.parse_args(argv)
    try:
        header, rows = read_rows_file(args.rows)
        report = sync(header, rows, read_folders_file(args.folders))
    except RegisterError as exc:
        print(f"Cannot sync: {exc}")
        return 2
    print("\n".join(report.lines()))
    return 1 if report.problems else 0


if __name__ == "__main__":
    sys.exit(main())
