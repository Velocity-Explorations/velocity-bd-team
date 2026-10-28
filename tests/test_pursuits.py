"""The proposal workspace's ledger (migration 008, PRO-568): a pursuit per call, one row per attempt at
a step, and every change guarded by the state it expects, so the worker and the owner never both win."""
from __future__ import annotations

import json

import pytest

from ledger import queries as lq


def _call(call_id: str = "sam-1", **overrides: object) -> str:
    run_id = lq.start_run("sam_gov")
    lq.upsert_call({"id": call_id, "portal": "sam_gov", "title": f"Title for {call_id}", "due_date": "2026-12-01",
                    **overrides}, run_id)
    return call_id


def _started(call_id: str = "sam-1", **options: object) -> int:
    return lq.start_pursuit(_call(call_id), "David Wood", **options)


def _ready(pursuit_id: int, cost: float = 0.0) -> dict:
    """Let the worker take the queued step and save it, as the worker will."""
    step = lq.claim_next_step()
    assert step is not None and step["pursuit_id"] == pursuit_id
    assert lq.finish_step(step["id"], summary="Key points", files=[{"name": "Discovery.docx", "id": "f1"}], cost_usd=cost)
    return lq.get_step(step["id"])


def _kinds(pursuit_id: int) -> list[str]:
    return [e["kind"] for e in lq.pursuit_events(pursuit_id)]


# ------------------------------------------------------------------------------ starting

def test_start_the_draft_queues_discovery_and_records_who_started_it(ledger_db: str) -> None:
    pursuit_id = _started(format="white paper", approval_mode="key_gates", direction="Lead with Echo C2",
                          collaborators=["Shaun Jones"], builds_on=[{"id": "d1", "name": "C2 prototype"}])
    pursuit = lq.get_pursuit(pursuit_id)
    assert pursuit is not None
    assert (pursuit["call_id"], pursuit["owner"], pursuit["state"], pursuit["current_step"]) == ("sam-1", "David Wood", "working",
                                                                                                    "discovery")
    assert (pursuit["format"], pursuit["approval_mode"], pursuit["direction"]) == ("white paper", "key_gates", "Lead with Echo C2")
    assert json.loads(pursuit["collaborators"]) == ["Shaun Jones"]
    assert json.loads(pursuit["builds_on"]) == [{"id": "d1", "name": "C2 prototype"}]
    assert (pursuit["cost_usd"], pursuit["budget_usd"]) == (0, 200)
    assert lq.pursuit_for_call("sam-1")["id"] == pursuit_id

    [step] = lq.pursuit_steps(pursuit_id)
    assert (step["step"], step["attempt"], step["state"], step["requested_by"]) == ("discovery", 1, "queued", "David Wood")
    [event] = lq.pursuit_events(pursuit_id)
    assert (event["who"], event["kind"]) == ("David Wood", "started")


def test_the_defaults_are_every_step_and_a_200_dollar_cap(ledger_db: str) -> None:
    pursuit = lq.get_pursuit(_started())
    assert (pursuit["approval_mode"], pursuit["budget_usd"], pursuit["collaborators"], pursuit["builds_on"]) == (
        "every_step", 200, None, None)


def test_a_call_is_pursued_once(ledger_db: str) -> None:
    _started()
    with pytest.raises(lq.PursuitRefused, match="already has a draft, started by David Wood"):
        lq.start_pursuit("sam-1", "Shaun Jones")


def test_a_call_marked_not_relevant_or_unknown_is_refused(ledger_db: str) -> None:
    _call("sam-2")
    lq.set_human("sam-2", "not_relevant", "Shaun Jones")
    with pytest.raises(lq.PursuitRefused, match="marked Not relevant"):
        lq.start_pursuit("sam-2", "David Wood")
    with pytest.raises(lq.PursuitRefused, match="No call"):
        lq.start_pursuit("sam-404", "David Wood")
    with pytest.raises(ValueError, match="approval mode"):
        lq.start_pursuit(_call("sam-3"), "David Wood", approval_mode="sometimes")
    assert lq.list_pursuits() == []


# ------------------------------------------------------------------------------ the worker

def test_the_worker_claims_the_oldest_queued_step_once(ledger_db: str) -> None:
    first, second = _started("sam-1"), _started("sam-2")
    claimed = lq.claim_next_step()
    assert claimed is not None
    assert (claimed["pursuit_id"], claimed["state"]) == (first, "working") and claimed["started_at"]
    assert lq.claim_next_step()["pursuit_id"] == second
    assert lq.claim_next_step() is None


def test_finishing_saves_the_work_and_adds_its_cost(ledger_db: str) -> None:
    pursuit_id = _started()
    step = _ready(pursuit_id, cost=1.25)
    assert step["state"] == "ready" and step["finished_at"] and step["summary"] == "Key points"
    assert json.loads(step["files"]) == [{"name": "Discovery.docx", "id": "f1"}]
    assert step["cost_usd"] == 1.25 and lq.get_pursuit(pursuit_id)["cost_usd"] == 1.25
    assert _kinds(pursuit_id) == ["started", "step_saved"]
    assert not lq.finish_step(step["id"], summary="again")      # only a working step can be saved


def test_task_states_change_only_while_the_step_works(ledger_db: str) -> None:
    pursuit_id = _started()
    step = lq.claim_next_step()
    assert lq.set_task_states(step["id"], {"recheck_page": "done", "attachments": "working"})
    assert json.loads(lq.get_step(step["id"])["task_states"])["attachments"] == "working"
    lq.finish_step(step["id"])
    assert not lq.set_task_states(step["id"], {"recheck_page": "done"})
    assert lq.get_pursuit(pursuit_id)["state"] == "working"


def test_a_failed_step_keeps_its_error_and_retries_as_a_new_attempt(ledger_db: str) -> None:
    pursuit_id = _started()
    step = lq.claim_next_step()
    assert lq.fail_step(step["id"], "The call page did not load", cost_usd=0.4)
    failed = lq.get_step(step["id"])
    assert (failed["state"], failed["error"]) == ("failed", "The call page did not load")
    assert lq.get_pursuit(pursuit_id)["cost_usd"] == 0.4

    retry = lq.retry_step(step["id"], "David Wood")
    assert retry is not None
    assert lq.retry_step(step["id"], "David Wood") is None       # a second click does not queue a third attempt
    again = lq.get_step(retry)
    assert (again["step"], again["attempt"], again["state"]) == ("discovery", 2, "queued")
    assert lq.get_step(step["id"])["state"] == "failed"
    assert _kinds(pursuit_id) == ["started", "failed", "retried"]


def test_budget_reached_blocks_the_step_until_someone_retries(ledger_db: str) -> None:
    pursuit_id = _started()
    step = lq.claim_next_step()
    assert lq.block_step(step["id"], "budget reached")
    blocked = lq.get_step(step["id"])
    assert (blocked["state"], blocked["error"]) == ("blocked", "budget reached")
    assert lq.claim_next_step() is None
    assert lq.retry_step(step["id"], "David Wood") is not None
    assert lq.claim_next_step()["attempt"] == 2
    assert "blocked" in _kinds(pursuit_id)


# ------------------------------------------------------------------------------ the owner

def test_approving_a_step_queues_the_next_one(ledger_db: str) -> None:
    pursuit_id = _started()
    discovery = _ready(pursuit_id)
    following = lq.approve_step(discovery["id"], "David Wood", note="Looks right")
    assert following is not None
    approved = lq.get_step(discovery["id"])
    assert (approved["state"], approved["decision"], approved["decided_by"], approved["decision_note"]) == (
        "approved", "approved", "David Wood", "Looks right")
    nxt = lq.get_step(following)
    assert (nxt["step"], nxt["attempt"], nxt["state"]) == ("summary", 1, "queued")
    assert lq.get_pursuit(pursuit_id)["current_step"] == "summary"
    assert _kinds(pursuit_id)[-1] == "approved"


def test_a_stale_or_repeated_approval_is_refused(ledger_db: str) -> None:
    pursuit_id = _started()
    queued = lq.pursuit_steps(pursuit_id)[0]
    assert lq.approve_step(queued["id"], "David Wood") is None                  # nothing to approve yet
    step = _ready(pursuit_id)
    assert lq.approve_step(step["id"], "David Wood", expected_updated_at="2000-01-01T00:00:00Z") is None
    assert lq.get_step(step["id"])["state"] == "ready"
    assert lq.approve_step(step["id"], "David Wood", expected_updated_at=step["updated_at"]) is not None
    assert lq.approve_step(step["id"], "Shaun Jones") is None
    assert [s["step"] for s in lq.pursuit_steps(pursuit_id)] == ["discovery", "summary"]


def test_asking_for_changes_redoes_the_step_with_the_note(ledger_db: str) -> None:
    pursuit_id = _started()
    step = _ready(pursuit_id)
    with pytest.raises(ValueError, match="note"):
        lq.ask_changes(step["id"], "David Wood", " ")
    redo = lq.ask_changes(step["id"], "David Wood", "Add the parent BAA")
    assert redo is not None
    assert lq.get_step(step["id"])["state"] == "changes_asked"
    again = lq.get_step(redo)
    assert (again["step"], again["attempt"], again["state"], again["request_note"]) == ("discovery", 2, "queued",
                                                                                        "Add the parent BAA")
    assert lq.ask_changes(step["id"], "David Wood", "twice") is None
    assert lq.latest_steps(pursuit_id)["discovery"]["id"] == redo


def test_the_gate_takes_go_or_go_with_conditions(ledger_db: str) -> None:
    pursuit_id = _started()
    for _ in range(4):                                   # discovery, summary, alignment, requirements
        step = _ready(pursuit_id)
        with pytest.raises(ValueError):
            lq.approve_step(step["id"], "David Wood", decision="go")
        lq.approve_step(step["id"], "David Wood")
    gate = _ready(pursuit_id)
    assert gate["step"] == "go_no_go"
    with pytest.raises(ValueError):
        lq.approve_step(gate["id"], "David Wood", decision="approved")
    outline = lq.approve_step(gate["id"], "David Wood", decision="go_with_conditions", note="Name the partner first")
    assert lq.get_step(gate["id"])["decision"] == "go_with_conditions"
    assert lq.get_step(outline)["step"] == "outline"
    assert _kinds(pursuit_id)[-1] == "go_with_conditions"


def test_the_worker_approves_steps_itself_with_key_gates_only(ledger_db: str) -> None:
    pursuit_id = _started(approval_mode="key_gates")
    step = _ready(pursuit_id)
    assert not lq.needs_owner("discovery", "key_gates") and lq.needs_owner("discovery", "every_step")
    assert all(lq.needs_owner(gate, "key_gates") for gate in ("go_no_go", "outline", "submit"))
    lq.approve_step(step["id"], lq.AUTO_APPROVER)
    assert lq.get_step(step["id"])["decided_by"] == "worker (key gates only)"
    assert _kinds(pursuit_id)[-1] == "auto_approved"


def test_submit_is_not_approved_like_a_step(ledger_db: str) -> None:
    assert lq.STEPS[-1] == "submit" and lq.next_step("final") == "submit" and lq.next_step("submit") is None
    pursuit_id = _started()
    for _ in range(10):
        lq.approve_step(_ready(pursuit_id)["id"], "David Wood", decision=None)
    submit = _ready(pursuit_id)
    assert submit["step"] == "submit"
    with pytest.raises(ValueError, match="Mark submitted"):
        lq.approve_step(submit["id"], "David Wood")


def test_no_go_stops_the_pursuit(ledger_db: str) -> None:
    pursuit_id = _started()
    step = _ready(pursuit_id)
    assert lq.no_go(step["id"], "David Wood", "Needs a cleared facility; ask again if they drop it")
    stopped = lq.get_step(step["id"])
    assert (stopped["state"], stopped["decision"]) == ("stopped", "no_go")
    assert lq.get_pursuit(pursuit_id)["state"] == "no_go"
    assert lq.claim_next_step() is None and _kinds(pursuit_id)[-1] == "no_go"
    assert not lq.no_go(step["id"], "David Wood", "again")


def test_no_go_is_only_offered_up_to_the_gate(ledger_db: str) -> None:
    pursuit_id = _started()
    for _ in range(4):
        lq.approve_step(_ready(pursuit_id)["id"], "David Wood")
    lq.approve_step(_ready(pursuit_id)["id"], "David Wood", decision="go")
    outline = _ready(pursuit_id)
    with pytest.raises(ValueError, match="no-go"):
        lq.no_go(outline["id"], "David Wood", "too late")
    with pytest.raises(ValueError, match="reason"):
        lq.no_go(lq.pursuit_steps(pursuit_id)[0]["id"], "David Wood", "")


def test_closing_stops_waiting_steps_and_the_worker_stops_its_own(ledger_db: str) -> None:
    first, second = _started("sam-1"), _started("sam-2")
    working = lq.claim_next_step()                       # the first pursuit's Discovery, now working
    assert lq.close_pursuit(first, "David Wood", "Partner pulled out")
    assert lq.get_pursuit(first)["state"] == "closed"
    assert not lq.close_pursuit(first, "David Wood")
    assert not lq.finish_step(working["id"], summary="late")       # the worker cannot save into a closed pursuit
    assert lq.stop_step(working["id"], cost_usd=0.3)
    assert lq.get_step(working["id"])["state"] == "stopped" and lq.get_pursuit(first)["cost_usd"] == 0.3

    assert lq.close_pursuit(second, "David Wood")        # its Discovery is still queued
    assert [s["state"] for s in lq.pursuit_steps(second)] == ["stopped"]
    assert lq.claim_next_step() is None
    assert [p["state"] for p in lq.list_pursuits(["closed"])] == ["closed", "closed"]


def test_events_are_kept_in_order_with_who_and_when(ledger_db: str) -> None:
    pursuit_id = _started()
    lq.add_event(pursuit_id, "Shaun Jones", "material", "https://example.invalid/parent-baa.pdf")
    with pytest.raises(ValueError):
        lq.add_event(pursuit_id, "Shaun Jones", "gossip", "x")
    events = lq.pursuit_events(pursuit_id)
    assert [(e["who"], e["kind"]) for e in events] == [("David Wood", "started"), ("Shaun Jones", "material")]
    assert all(e["at"] for e in events)


# --------------------------------------------------------------------- the worker's helpers (PRO-577)

def test_the_worker_beats_in_the_workers_table(ledger_db: str) -> None:
    assert lq.get_worker("worker") is None
    lq.worker_started("worker")
    first = lq.get_worker("worker")
    assert (first["state"], first["doing"]) == ("idle", None) and first["started_at"] == first["seen_at"]
    lq.worker_beat("worker", "working", "Discovery (pursuit 1)")
    beat = lq.get_worker("worker")
    assert (beat["state"], beat["doing"], beat["started_at"]) == ("working", "Discovery (pursuit 1)", first["started_at"])
    lq.worker_beat("worker", "stopped")
    assert (lq.get_worker("worker")["state"], lq.get_worker("worker")["doing"]) == ("stopped", None)
    with pytest.raises(ValueError):
        lq.worker_beat("worker", "asleep")


def test_a_step_blocked_mid_way_keeps_what_it_cost(ledger_db: str) -> None:
    pursuit_id = _started()
    step = lq.claim_next_step()
    assert lq.block_step(step["id"], "budget reached", cost_usd=1.25)
    blocked = lq.get_step(step["id"])
    assert (blocked["state"], blocked["error"], blocked["cost_usd"]) == ("blocked", "budget reached", 1.25)
    assert lq.get_pursuit(pursuit_id)["cost_usd"] == 1.25


def test_working_steps_are_listed_for_the_worker_to_recover(ledger_db: str) -> None:
    _started("sam-1"), _started("sam-2")
    claimed = lq.claim_next_step()
    assert [s["id"] for s in lq.steps_in_state("working")] == [claimed["id"]]
    assert len(lq.steps_in_state("queued")) == 1


def test_discovery_sets_when_the_result_is_expected(ledger_db: str) -> None:
    pursuit_id = _started()
    assert lq.set_result_expected(pursuit_id, "2027-03-01", "Section 6.2: selections within 90 days of the close")
    pursuit = lq.get_pursuit(pursuit_id)
    assert (pursuit["result_expected_by"], pursuit["result_expected_source"]) == (
        "2027-03-01", "Section 6.2: selections within 90 days of the close")
    with pytest.raises(ValueError):
        lq.set_result_expected(pursuit_id, "1 March 2027", "words")
    lq.close_pursuit(pursuit_id, "David Wood")
    assert not lq.set_result_expected(pursuit_id, "2027-04-01", "later")


def test_requirements_set_target_dates_and_the_checklist(ledger_db: str) -> None:
    pursuit_id = _started()
    assert lq.set_target_dates(pursuit_id, {"submit_by": "2026-11-30", "outline": "2026-11-10"})
    assert json.loads(lq.get_pursuit(pursuit_id)["target_dates"]) == {"submit_by": "2026-11-30", "outline": "2026-11-10"}
    items = [
        {"part": "registrations", "text": "SAM.gov registration active, UEI and CAGE", "source": "per BAA 3.1", "owner": "David Wood",
         "due_date": "2026-11-20", "done": True},
        {"part": "documents", "text": "Technical Volume: 20 pages max, PDF", "source": "per BAA 5.4", "owner": "Claude",
         "due_date": None, "done": False},
    ]
    assert lq.save_checklist(pursuit_id, items, "requirements") == 2
    saved = lq.checklist(pursuit_id)
    assert [(i["part"], i["position"], i["done"], i["origin"]) for i in saved] == [
        ("registrations", 0, 1, "requirements"), ("documents", 1, 0, "requirements")]
    assert saved[0]["done_by"] == lq.WORKER and saved[1]["done_by"] is None

    # A redo replaces the open items it wrote and keeps what was ticked, without repeating it.
    redo = [items[0], {"part": "submission", "text": "Portal login tested", "source": None, "owner": "David Wood",
                       "due_date": "2026-11-29", "done": False}]
    assert lq.save_checklist(pursuit_id, redo, "requirements") == 1
    assert [(i["text"], i["position"]) for i in lq.checklist(pursuit_id)] == [
        ("SAM.gov registration active, UEI and CAGE", 0), ("Portal login tested", 1)]
    with pytest.raises(ValueError):
        lq.save_checklist(pursuit_id, [{"part": "snacks", "text": "x"}], "requirements")


def test_clash_checks_find_the_same_title_and_other_pursued_calls(ledger_db: str) -> None:
    _call("sam-1", title="Edge AI for C2")
    _call("ssc-9", title="  edge ai for c2 ", portal="ssc_front_door")
    _call("sam-2", title="Something else")
    assert [c["id"] for c in lq.calls_titled("Edge AI for C2", exclude_id="sam-1")] == ["ssc-9"]
    lq.set_human("sam-2", "pursue", "Shaun Jones")
    assert [c["id"] for c in lq.pursued_calls(exclude_id="sam-1")] == ["sam-2"]
