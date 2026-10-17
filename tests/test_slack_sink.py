from __future__ import annotations

import json

import pytest

from ledger import queries as lq
from slack import sink


class FakeClient:
    """Scripted Slack Web API. responses maps method -> list of payloads (popped in order)."""

    def __init__(self, responses: dict[str, list[dict | None]] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[tuple[str, dict, bool]] = []

    def call(self, method: str, params: dict, post: bool = True):
        self.calls.append((method, params, post))
        queue = self.responses.get(method)
        if queue:
            return queue.pop(0)
        if method == "chat.postMessage":
            return {"ok": True, "ts": f"17000.{len(self.calls):04d}", "channel": params["channel"]}
        return {"ok": True}


ROW = {"id": "vulcan-1", "title": "AI <Scribe>", "url": "https://vulcan-sof.com/x", "ai_verdict": "yes",
       "ai_reasoning": "fits", "due_date": "01 NOV 2026", "type": "OTA Prototype", "match_tier": "tight", "portal": "Vulcan SOF"}


def test_card_blocks_and_text() -> None:
    blocks = sink.card_blocks(ROW)
    assert blocks[0]["text"]["text"].startswith("\U0001F7E2 yes  <https://vulcan-sof.com/x|AI (Scribe)>")
    fields = [f["text"] for f in blocks[1]["fields"]]
    assert fields == ["*Due*\n01 NOV 2026", "*Type*\nOTA Prototype", "*Match tier*\ntight"]
    assert blocks[2]["text"]["text"] == "fits"
    assert "`vulcan-1`" in blocks[3]["elements"][0]["text"]
    assert json.dumps(blocks)   # serialisable
    text = sink.card_text(ROW)
    assert text.startswith("[YES] AI <Scribe>") and "id: vulcan-1" in text


def test_post_call_sets_slack_columns(ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123")
    run = lq.start_run("Vulcan SOF")
    lq.upsert_call({"id": "vulcan-1", "portal": "Vulcan SOF", "title": "AI Scribe"}, run)
    client = FakeClient()
    ts = sink.post_call({**ROW, "id": "vulcan-1"}, client)
    assert ts == "17000.0001"
    row = lq.get_call("vulcan-1")
    assert row and row["slack_channel"] == "C123" and row["slack_ts"] == ts and row["posted_at"]
    method, params, _ = client.calls[0]
    assert method == "chat.postMessage" and params["channel"] == "C123" and params["blocks"]


def test_post_call_failure_leaves_row_untouched(ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123")
    run = lq.start_run("Vulcan SOF")
    lq.upsert_call({"id": "vulcan-2", "portal": "Vulcan SOF", "title": "x"}, run)
    assert sink.post_call({**ROW, "id": "vulcan-2"}, FakeClient({"chat.postMessage": [None]})) is None
    assert lq.get_call("vulcan-2")["slack_ts"] is None   # type: ignore[index]


def test_summary_text() -> None:
    text = sink.summary_text({"portal": "Vulcan SOF", "scanned": 60, "new": 3, "yes": 1, "maybe": 2, "elapsed": 171.4})
    assert text.startswith("*Vulcan SOF scan*: 60 calls scanned, 3 new (1 yes, 2 maybe), 171s.")
    assert "note:" in text


def test_status_from_reactions_priority() -> None:
    assert sink.status_from_reactions([{"name": "+1", "users": ["U1"]}]) == ("pursue", "U1")
    assert sink.status_from_reactions([{"name": "+1", "users": ["U1"]}, {"name": "x", "users": ["U2"]}]) == ("dismissed", "U2")
    assert sink.status_from_reactions([{"name": "thumbsdown", "users": ["U3"]}, {"name": "white_check_mark", "users": ["U4"]}]) == ("submitted", "U4")
    assert sink.status_from_reactions([{"name": "eyes", "users": ["U1"]}]) is None
    assert sink.status_from_reactions([]) is None


def _seed_posted(call_id: str, title: str) -> None:
    run = lq.start_run("Vulcan SOF")
    lq.upsert_call({"id": call_id, "portal": "Vulcan SOF", "title": title}, run)
    lq.set_review(call_id, "yes", "r")
    lq.set_slack(call_id, "C123", f"{call_id}.ts")


def test_collect_feedback_reaction_note_and_dismiss(ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123")
    _seed_posted("vulcan-a", "A")
    _seed_posted("vulcan-b", "B")
    _seed_posted("vulcan-c", "C")
    client = FakeClient({
        "reactions.get": [
            {"ok": True, "message": {"reactions": [{"name": "-1", "users": ["UDAVID"]}]}},
            {"ok": True, "message": {"reactions": [{"name": "x", "users": ["UDAVID"]}]}},
            {"ok": True, "message": {"reactions": []}},
        ],
        "conversations.replies": [
            {"ok": True, "messages": [
                {"ts": "vulcan-a.ts", "text": "card"},
                {"ts": "1700000001.000100", "user": "UDAVID", "text": "Note: hardware-heavy, not us"},
                {"ts": "1700000002.000100", "user": "UOTHER", "text": "Just to note, this one seems hardware heavy"},
                {"ts": "1700000003.000100", "user": "UBOT", "bot_id": "B1", "text": "bot echo, ignored"},
                {"ts": "1700000004.000100", "user": "USYS", "subtype": "channel_join", "text": "joined"},
            ]},
            {"ok": True, "messages": [{"ts": "vulcan-b.ts", "text": "card"}]},
            {"ok": True, "messages": [{"ts": "vulcan-c.ts", "text": "card"}]},
        ],
    })
    sleeps: list[float] = []
    changes = sink.collect_feedback(client, sleep=sleeps.append)
    assert [c["id"] for c in changes] == ["vulcan-a", "vulcan-b"]

    a = lq.get_call("vulcan-a")
    assert a and a["human_status"] == "not_relevant" and a["human_by"] == "UDAVID" and a["human_at"]
    assert a["human_notes"] == ("[2023-11-14T22:13:21Z UDAVID] hardware-heavy, not us
"
                                "[2023-11-14T22:13:22Z UOTHER] Just to note, this one seems hardware heavy")
    b = lq.get_call("vulcan-b")
    assert b and b["human_status"] == "dismissed"
    assert ("chat.delete", {"channel": "C123", "ts": "vulcan-b.ts"}, True) in client.calls
    c = lq.get_call("vulcan-c")
    assert c and c["human_status"] is None
    assert [m for m, _, _ in client.calls].count("chat.delete") == 1
    assert all(s == sink.PAUSE_S for s in sleeps) and len(sleeps) >= 6
    assert lq.pending_feedback()[0]["id"] == "vulcan-c"


def test_collect_feedback_does_not_duplicate_notes(ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123")
    _seed_posted("vulcan-d", "D")
    replies = {"ok": True, "messages": [{"ts": "vulcan-d.ts"}, {"ts": "1700000001.5", "user": "U1", "text": "note: keep an eye on this"}]}
    client = FakeClient({"reactions.get": [{"ok": True, "message": {"reactions": []}}] * 2,
                         "conversations.replies": [replies, replies]})
    sink.collect_feedback(client, sleep=lambda s: None)
    sink.collect_feedback(client, sleep=lambda s: None)
    notes = lq.get_call("vulcan-d")["human_notes"]   # type: ignore[index]
    assert notes.count("keep an eye on this") == 1


def test_collect_feedback_survives_slack_failures(ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123")
    _seed_posted("vulcan-e", "E")
    client = FakeClient({"reactions.get": [None], "conversations.replies": [None]})
    assert sink.collect_feedback(client, sleep=lambda s: None) == []
    assert lq.get_call("vulcan-e")["human_status"] is None   # type: ignore[index]


def test_client_without_token_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    client = sink.SlackClient(token="")
    assert client.call("chat.postMessage", {"channel": "C1", "text": "x"}) is None


def test_decided_cards_still_collect_notes_and_late_x(ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123")
    _seed_posted("vulcan-p", "P")
    _seed_posted("vulcan-q", "Q")
    lq.set_human("vulcan-p", "not_relevant", "UDAVID")   # decided earlier, note arrives later
    lq.set_human("vulcan-q", "pursue", "UDAVID")         # decided earlier, X arrives later
    client = FakeClient({
        "reactions.get": [
            {"ok": True, "message": {"reactions": [{"name": "-1", "users": ["UDAVID"]}, {"name": "+1", "users": ["UOTHER"]}]}},
            {"ok": True, "message": {"reactions": [{"name": "+1", "users": ["UDAVID"]}, {"name": "x", "users": ["UDAVID"]}]}},
        ],
        "conversations.replies": [
            {"ok": True, "messages": [{"ts": "vulcan-p.ts"}, {"ts": "1700000009.1", "user": "UDAVID", "text": "note: hardware-heavy, not us"}]},
            {"ok": True, "messages": [{"ts": "vulcan-q.ts"}]},
        ],
    })
    changes = sink.collect_feedback(client, sleep=lambda s: None)
    p = lq.get_call("vulcan-p")
    assert p and p["human_status"] == "not_relevant" and "hardware-heavy, not us" in p["human_notes"]
    q = lq.get_call("vulcan-q")
    assert q and q["human_status"] == "dismissed"
    assert ("chat.delete", {"channel": "C123", "ts": "vulcan-q.ts"}, True) in client.calls
    assert sorted(c["id"] for c in changes) == ["vulcan-p", "vulcan-q"]


def test_dismissed_cards_are_not_polled(ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123")
    _seed_posted("vulcan-z", "Z")
    lq.set_human("vulcan-z", "dismissed", "UDAVID")
    client = FakeClient()
    assert sink.collect_feedback(client, sleep=lambda s: None) == []
    assert client.calls == []
