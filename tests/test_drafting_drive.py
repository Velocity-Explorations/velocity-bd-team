"""The proposal workspace's Google Drive (phase 6b): each pursuit's folder in the Proposal Library, its Word files in
02_working/, the index of past work for Builds on, and the no-go move. A fake Drive stands in; no test reaches Google."""
from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any

import pytest

from drafting import drive, worker
from ledger import queries as lq
from tests.test_drafting_worker import Model, _pursuit

FOLDER = drive.FOLDER_MIME
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class FakeDrive:
    """An in-memory Drive with the calls the worker makes. Nothing is ever deleted, as on the shared drive."""

    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}
        self.ids = (f"id{n}" for n in itertools.count(1))
        self.fail = False
        self.library = self.add("BD Proposal Library", FOLDER, None)["id"]
        self.submissions = self.add("Submissions", FOLDER, self.library)["id"]

    def add(self, name: str, mime: str, parent: str | None, modified: str = "2026-10-01T00:00:00Z") -> dict[str, Any]:
        item_id = next(self.ids)
        item = {"id": item_id, "name": name, "mimeType": mime, "parents": [parent] if parent else [], "trashed": False,
                "webViewLink": f"https://drive.example.invalid/{item_id}", "modifiedTime": modified, "content": b""}
        self.items[item_id] = item
        return item

    def _check(self) -> None:
        if self.fail:
            raise drive.DriveError("Drive answered 503")

    def get(self, item_id: str, fields: str = "") -> dict[str, Any]:
        self._check()
        return self.items[item_id]

    def children(self, parent_id: str) -> list[dict[str, Any]]:
        self._check()
        return [i for i in self.items.values() if parent_id in i["parents"] and not i["trashed"]]

    def find(self, parent_id: str, name: str, folder: bool) -> dict[str, Any] | None:
        return next((i for i in self.children(parent_id) if i["name"] == name and (i["mimeType"] == FOLDER) == folder), None)

    def make_folder(self, parent_id: str, name: str) -> dict[str, Any]:
        self._check()
        return self.add(name, FOLDER, parent_id)

    def upload(self, parent_id: str, path: Path, name: str, mime: str) -> dict[str, Any]:
        self._check()
        found = self.find(parent_id, name, folder=False) or self.add(name, mime, parent_id)
        found["content"] = path.read_bytes()
        return found

    def move(self, item_id: str, to_parent: str) -> None:
        self._check()
        self.items[item_id]["parents"] = [to_parent]

    def path_of(self, item_id: str) -> str:
        parts = []
        while item_id != self.library:
            item = self.items[item_id]
            parts.append(item["name"])
            item_id = item["parents"][0]
        return "/".join(reversed(parts))


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeDrive:
    found = FakeDrive()
    monkeypatch.setattr(drive, "client", lambda: found)
    monkeypatch.setattr(drive, "library_id", lambda: found.library)
    return found


@pytest.fixture
def local(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(worker, "DATA_DIR", tmp_path / "drafting")
    monkeypatch.setattr(worker, "LOCK_FILE", tmp_path / "drafting" / "worker.lock")
    monkeypatch.setattr(worker, "WORK_ROOT", tmp_path / "drafting" / "pursuits")
    return tmp_path


def test_tests_never_reach_live_drive() -> None:
    assert drive.client() is None   # tests/conftest.py, whatever .env says


def test_a_pursuits_folder_is_named_for_the_library() -> None:
    assert drive.folder_name("2026-10-29", "SAM.gov", "Edge AI for C2 software") == "2026-10-29_sam-gov_edge-ai-for"
    assert drive.folder_name("2026-10-29", "SSC Front Door", None) == "2026-10-29_ssc-front-door_untitled"


def test_the_folder_and_its_four_parts_are_made_once(fake: FakeDrive) -> None:
    made = drive.pursuit_folder(fake, fake.library, "2026-10-29_sam-gov_edge-ai-for", taken=set())
    assert fake.path_of(made["id"]) == "Submissions/2026-10-29_sam-gov_edge-ai-for"
    assert sorted(i["name"] for i in fake.children(made["id"])) == ["00_solicitation", "01_submitted", "02_working", "03_outcome"]
    again = drive.pursuit_folder(fake, fake.library, "2026-10-29_sam-gov_edge-ai-for", taken=set())
    assert again["id"] == made["id"] and len(fake.children(made["id"])) == 4
    other = drive.pursuit_folder(fake, fake.library, "2026-10-29_sam-gov_edge-ai-for", taken={made["id"]})
    assert fake.items[other["id"]]["name"] == "2026-10-29_sam-gov_edge-ai-for-2"   # another pursuit has that name


def test_a_file_goes_into_02_working_and_a_second_save_replaces_it(fake: FakeDrive, tmp_path: Path) -> None:
    folder = drive.pursuit_folder(fake, fake.library, "2026-10-29_sam-gov_edge-ai-for", taken=set())
    page = tmp_path / "draft_v1.docx"
    page.write_bytes(b"one")
    first = drive.upload(fake, folder["id"], page)
    page.write_bytes(b"two")
    second = drive.upload(fake, folder["id"], page)
    assert first == second == {"id": first["id"], "link": f"https://drive.example.invalid/{first['id']}"}
    assert fake.path_of(first["id"]) == "Submissions/2026-10-29_sam-gov_edge-ai-for/02_working/draft_v1.docx"
    assert fake.items[first["id"]]["mimeType"] == DOCX and fake.items[first["id"]]["content"] == b"two"


def test_the_library_is_indexed_for_builds_on(fake: FakeDrive) -> None:
    past = fake.add("2026-03-17_vulcan-sof_vigilant-eagle-27", FOLDER, fake.submissions, "2026-03-17T12:00:00Z")
    submitted = fake.add("01_submitted", FOLDER, past["id"])
    fake.add("white-paper.pdf", "application/pdf", submitted["id"])
    fake.add("02_working", FOLDER, past["id"])
    no_go = fake.add("_no-go", FOLDER, fake.submissions)
    fake.add("2026-05-01_sam-gov_dropped", FOLDER, no_go["id"])
    reference = fake.add("01 Company Reference", FOLDER, fake.library)
    bios = fake.add("Bios", FOLDER, reference["id"])
    fake.add("David Wood bio.docx", DOCX, bios["id"])
    fake.add("Capabilities.pdf", "application/pdf", reference["id"])
    fake.add("00 README", "application/vnd.google-apps.document", fake.library)
    rows = drive.index_library(fake, fake.library)
    assert sorted(r["path"] for r in rows) == [
        "01 Company Reference/Bios/David Wood bio.docx", "01 Company Reference/Capabilities.pdf",
        "Submissions/2026-03-17_vulcan-sof_vigilant-eagle-27", "Submissions/2026-03-17_vulcan-sof_vigilant-eagle-27/01_submitted/white-paper.pdf"]
    folder = next(r for r in rows if r["name"] == "2026-03-17_vulcan-sof_vigilant-eagle-27")
    assert (folder["mime"], folder["web_link"], folder["modified_at"]) == (FOLDER, past["webViewLink"], "2026-03-17T12:00:00Z")


# ------------------------------------------------------------------------------ the worker with Drive

def test_the_worker_makes_the_folder_and_saves_each_steps_word_file_there(ledger_db: str, local: Path, fake: FakeDrive) -> None:
    pursuit_id = _pursuit()
    assert worker.work_once(generate=Model()) is True
    pursuit = lq.get_pursuit(pursuit_id)
    assert pursuit["drive_folder_name"].startswith("Submissions/") and pursuit["drive_folder_name"].endswith("_sam-gov_edge-ai-sam-1")
    assert fake.path_of(pursuit["drive_folder_id"]) == pursuit["drive_folder_name"]
    entry = json.loads(lq.pursuit_steps(pursuit_id)[0]["files"])[0]
    assert entry["link"].startswith("https://drive.example.invalid/")
    assert fake.path_of(entry["drive_id"]).endswith("/02_working/discovery.docx")
    assert any(e["kind"] == "drive" and e["text"] == f"Made the Drive folder {pursuit['drive_folder_name']}"
               for e in lq.pursuit_events(pursuit_id))


def test_a_drive_failure_keeps_the_files_on_the_pc_and_the_step_ready(ledger_db: str, local: Path, fake: FakeDrive) -> None:
    pursuit_id = _pursuit()
    fake.fail = True
    assert worker.work_once(generate=Model()) is True
    step = lq.pursuit_steps(pursuit_id)[0]
    assert step["state"] == "ready"
    assert all("link" not in f for f in json.loads(step["files"]))
    assert lq.get_pursuit(pursuit_id)["drive_folder_id"] is None   # made on the next step, once Drive answers


def test_a_drive_refresh_job_indexes_the_library(ledger_db: str, local: Path, fake: FakeDrive) -> None:
    fake.add("2026-03-17_vulcan-sof_vigilant-eagle-27", FOLDER, fake.submissions)
    job_id = lq.queue_job("drive_refresh", None, None, "David Wood")
    assert worker.work_once(generate=Model()) is True
    assert (lq.get_job(job_id)["state"], lq.get_job(job_id)["result"]) == ("done", "Indexed 1 item from the Proposal Library.")
    assert [r["name"] for r in lq.drive_items()] == ["2026-03-17_vulcan-sof_vigilant-eagle-27"]
    next(i for i in fake.items.values() if i["name"].startswith("2026-03-17"))["trashed"] = True
    lq.queue_job("drive_refresh", None, None, "David Wood")
    worker.work_once(generate=Model())
    assert lq.drive_items() == []   # the index mirrors the library


def test_without_drive_a_refresh_says_so(ledger_db: str, local: Path) -> None:
    job_id = lq.queue_job("drive_refresh", None, None, "David Wood")
    worker.work_once(generate=Model())
    assert (lq.get_job(job_id)["state"], lq.get_job(job_id)["result"]) == ("failed", "Drive is not set up yet.")


def test_the_idle_worker_refreshes_every_15_minutes_and_moves_no_go_folders(ledger_db: str, local: Path, fake: FakeDrive) -> None:
    pursuit_id = _pursuit()
    worker.work_once(generate=Model())   # Discovery makes the folder
    folder_id = lq.get_pursuit(pursuit_id)["drive_folder_id"]
    assert lq.no_go(lq.pursuit_steps(pursuit_id)[0]["id"], "David Wood", "Not our work")
    clock = iter([0.0, 60.0, 16 * 60.0])
    refreshed = [worker.housekeeping(next(clock)) for _ in range(3)]
    assert [r["refreshed"] for r in refreshed] == [True, False, True]
    assert fake.path_of(folder_id).startswith("Submissions/_no-go/")
    assert [r["moved"] for r in refreshed] == [1, 0, 0]
    assert any(e["kind"] == "folder_moved" for e in lq.pursuit_events(pursuit_id))


def test_the_drive_check_reads_and_never_writes(fake: FakeDrive, capsys: pytest.CaptureFixture[str]) -> None:
    before = dict(fake.items)
    assert worker.main(["--drive-check"]) == 0
    out = capsys.readouterr().out
    assert "can see the library folder: yes, 'BD Proposal Library'" in out and "items inside: 1" in out
    assert fake.items == before
