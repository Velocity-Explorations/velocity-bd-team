"""The Proposal Register, validated and synced into the ledger's proposals table (Library Phase A, PRO-475)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledger import queries as lq
from library import register

HEADER = list(register.COLUMNS)
VIGILANT = "2026-03-17_vulcan-sof_vigilant-eagle-27"
NORTHERN = "2026-04-03_vulcan-sof_northern-edge-27"


def row(**values: str) -> list[str]:
    return [values.get(column, "") for column in HEADER]


GOOD = row(submission_id=VIGILANT, title="Vigilant Eagle 27", portal="vulcan-sof", type="white_paper",
           submitted_date="2026-03-17", outcome="pending", strength_rating="4", use_as_exemplar="yes",
           themes="C2, edge AI", drive_link="https://drive.google.com/drive/folders/x")


def test_a_valid_row_becomes_a_ledger_row() -> None:
    valid, problems = register.parse_rows(HEADER, [GOOD, [], row()])   # blank rows are ignored
    assert problems == []
    assert len(valid) == 1
    rec = valid[0]
    assert (rec["submission_id"], rec["portal"], rec["type"], rec["outcome"]) == (VIGILANT, "vulcan-sof", "white_paper", "pending")
    assert (rec["strength_rating"], rec["use_as_exemplar"], rec["themes"]) == (4, 1, ["C2", "edge AI"])
    assert rec["submitted_date"] == "2026-03-17" and rec["agency"] is None


def test_dates_typed_the_sheet_way_are_read_as_iso() -> None:
    valid, problems = register.parse_rows(HEADER, [row(submission_id=VIGILANT, submitted_date="3/17/2026",
                                                       outcome_date="10/2/2026")])
    assert problems == [] and (valid[0]["submitted_date"], valid[0]["outcome_date"]) == ("2026-03-17", "2026-10-02")


def test_each_bad_value_is_reported_with_its_sheet_row_and_reason() -> None:
    rows = [row(submission_id="vigilant eagle"),
            row(submission_id="2026-03-17_vulcan_x", portal="vulcan"),
            row(submission_id="2026-03-17_vulcan-sof_x", strength_rating="7"),
            row(submission_id="2026-03-17_vulcan-sof_y", submitted_date="17th March"),
            row(submission_id="2026-03-17_vulcan-sof_z", use_as_exemplar="maybe"),
            row(submission_id="2026-03-17_vulcan-sof_w", outcome="lost?")]
    valid, problems = register.parse_rows(HEADER, rows)
    assert valid == []
    assert [p.row for p in problems] == [2, 3, 4, 5, 6, 7]
    for problem, column in zip(problems, ["submission_id", "portal", "strength_rating", "submitted_date",
                                          "use_as_exemplar", "outcome"]):
        assert column in problem.reason, (problem, column)
    assert "vulcan-sof" in problems[1].reason   # says what the allowed values are


def test_a_header_missing_a_register_column_is_refused() -> None:
    with pytest.raises(register.RegisterError, match="submission_id"):
        register.parse_rows(["title", "portal"], [["A", "vulcan-sof"]])
    renamed = ["Outcome" if column == "outcome" else column for column in HEADER]   # would blank every outcome
    with pytest.raises(register.RegisterError, match="missing outcome"):
        register.parse_rows(renamed, [GOOD])


def test_a_sync_writes_valid_rows_and_leaves_a_broken_rows_ledger_row_alone(ledger_db: str) -> None:
    report = register.sync(HEADER, [GOOD], [VIGILANT])
    assert (report.synced, report.new, report.problems) == (1, 1, [])
    assert report.folders_without_rows == [] and report.rows_without_folders == []
    broken = list(GOOD)
    broken[HEADER.index("strength_rating")] = "7"
    report = register.sync(HEADER, [broken], [VIGILANT])
    assert report.synced == 0 and "strength_rating" in report.problems[0].reason
    stored = lq.list_proposals()[0]
    assert (stored["submission_id"], stored["strength_rating"], stored["use_as_exemplar"]) == (VIGILANT, 4, 1)
    assert stored["synced_at"]


def test_the_report_names_folders_without_rows_and_rows_without_folders(ledger_db: str) -> None:
    report = register.sync(HEADER, [GOOD], [NORTHERN])
    assert report.folders_without_rows == [NORTHERN]
    assert report.rows_without_folders == [VIGILANT]
    text = "\n".join(report.lines())
    assert "1 row synced" in text and NORTHERN in text and "no Register row" in text


def test_the_cli_syncs_from_the_files_the_connectors_wrote(ledger_db: str, tmp_path: Path,
                                                          capsys: pytest.CaptureFixture[str]) -> None:
    rows_file = tmp_path / "register_rows.json"
    rows_file.write_text(json.dumps({"values": [HEADER, GOOD]}), encoding="utf-8")
    folders_file = tmp_path / "folders.json"
    folders_file.write_text(json.dumps({"folders": [VIGILANT]}), encoding="utf-8")
    assert register.main(["sync", "--rows", str(rows_file), "--folders", str(folders_file)]) == 0
    printed = capsys.readouterr().out
    assert "1 row synced" in printed and "0 problems" in printed
    rows_file.write_text(json.dumps({"values": [HEADER, row(submission_id=VIGILANT, portal="vulcan")]}), encoding="utf-8")
    assert register.main(["sync", "--rows", str(rows_file), "--folders", str(folders_file)]) == 1
