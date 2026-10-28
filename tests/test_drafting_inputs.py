"""What the worker's steps know about a pursued call, gathered from the ledger (PRO-577)."""
from __future__ import annotations

from datetime import date

from drafting import inputs
from ledger import queries as lq


def _pursued(**pursuit: object) -> int:
    run_id = lq.start_run("sam_gov")
    lq.upsert_call({"id": "sam-1", "portal": "SAM.gov", "title": "Edge AI for C2", "type": "Sources Sought",
                    "department": "DEPT OF THE ARMY", "due_date": "2026-12-01", "url": "https://sam.gov/opp/1",
                    "description": "The Army seeks edge AI for command and control.",
                    "extra": {"sam_solicitation_number": "W1-26-R-0001", "sam_set_aside": "SBA"}}, run_id)
    lq.set_review("sam-1", "yes", "Fits Echo C2")
    lq.add_judgment("sam-1", "grok", "grok-4.7", "maybe", "Partial fit: no Army past performance")
    lq.set_human("sam-1", "pursue", "Shaun Jones")
    lq.append_note("sam-1", "Lead with the Cobra Gold results", "Shaun Jones")
    lq.upsert_proposal({"submission_id": "2025-03-17_sbir_c2-edge", "title": "Edge C2 for the Army", "agency": "Army",
                        "type": "SBIR Phase I", "submitted_date": "2025-03-17", "outcome": "won", "strength_rating": 4,
                        "use_as_exemplar": 1, "brief": "Echo C2 at the edge."})
    lq.upsert_proposal({"submission_id": "2024-01-02_nasa_lunar", "title": "Lunar landing sensors", "agency": "NASA",
                        "type": "white paper", "submitted_date": "2024-01-02", "outcome": "lost"})
    return lq.start_pursuit("sam-1", "David Wood", **pursuit)


def test_the_record_holds_the_call_and_what_the_dashboard_knows(ledger_db: str) -> None:
    pursuit_id = _pursued(format="RFI response", direction="Lead with Echo C2", collaborators=["Shaun Jones"],
                          builds_on=[{"id": "d1", "name": "C2 prototype white paper"}])
    record = inputs.gather(pursuit_id)
    facts = inputs.call_facts(record, today=date(2026, 10, 28))
    for expected in ("Edge AI for C2", "SAM.gov", "Sources Sought", "DEPT OF THE ARMY", "2026-12-01", "https://sam.gov/opp/1",
                     "RFI response", "David Wood", "Shaun Jones", "2026-10-28",
                     "The Army seeks edge AI for command and control.", "W1-26-R-0001",
                     "Claude: yes", "Fits Echo C2", "Grok: maybe", "no Army past performance",
                     "Shaun Jones: pursue", "Lead with the Cobra Gold results",
                     "Lead with Echo C2", "C2 prototype white paper"):
        assert expected in facts, expected


def test_past_work_puts_the_same_agency_and_exemplars_first(ledger_db: str) -> None:
    record = inputs.gather(_pursued())
    assert [p["submission_id"] for p in record.past_work] == ["2025-03-17_sbir_c2-edge", "2024-01-02_nasa_lunar"]
    text = inputs.past_work_text(record)
    assert text.index("2025-03-17_sbir_c2-edge") < text.index("2024-01-02_nasa_lunar")
    assert "won" in text and "Echo C2 at the edge." in text


def test_the_draft_inputs_follow_the_chosen_format(ledger_db: str) -> None:
    rfi = inputs.draft_inputs(inputs.gather(_pursued(format="RFI response")))
    assert (rfi.opp_type, rfi.template["name"], rfi.agency, rfi.due_date) == ("RFI", "capability_statement", "DEPT OF THE ARMY",
                                                                              "2026-12-01")
    assert "The Army seeks edge AI" in rfi.listing_text and "W1-26-R-0001" in rfi.listing_text
    assert "2025-03-17_sbir_c2-edge" in rfi.past_experience
    assert "Lead with the Cobra Gold results" in rfi.team_notes
    assert "Velocity Explorations" in rfi.company_context


def test_without_a_format_the_call_type_picks_the_template(ledger_db: str) -> None:
    draft = inputs.draft_inputs(inputs.gather(_pursued()))
    assert (draft.opp_type, draft.template["name"]) == ("Sources Sought", "capability_statement")


def test_the_clash_check_finds_reposts_and_pursued_calls_closing_near_the_deadline(ledger_db: str) -> None:
    pursuit_id = _pursued()
    run_id = lq.start_run("ssc_front_door")
    lq.upsert_call({"id": "ssc-9", "portal": "SSC Front Door", "title": "Edge AI for C2", "due_date": "2026-12-01"}, run_id)
    lq.upsert_call({"id": "sam-2", "portal": "SAM.gov", "title": "Space sensors", "due_date": "2026-12-04"}, run_id)
    lq.upsert_call({"id": "sam-3", "portal": "SAM.gov", "title": "Far away", "due_date": "2027-03-01"}, run_id)
    lq.set_human("sam-2", "pursue", "David Wood")
    lq.set_human("sam-3", "pursue", "David Wood")
    clashes = inputs.gather(pursuit_id).clashes
    assert [c["id"] for c in clashes["same_title"]] == ["ssc-9"]
    assert [c["id"] for c in clashes["closing_near"]] == ["sam-2"]
    assert clashes["register"] == []


def test_material_the_team_adds_reaches_every_later_prompt(ledger_db: str) -> None:
    pursuit_id = _pursued()
    lq.add_event(pursuit_id, "Shaun Jones", "material", "The parent BAA is at https://example.invalid/baa.pdf")
    facts = inputs.call_facts(inputs.gather(pursuit_id), today=date(2026, 10, 28))
    assert "MATERIAL THE TEAM ADDED" in facts
    assert "Shaun Jones: The parent BAA is at https://example.invalid/baa.pdf" in facts
    assert "MATERIAL THE TEAM ADDED" not in inputs.call_facts(inputs.gather(_other_pursuit()), today=date(2026, 10, 28))


def _other_pursuit() -> int:
    run_id = lq.start_run("sam_gov")
    lq.upsert_call({"id": "sam-9", "portal": "SAM.gov", "title": "Another call", "due_date": "2026-12-09"}, run_id)
    return lq.start_pursuit("sam-9", "David Wood")
