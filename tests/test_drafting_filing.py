"""Filing a submitted proposal in the Proposal Library (phase 6b, part 3): the folder renamed to the day it went in, the
final version copied into 01_submitted/, the Register row added; and once its result is recorded, the outcome note in
03_outcome/ and the outcome on the Register row. Fake Drive and Sheets stand in; no test reaches Google."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from drafting import drive, worker
from ledger import queries as lq
from ledger.db import q, tx
from tests.test_drafting_drive import FOLDER, FakeDrive
from tests.test_drafting_worker import Model, _pursuit

HEADER = ["submission_id", "title", "portal", "agency", "solicitation_id", "type", "role", "partners", "submitted_date",
          "due_date", "requested_value", "outcome", "outcome_date", "award_value", "strength_rating", "strength_reason",
          "why_won_or_lost", "use_as_exemplar", "themes", "drive_link"]


class FakeSheets:
    """One spreadsheet tab as a list of rows, header first."""

    def __init__(self) -> None:
        self.rows: list[list[str]] = [list(HEADER), ["2026-03-17_vulcan-sof_vigilant-eagle-27", "Vigilant Eagle 27", "vulcan-sof"]]

    def values(self, sheet_id: str, tab: str) -> list[list[str]]:
        assert tab == drive.REGISTER_TAB
        return [list(r) for r in self.rows]

    def append(self, sheet_id: str, tab: str, row: list[str]) -> None:
        self.rows.append(list(row))

    def update(self, sheet_id: str, tab: str, row_number: int, cells: dict[int, str]) -> None:
        row = self.rows[row_number - 1]
        row.extend([""] * (len(HEADER) - len(row)))
        for column, value in cells.items():
            row[column] = value

    def cell(self, submission_id: str, name: str) -> str:
        row = next(r for r in self.rows if r and r[0] == submission_id)
        index = HEADER.index(name)
        return row[index] if index < len(row) else ""


@pytest.fixture
def google(monkeypatch: pytest.MonkeyPatch) -> tuple[FakeDrive, FakeSheets]:
    found, sheets = FakeDrive(), FakeSheets()
    found.add(drive.REGISTER, drive.SHEET_MIME, found.library)
    monkeypatch.setattr(drive, "client", lambda: found)
    monkeypatch.setattr(drive, "sheets_client", lambda: sheets)
    monkeypatch.setattr(drive, "library_id", lambda: found.library)
    return found, sheets


@pytest.fixture
def local(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(worker, "DATA_DIR", tmp_path / "drafting")
    monkeypatch.setattr(worker, "LOCK_FILE", tmp_path / "drafting" / "worker.lock")
    monkeypatch.setattr(worker, "WORK_ROOT", tmp_path / "drafting" / "pursuits")
    monkeypatch.setattr(worker, "_refreshed_at", [])   # each test's idle worker starts with no index refresh behind it
    return tmp_path


def _submitted(pursuit_id: int, at: str = "2026-11-24T22:40:00Z", gate: bool = True) -> None:
    """The pursuit marked submitted, as the dashboard's Mark submitted leaves it."""
    now = "2026-11-24T22:40:00Z"
    with tx() as conn:
        if gate:
            q(conn, "INSERT INTO pursuit_steps (pursuit_id, step, attempt, state, requested_by, decision, decided_by, decided_at, "
                    "queued_at, updated_at) VALUES (?, 'submit', 1, 'approved', 'David Wood', 'submitted', 'David Wood', ?, ?, ?)",
              (pursuit_id, now, now, now))
        q(conn, "UPDATE pursuits SET state = 'submitted', current_step = 'submit', submitted_at = ?, submitted_by = 'David Wood', "
                "confirmation_number = 'SAM-123' WHERE id = ?", (at, pursuit_id))


def test_a_submitted_proposal_is_filed_in_the_library(ledger_db: str, local: Path, google: tuple[FakeDrive, FakeSheets]) -> None:
    found, sheets = google
    pursuit_id = _pursuit()
    worker.work_once(generate=Model())                       # Discovery makes the folder, named for the day it started
    work = local / "drafting" / "pursuits" / f"pursuit-{pursuit_id}"
    (work / "draft_final.docx").write_bytes(b"the final version")
    _submitted(pursuit_id)
    assert worker.housekeeping(0.0)["filed"] == 1
    pursuit = lq.get_pursuit(pursuit_id)
    day = "2026-11-24"   # 22:40 UTC is 15:40 in Denver
    assert pursuit["drive_folder_name"] == f"Submissions/{day}_sam-gov_edge-ai-sam-1"
    assert pursuit["submission_id"] == f"{day}_sam-gov_edge-ai-sam-1"
    assert found.path_of(pursuit["drive_folder_id"]) == pursuit["drive_folder_name"]
    submitted = found.find(pursuit["drive_folder_id"], "01_submitted", folder=True)
    [copy] = found.children(submitted["id"])
    assert (copy["name"], copy["content"]) == ("white-paper.docx", b"the final version")
    row = sheets.rows[-1]
    cells = dict(zip(HEADER, row))
    assert {k: cells[k] for k in ("submission_id", "title", "portal", "agency", "type", "submitted_date", "due_date", "outcome")} == {
        "submission_id": f"{day}_sam-gov_edge-ai-sam-1", "title": "Edge AI sam-1", "portal": "sam-gov",
        "agency": "DEPT OF THE ARMY", "type": "white_paper", "submitted_date": day, "due_date": "2026-12-01", "outcome": "pending"}
    assert cells["drive_link"].startswith("https://drive.example.invalid/")
    assert any(e["kind"] == "filed" for e in lq.pursuit_events(pursuit_id))
    assert worker.housekeeping(0.0)["filed"] == 0             # filed once
    assert len(sheets.rows) == 3


def test_the_result_goes_to_03_outcome_and_the_register(ledger_db: str, local: Path, google: tuple[FakeDrive, FakeSheets]) -> None:
    found, sheets = google
    pursuit_id = _pursuit()
    worker.work_once(generate=Model())
    _submitted(pursuit_id)
    worker.housekeeping(0.0)
    with tx() as conn:
        q(conn, "UPDATE pursuits SET result = 'cancelled_by_agency', result_at = '2027-02-01T17:00:00Z', result_by = 'David Wood', "
                "debrief = 'The topic was withdrawn.', next_time = 'Ask about funding first.' WHERE id = ?", (pursuit_id,))
    assert worker.housekeeping(1.0)["results"] == 1
    pursuit = lq.get_pursuit(pursuit_id)
    outcome = found.find(pursuit["drive_folder_id"], "03_outcome", folder=True)
    [note] = found.children(outcome["id"])
    assert note["name"] == "outcome.docx" and note["content"]
    assert sheets.cell(pursuit["submission_id"], "outcome") == "no_award"           # cancelled by the agency
    assert sheets.cell(pursuit["submission_id"], "outcome_date") == "2027-02-01"
    assert sheets.cell(pursuit["submission_id"], "why_won_or_lost") == "The topic was withdrawn."
    assert worker.housekeeping(2.0)["results"] == 0


def test_what_people_wrote_on_the_register_row_is_kept(ledger_db: str, local: Path, google: tuple[FakeDrive, FakeSheets]) -> None:
    found, sheets = google
    pursuit_id = _pursuit()
    worker.work_once(generate=Model())
    _submitted(pursuit_id)
    worker.housekeeping(0.0)
    submission = lq.get_pursuit(pursuit_id)["submission_id"]
    sheets.update("x", drive.REGISTER_TAB, len(sheets.rows), {HEADER.index("why_won_or_lost"): "Strong team, weak price"})
    with tx() as conn:
        q(conn, "UPDATE pursuits SET result = 'lost', result_at = '2027-02-01T17:00:00Z', debrief = 'Price' WHERE id = ?", (pursuit_id,))
    worker.housekeeping(1.0)
    assert sheets.cell(submission, "why_won_or_lost") == "Strong team, weak price"
    assert sheets.cell(submission, "outcome") == "lost"


def test_a_call_marked_submitted_outside_the_workspace_is_not_filed(ledger_db: str, local: Path,
                                                                     google: tuple[FakeDrive, FakeSheets]) -> None:
    found, sheets = google
    pursuit_id = _pursuit()
    worker.work_once(generate=Model())
    _submitted(pursuit_id, gate=False)
    assert worker.housekeeping(0.0)["filed"] == 0
    assert len(sheets.rows) == 2


def test_a_submission_without_a_folder_or_a_final_version_is_still_filed(ledger_db: str, local: Path,
                                                                           google: tuple[FakeDrive, FakeSheets]) -> None:
    found, sheets = google
    pursuit_id = _pursuit()
    _submitted(pursuit_id)
    assert worker.housekeeping(0.0)["filed"] == 1
    pursuit = lq.get_pursuit(pursuit_id)
    assert pursuit["drive_folder_name"] == "Submissions/2026-11-24_sam-gov_edge-ai-sam-1"
    assert found.children(found.find(pursuit["drive_folder_id"], "01_submitted", folder=True)["id"]) == []
    assert sheets.rows[-1][0] == "2026-11-24_sam-gov_edge-ai-sam-1"
    assert any("no final version" in e["text"] for e in lq.pursuit_events(pursuit_id) if e["kind"] == "filed")


def test_the_register_row_needs_its_columns_by_name() -> None:
    assert drive.register_row(["title", "submission_id", "extra"], {"submission_id": "x", "title": "T"}) == ["T", "x", ""]
    assert drive.register_portal("SAM.gov") == "sam-gov" and drive.register_portal("SpaceWERX") == "other"
    assert drive.volume_name("SBIR or STTR technical volume") == "technical-volume" and drive.volume_name("Other") == "submission"
