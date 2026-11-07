"""Ask Grok (David, 7 Nov 2026): a question asked from the dashboard's panel waits in the ledger, run.py --assistant has
Grok answer it with read-only tools, and the answer goes back to the ledger. Grok is faked throughout."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

import run
from assistant import chat, grok, tools
from ledger import db
from ledger import queries as lq
from tests.test_briefs import scored, seed

NOW = datetime(2026, 11, 7, 15, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- the ledger

def test_a_question_waits_is_taken_once_and_keeps_its_answer(ledger_db: str) -> None:
    asked = lq.ask_question("t-1", "David Wood", "Is Unison worth bidding?", "/review?view=top10&focus=samgov-1")
    taken = lq.claim_next_question()
    assert taken and taken["id"] == asked and taken["state"] == "working" and taken["page"].endswith("focus=samgov-1")
    assert lq.claim_next_question() is None
    lq.finish_question(asked, "done", "Yes.", sources={"calls": [], "facts": ["F-06"]}, tools=[{"name": "brief_call"}],
                       model="grok-4.7", cost_usd=0.04)
    row = lq.get_question(asked)
    assert row["state"] == "done" and row["answer"] == "Yes." and row["answered_at"]
    assert json.loads(row["sources"])["facts"] == ["F-06"] and json.loads(row["tools"]) == [{"name": "brief_call"}]


def test_a_thread_s_history_is_its_answered_exchanges_oldest_first_and_the_asker_s_only(ledger_db: str) -> None:
    first = lq.ask_question("t-1", "David Wood", "one", None)
    lq.claim_next_question()
    lq.finish_question(first, "done", "answer one")
    failed = lq.ask_question("t-1", "David Wood", "two", None)
    lq.claim_next_question()
    lq.finish_question(failed, "failed", "Grok could not answer")
    other = lq.ask_question("t-1", "Shaun Jones", "theirs", None)   # the same thread id, someone else
    lq.claim_next_question()
    lq.finish_question(other, "done", "their answer")
    now = lq.ask_question("t-1", "David Wood", "three", None)
    assert [(h["question"], h["answer"]) for h in lq.thread_history("t-1", "David Wood", now)] == [("one", "answer one")]


def test_the_day_s_spend_adds_up_the_answers_since_midnight_utc(ledger_db: str) -> None:
    for cost, when in ((0.25, NOW - timedelta(days=1)), (0.5, NOW - timedelta(hours=2)), (0.75, NOW)):
        asked = lq.ask_question("t", "David Wood", "q", None)
        lq.claim_next_question()
        lq.finish_question(asked, "done", "a", cost_usd=cost)
        with db.tx() as conn:
            db.q(conn, "UPDATE chat_messages SET answered_at = ? WHERE id = ?", (when.isoformat().replace("+00:00", "Z"), asked))
    assert lq.chat_spend_today(NOW) == pytest.approx(1.25)


def test_questions_a_stopped_assistant_left_working_wait_again(ledger_db: str) -> None:
    asked = lq.ask_question("t", "David Wood", "q", None)
    lq.claim_next_question()
    assert lq.requeue_working_questions() == 1
    assert lq.get_question(asked)["state"] == "queued"


# --------------------------------------------------------------------------- the Grok client

class Reply:
    def __init__(self, body: dict[str, Any]) -> None:
        self.body = json.dumps(body).encode("utf-8")

    def read(self) -> bytes:
        return self.body

    def __enter__(self) -> "Reply":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


USAGE = {"input_tokens": 1000, "input_tokens_details": {"cached_tokens": 100}, "output_tokens": 37}
CALL_ITEM = {"type": "function_call", "id": "fc_1", "call_id": "call_1", "name": "brief_call",
             "arguments": '{"call_id": "samgov-1"}', "status": "completed"}
REASONING = {"type": "reasoning", "id": "", "summary": [], "status": "completed"}
MESSAGE = {"type": "message", "role": "assistant", "status": "completed",
           "content": [{"type": "output_text", "text": "Unison is worth a look.", "annotations": []}]}
TOOL_DEF = {"type": "function", "name": "brief_call", "description": "d", "parameters": {"type": "object", "properties": {}}}


@pytest.fixture
def xai(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Every request body sent to xAI; each test sets the replies on grok._open."""
    monkeypatch.setenv("BD_XAI_API_KEY", "test-key-not-real")
    monkeypatch.setattr(grok, "RETRY_DELAY_S", 0)
    return []


def replying(sent: list[dict[str, Any]], *answers: Any):   # noqa: ANN201
    queue = list(answers)

    def fake_open(request: Any, timeout: float) -> Reply:
        sent.append(json.loads(request.data.decode("utf-8")))
        assert request.get_header("Authorization") == "Bearer test-key-not-real"
        answer = queue.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return Reply(answer)

    return fake_open


def test_grok_hands_back_its_tool_calls_and_the_items_to_send_with_their_results(xai: list, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(grok, "_open", replying(xai, {"status": "completed", "output": [REASONING, CALL_ITEM], "usage": USAGE}))
    turn = grok.GrokChat().respond([{"role": "user", "content": "hi"}], [TOOL_DEF])
    assert xai[0]["model"] == "grok-4.7" and xai[0]["store"] is False and xai[0]["tools"] == [TOOL_DEF]
    assert turn.calls == [{"call_id": "call_1", "name": "brief_call", "arguments": {"call_id": "samgov-1"}}]
    assert turn.items == [CALL_ITEM]   # the reasoning item is not sent back
    assert turn.text == "" and (turn.input_tokens, turn.cached_tokens, turn.output_tokens) == (900, 100, 37)


def test_grok_s_answer_is_its_message_text(xai: list, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(grok, "_open", replying(xai, {"status": "completed", "output": [REASONING, MESSAGE], "usage": USAGE}))
    turn = grok.GrokChat().respond([{"role": "user", "content": "hi"}], [])
    assert turn.text == "Unison is worth a look." and turn.calls == [] and "tools" not in xai[0]


def test_a_rate_limit_is_tried_once_more_and_a_bad_request_is_not(xai: list, monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.error

    limited = urllib.error.HTTPError(grok.XAI_URL, 429, "Too Many Requests", {}, None)   # type: ignore[arg-type]
    monkeypatch.setattr(grok, "_open", replying(xai, limited, {"status": "completed", "output": [MESSAGE], "usage": USAGE}))
    assert grok.GrokChat().respond([{"role": "user", "content": "hi"}], []).text == "Unison is worth a look."
    bad = urllib.error.HTTPError(grok.XAI_URL, 400, "Bad Request", {}, None)   # type: ignore[arg-type]
    monkeypatch.setattr(grok, "_open", replying(xai, bad))
    with pytest.raises(grok.GrokError, match="400"):
        grok.GrokChat().respond([{"role": "user", "content": "hi"}], [])


# --------------------------------------------------------------------------- the conversation

class ScriptedGrok:
    """Grok's turns, in order, and every exchange it was sent."""

    def __init__(self, *turns: grok.Turn) -> None:
        self.turns = list(turns)
        self.sent: list[tuple[list[dict[str, Any]], list[dict[str, Any]]]] = []

    def respond(self, items: list[dict[str, Any]], tool_defs: list[dict[str, Any]]) -> grok.Turn:
        self.sent.append((json.loads(json.dumps(items)), tool_defs))
        return self.turns.pop(0)


def asks(*calls: tuple[str, dict[str, Any]]) -> grok.Turn:
    found = [{"call_id": f"c{i}", "name": name, "arguments": args} for i, (name, args) in enumerate(calls)]
    items = [{"type": "function_call", "call_id": c["call_id"], "name": c["name"], "arguments": json.dumps(c["arguments"])}
             for c in found]
    return grok.Turn(text="", calls=found, items=items, input_tokens=100, cached_tokens=0, output_tokens=10)


def says(text: str) -> grok.Turn:
    return grok.Turn(text=text, calls=[], items=[], input_tokens=200, cached_tokens=50, output_tokens=40)


def fake_tool(name: str, result: Any) -> tools.Tool:
    def run_it(**kwargs: Any) -> dict[str, Any]:
        if isinstance(result, Exception):
            raise result
        return result(kwargs) if callable(result) else result

    return tools.Tool(name, f"the {name} tool", "read", {"type": "object", "properties": {}}, run_it)


def test_grok_calls_the_tools_it_needs_and_answers_with_sources(ledger_db: str) -> None:
    model = ScriptedGrok(asks(("search_calls", {"query": "unison"})), says("Unison is open until 4 Dec, per F-07 and PP-20."))
    search = fake_tool("search_calls", lambda args: {
        "calls": [{"id": "samgov-1", "title": "Unison", "portal": "SAM.gov"}, {"id": "x-2", "title": "Other", "portal": "DIU"}],
        "text": f"- Unison (SAM.gov; id samgov-1), searched for {args['query']}"})
    reply = chat.answer("Tell me about Unison", [("Hi", "Hello.")], "/review?view=top10&focus=samgov-1", model, [search],
                        asked_by="David Wood")
    assert reply.text == "Unison is open until 4 Dec, per F-07 and PP-20."
    assert reply.sources == {"calls": [{"id": "samgov-1", "title": "Unison", "portal": "SAM.gov"}], "facts": ["F-07", "PP-20"]}
    sent = "- Unison (SAM.gov; id samgov-1), searched for unison"
    assert reply.trace == [{"name": "search_calls", "arguments": {"query": "unison"}, "chars": len(sent)}]
    assert (reply.input_tokens, reply.cached_tokens, reply.output_tokens, reply.rounds) == (300, 50, 50, 2)
    first, defs = model.sent[0]
    assert first[0]["role"] == "system" and first[0]["content"] == chat.SYSTEM
    assert [m["content"] for m in first[1:3]] == ["Hi", "Hello."]
    assert "David Wood" in first[3]["content"] and "samgov-1" in first[3]["content"] and "Tell me about Unison" in first[3]["content"]
    assert defs == [{"type": "function", "name": "search_calls", "description": "the search_calls tool",
                     "parameters": {"type": "object", "properties": {}}}]
    second, _ = model.sent[1]
    assert second[-2]["type"] == "function_call" and second[-1] == {
        "type": "function_call_output", "call_id": "c0", "output": "- Unison (SAM.gov; id samgov-1), searched for unison"}


def test_a_tool_that_fails_or_does_not_exist_tells_grok_so(ledger_db: str) -> None:
    model = ScriptedGrok(asks(("brief_call", {"call_id": "nope"}), ("made_up", {})), says("I could not find that call."))
    broken = fake_tool("brief_call", tools.ToolError("No call with id nope."))
    reply = chat.answer("Brief nope", [], None, model, [broken])
    outputs = [item["output"] for item in model.sent[1][0] if item.get("type") == "function_call_output"]
    assert outputs == ["The tool said: No call with id nope.", "There is no tool called made_up."]
    assert reply.text == "I could not find that call."


def test_a_long_tool_result_is_cut_and_grok_must_answer_after_the_last_round(ledger_db: str) -> None:
    rounds = [asks(("search_calls", {"query": str(i)})) for i in range(chat.MAX_ROUNDS)]
    model = ScriptedGrok(*rounds, says("Here is what I found."))
    big = fake_tool("search_calls", {"text": "x" * (chat.RESULT_CHARS + 500)})
    reply = chat.answer("Find everything", [], None, model, [big])
    sent_output = next(item for item in model.sent[1][0] if item.get("type") == "function_call_output")["output"]
    assert len(sent_output) <= chat.RESULT_CHARS + 40 and sent_output.endswith("(cut short)")
    assert model.sent[-1][1] == []   # the last call offers no tools, so Grok answers
    assert reply.text == "Here is what I found." and reply.rounds == chat.MAX_ROUNDS + 1


def test_the_rules_ask_for_ids_and_needs_fact_and_forbid_sensitive_items_and_dashes() -> None:
    for words in ("NEEDS FACT", "SENSITIVE", "F-06", "only from what your tools return", "cannot change",
                  "not approved to name"):   # David, 7 Nov: an answer named a contact the record said not to
        assert words in chat.SYSTEM, words
    assert "–" not in chat.SYSTEM and "—" not in chat.SYSTEM


# --------------------------------------------------------------------------- the new read tools

def test_search_calls_finds_open_calls_by_their_words_with_both_verdicts_fit_and_kind(ledger_db: str) -> None:
    scored("unison-call", "yes", "yes", 63)
    scored("other-call", "maybe", "no", 80)
    scored("closed-unison", "yes", "yes", 70, days=-2)   # its deadline has passed
    lq.set_listing("unison-call", "Call")
    with db.tx() as conn:
        db.q(conn, "UPDATE calls SET title = 'Unison collaborative autonomy' WHERE id IN ('unison-call', 'closed-unison')")
    found = tools.search_calls("unison autonomy")
    assert [c["id"] for c in found["calls"]] == ["unison-call"]
    call = found["calls"][0]
    assert (call["claude"], call["grok"], call["fit"], call["listing"]) == ("yes", "yes", 63, "Call")
    assert "unison-call" in found["text"] and "Unison collaborative autonomy" in found["text"]
    assert [c["id"] for c in tools.search_calls("unison", open_only=False)["calls"]] == ["closed-unison", "unison-call"]


def test_top_ten_gives_either_list_in_words(ledger_db: str) -> None:
    scored("a-call", "yes", "yes", 60)
    scored("an-umbrella", "yes", "no", 90)
    lq.set_listing("an-umbrella", "Umbrella")
    calls = tools.top_ten("calls")
    assert [c["id"] for c in calls["calls"]] == ["a-call"] and "1. a-call" in calls["text"]
    assert [c["id"] for c in tools.top_ten("watch")["calls"]] == ["an-umbrella"]


def test_past_bids_searches_the_register_and_leaves_the_money_out(ledger_db: str) -> None:
    lq.upsert_proposal({"submission_id": "2026-03-01_darpa_swarm", "title": "Swarm comms", "portal": "SAM.gov",
                        "agency": "DARPA", "outcome": "lost", "award_value": "250000", "requested_value": "300000",
                        "why_won_or_lost": "Too early", "themes": "autonomy"})
    lq.upsert_proposal({"submission_id": "2026-04-01_afwerx_echo", "title": "Echo", "portal": "AFWERX", "agency": "USAF",
                        "outcome": "won"})
    found = tools.past_bids("darpa autonomy")
    assert [b["submission_id"] for b in found["bids"]] == ["2026-03-01_darpa_swarm"]
    assert "award_value" not in found["bids"][0] and "requested_value" not in found["bids"][0]
    assert "250000" not in found["text"] and "300000" not in found["text"] and "Too early" in found["text"]


def test_the_new_tools_are_read_tools_a_model_can_be_given() -> None:
    names = {t.name: t for t in tools.all_tools()}
    for name in ("search_calls", "top_ten", "past_bids"):
        assert names[name].permission == "read"


# --------------------------------------------------------------------------- run.py --assistant

def test_company_facts_reads_the_reference_live_and_never_hands_over_a_sensitive_item(ledger_db: str) -> None:
    facts_tool = run.company_facts_tool()
    found = facts_tool.run(query="clearance pricing facility")
    assert "F-12" not in found["text"] and "PP-02" not in found["text"] and "clearance_level" not in found["text"]
    assert all(not item_id.startswith(("F-12", "PP-02")) and "clearance" not in item_id for item_id in found["ids"])
    everything = facts_tool.run()
    assert everything["ids"] and "SENSITIVE" not in everything["text"]
    assert "–" not in everything["text"] and "—" not in everything["text"]


def test_the_assistant_answers_a_waiting_question_and_records_what_it_cost(ledger_db: str) -> None:
    seed("samgov-1", "SAM.gov", "yes", 20.5)
    asked = lq.ask_question("t-1", "David Wood", "Brief samgov-1", "/calls")
    model = ScriptedGrok(asks(("brief_call", {"call_id": "samgov-1"})), says("It is due in 20 days."))
    assert run.run_assistant(model=model, max_questions=1, poll_s=0) == 0
    row = lq.get_question(asked)
    assert row["state"] == "done" and row["answer"] == "It is due in 20 days." and row["model"] == "grok-4.7"
    assert json.loads(row["tools"])[0]["name"] == "brief_call"
    # 300 input tokens at $2, 50 cached at $0.50 and 50 output at $6, per million
    assert row["cost_usd"] == pytest.approx((300 * 2 + 50 * 0.5 + 50 * 6) / 1_000_000)
    assert lq.get_worker(run.ASSISTANT)["state"] == "stopped"


def test_over_the_day_s_budget_a_question_gets_an_apology_not_an_answer(ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASSISTANT_DAILY_USD", "0.10")
    spent = lq.ask_question("t", "David Wood", "earlier", None)
    lq.claim_next_question()
    lq.finish_question(spent, "done", "a", cost_usd=0.11)
    asked = lq.ask_question("t", "David Wood", "now", None)
    assert run.run_assistant(model=ScriptedGrok(), max_questions=1, poll_s=0) == 0
    row = lq.get_question(asked)
    assert row["state"] == "failed" and "budget" in row["answer"]


def test_when_grok_fails_the_question_says_so_and_the_assistant_carries_on(ledger_db: str) -> None:
    class Down:
        def respond(self, items: Any, tool_defs: Any) -> grok.Turn:
            raise grok.GrokError("xAI answered 503")

    first = lq.ask_question("t", "David Wood", "one", None)
    second = lq.ask_question("t", "David Wood", "two", None)
    assert run.run_assistant(model=Down(), max_questions=2, poll_s=0) == 0
    for asked in (first, second):
        row = lq.get_question(asked)
        assert row["state"] == "failed" and "Try again" in row["answer"]
