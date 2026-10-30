"""Velocity's facts, read from 01 Company Reference on Drive at draft time and never kept in the repo (PRO-565).
The files here are made up (tests/company_reference.py)."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from drafting import company, drive, facts
from tests import company_reference

NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
READ_DRIVE = facts.read_drive   # the real one: tests/conftest.py stands a made-up Company Reference in for it


def test_every_item_reaches_the_writer_by_its_id_without_the_source_links() -> None:
    block = facts.parse(company_reference.files(), NOW).block(hoverslam=False)
    for line in ("F-02 | UEI: TESTUEI00001 (matches public data)", "PP-01 |", "PR-01 |", "PE-01 |"):
        assert line in block, line
    assert "Example Velocity builds software for operators $5 cheaper." in block   # the doc's text, unescaped
    assert "Echo, in title case" in block                                          # the Brand Guide
    assert "example.invalid" not in block and "Signed form" not in block           # source links stay in Drive


def test_the_writer_is_told_facts_are_the_only_source_and_to_leave_needs_fact() -> None:
    block = facts.parse(company_reference.files(), NOW).block(hoverslam=False)
    assert "only source" in block and "[NEEDS FACT:" in block and "2026-10-30 12:00 UTC" in block
    assert "The proposing company is Velocity Explorations" in block


def test_a_former_employee_is_left_out_of_bios_and_key_personnel() -> None:
    found = facts.parse(company_reference.files(), NOW)
    assert "PE-02" not in found.items and "Pat Former" not in found.block(hoverslam=False)
    assert "PARTNER" in found.items["PE-03"].text                                 # a partner stays, named as one


def test_sensitive_items_are_marked_and_a_sensitive_column_is_its_own_item() -> None:
    found = facts.parse(company_reference.files(), NOW)
    block = found.block(hoverslam=False)
    assert "F-12 [SENSITIVE] |" in block and "PP-02 [SENSITIVE] |" in block and "PP-01 |" in block
    assert found.items["PE-01.clearance_level"].sensitive and "Secret" not in found.items["PE-01"].text
    assert "PE-01.clearance_level [SENSITIVE] | Alex Example: Secret" in block


def test_an_item_on_an_open_question_is_marked_open_and_one_on_a_pending_answer_says_so() -> None:
    block = facts.parse(company_reference.files(), NOW).block(hoverslam=False)
    assert "PR-03 [OPEN: CF-27] |" in block                    # open: not to be stated as settled
    assert "F-06 [EVIDENCE PENDING: CF-14] |" in block          # confirmed by David, evidence pending: usable
    assert "F-03 |" in block and "PR-01 |" in block              # resolved questions leave no mark
    assert "CF-27 [open] | Scout maturity" in block and "CF-01" not in block.split("05 CONFLICTS")[1]


def test_hoverslam_facts_appear_only_for_a_hoverslam_bid_with_its_sam_renewal_flagged() -> None:
    found = facts.parse(company_reference.files(), NOW)
    velocity, hoverslam = found.block(hoverslam=False), found.block(hoverslam=True)
    assert "EXAMPLE HOVERSLAM LLC" not in velocity and "PR-02" not in velocity and "CF-26" not in velocity
    assert "EXAMPLE HOVERSLAM LLC" in hoverslam and "F-49 [OPEN: CF-26] |" in hoverslam
    assert "This bid is for Hoverslam Designs LLC" in hoverslam and "SAM renewal" in hoverslam


def test_the_facts_are_read_fresh_and_a_copy_stands_in_for_24_hours_when_drive_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    reads: list[int] = []
    monkeypatch.setattr(facts, "read_drive", lambda: reads.append(1) or company_reference.files())
    first = facts.load(NOW)
    assert reads == [1] and first.note == "" and facts.CACHE.exists()

    def down() -> dict[str, object]:
        raise drive.DriveError("Drive answered 503")

    monkeypatch.setattr(facts, "read_drive", down)
    later = facts.load(NOW + timedelta(hours=23))
    assert "F-02" in later.items and "Drive answered 503" in later.note and later.read_at == first.read_at
    with pytest.raises(facts.FactsUnavailable, match="last 24 hours"):
        facts.load(NOW + timedelta(hours=25))


def test_without_the_file_ids_in_env_the_writer_will_not_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, _, _ in facts.SOURCES.values():
        monkeypatch.setenv(key, "")
    with pytest.raises(facts.FactsUnavailable, match="COMPANY_FACTS_DOC_ID"):
        READ_DRIVE()


def test_the_facts_used_notes_list_each_id_and_what_needs_review() -> None:
    found = facts.parse(company_reference.files(), NOW)
    used = [{"id": "F-02", "claims": ["the UEI on the cover page"]}, {"id": "F-12", "claims": ["the facility clearance"]},
            {"id": "F-06", "claims": ["WOSB status"]}, {"id": "PR-03", "claims": ["Scout at TRL 5"]},
            {"id": "F-99", "claims": ["a contract number"]}]
    notes = found.notes(used, ["Velocity has 40 staff"], "Draft v1", hoverslam=False, needs_fact=2)
    assert notes.startswith("# Facts used, Draft v1")
    assert "| F-02 | the UEI on the cover page |" in notes
    assert "F-12 is SENSITIVE" in notes
    assert "F-06 rests on CF-14 (WOSB certification), confirmed by David, evidence pending" in notes
    assert "PR-03 rests on CF-27 (Scout maturity), which is still open" in notes
    assert "F-99" in notes.split("not in 01 Company Reference")[1]
    assert "Velocity has 40 staff" in notes and "2 [NEEDS FACT] placeholders" in notes
    assert found.to_review(used) == ["F-12", "F-06", "PR-03"]
    assert "SAM renewal" in found.notes([], [], "Draft v1", hoverslam=True, needs_fact=0)


def test_the_trace_prompt_holds_the_facts_and_the_draft() -> None:
    prompt = facts.parse(company_reference.files(), NOW).trace_prompt("# Draft\nVelocity is a WOSB.", hoverslam=False)
    assert "rests on none" in prompt.system and '"used"' in prompt.system
    assert "F-06 [EVIDENCE PENDING: CF-14]" in prompt.user and prompt.user.endswith("# Draft\nVelocity is a WOSB.")


def test_the_repo_keeps_only_fact_ids_for_the_title_page_fields() -> None:
    """company.yaml once held the CAGE, UEI, NAICS and POC; now each field names the fact that fills it."""
    fields = company.profile()
    assert fields["company_name"] == "Velocity Explorations"
    for name in ("legal_name", "cage", "uei", "duns", "naics_display", "business_size", "company_description"):
        assert fields[name].startswith("[F-"), name
    assert fields["poc_email"].startswith("[NEEDS FACT:") and fields["poc_phone"].startswith("[NEEDS FACT:")
    assert not re.search(r"\d{4}", Path(company.PROFILE_PATH).read_text(encoding="utf-8"))   # no codes or numbers
