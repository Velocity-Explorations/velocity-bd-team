from __future__ import annotations

import json
from datetime import datetime, timezone

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

    def methods(self) -> list[str]:
        return [m for m, _, _ in self.calls]

    def params_of(self, method: str) -> list[dict]:
        return [p for m, p, _ in self.calls if m == method]


ROW = {"id": "vulcan-1", "title": "AI <Scribe>", "url": "https://vulcan-sof.com/x", "ai_verdict": "yes",
       "ai_reasoning": "fits", "due_date": "01 NOV 2026", "type": "OTA Prototype", "match_tier": "tight", "portal": "Vulcan SOF"}


@pytest.fixture(autouse=True)
def no_dashboard_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sink, "dashboard_url", lambda: "")


# ------------------------------------------------------------------------- cards

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


def test_card_links_to_the_dashboard_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sink, "dashboard_url", lambda: "https://bd.example.invalid")
    context = sink.card_blocks(ROW)[-1]["elements"][0]["text"]
    assert "<https://bd.example.invalid|Decide on the dashboard>" in context


def test_render_card_shows_the_decision_first() -> None:
    decided = {**ROW, "human_status": "not_relevant", "human_by": "David Wood", "human_at": "2026-10-17T10:32:57Z"}
    blocks = sink.render_card(decided)
    head = blocks[0]
    assert head["block_id"] == "decision:not_relevant:2026-10-17T10:32:57Z"
    text = head["text"]["text"]
    assert "*Decision: Not relevant*" in text and "by David Wood" in text
    assert "<!date^1792233177^{date_short_pretty} at {time}|2026-10-17 10:32 UTC>" in text
    assert blocks[1:] == sink.card_blocks(decided)
    assert sink.render_card(ROW) == sink.card_blocks(ROW)   # undecided: no decision block
    legacy = {**ROW, "human_status": "pursue", "human_by": "U08V7ULPH1N", "human_at": "2026-10-16T12:15:17Z"}
    assert "by <@U08V7ULPH1N>" in sink.render_card(legacy)[0]["text"]["text"]


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


def test_summary_points_to_the_dashboard(monkeypatch: pytest.MonkeyPatch) -> None:
    summary = {"portal": "Vulcan SOF", "scanned": 60, "new": 3, "yes": 1, "maybe": 2, "elapsed": 171.4}
    text = sink.summary_text(summary)
    assert text.startswith("*Vulcan SOF scan*: 60 calls scanned, 3 new (1 yes, 2 maybe), 171s.")
    assert "Decide on the dashboard" in text and "thread" in text and "React" not in text
    monkeypatch.setattr(sink, "dashboard_url", lambda: "https://bd.example.invalid")
    assert "<https://bd.example.invalid|the dashboard>" in sink.summary_text(summary)


def block_texts(blocks: list[dict]) -> str:
    out = []
    for block in blocks:
        if "text" in block:
            out.append(block["text"]["text"])
        out += [element.get("text", "") for element in block.get("elements", [])]
    return "\n".join(out)


def test_weekly_summary_message_reads_as_a_brief(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sink, "dashboard_url", lambda: "https://bd.example.invalid")
    pick = {"id": "v-1", "title": "IT & Cyber <Ops>", "url": "https://portal.invalid/1", "verdict": "yes",
            "deadline": "27 OCT 2026 : 21:59 MDT", "days_left": 7, "reason": "Builds C2 software."}
    summary = {
        "portal": "Vulcan SOF", "days": 7, "waiting": 13,
        "new": {"total": 3, "by_verdict": {"yes": 1, "maybe": 2}, "calls": []},
        "top_picks": [pick],
        "closing_soon": [
            {"id": "v-2", "title": "Picked call", "url": None, "deadline": "22 OCT 2026 : 10:00 MDT", "days_left": 2,
             "status": "pursue"},
            {**pick, "status": None},
        ],
        "decided": [
            {"id": "v-3", "title": "Old call", "url": None, "status": "dismissed", "by": "U08V7ULPH1N", "at": "x"},
            {"id": "v-4", "title": "New call", "url": None, "status": "pursue", "by": "David Wood", "at": "y"},
        ],
    }
    health = [{"name": "Vulcan SOF", "text": "Vulcan SOF: the last scan completed at 19 Oct 06:03."}]
    text, blocks = sink.weekly_summary_message([summary], health, now=datetime(2026, 10, 21, tzinfo=timezone.utc))
    body = block_texts(blocks)
    assert blocks[0]["type"] == "header" and blocks[0]["text"]["text"] == "Weekly BD summary, week of 19 Oct"
    assert "*Vulcan SOF*: 3 new this week, 13 open calls waiting for a decision" in body
    assert "<https://bd.example.invalid/?state=open|Open the review queue>" in body
    assert "1. <https://portal.invalid/1|IT &amp; Cyber &lt;Ops&gt;>: yes, closes Tue 27 Oct (7 days)" in body
    assert "Builds C2 software." in body
    assert "Picked call, closes Thu 22 Oct (2 days)" in body and body.count("IT &amp; Cyber") == 1
    assert "Dismissed: Old call (decided in Slack)" in body and "Pursue: New call (David Wood)" in body
    assert "U08V7ULPH1N" not in json.dumps(blocks)
    assert "Scraper: Vulcan SOF: the last scan completed at 19 Oct 06:03." in body
    assert text == "Weekly BD summary, week of 19 Oct. Vulcan SOF: 3 new, 13 waiting for a decision."
    assert sink._closes("15 APR 2028 : 22:59 MDT", 543) == "closes Sat 15 Apr 2028 (543 days)"


# ---------------------------------------------------------------------- feedback

def _seed_posted(call_id: str, title: str, status: str | None = None, by: str | None = None) -> None:
    run = lq.start_run("Vulcan SOF")
    lq.upsert_call({"id": call_id, "portal": "Vulcan SOF", "title": title}, run)
    lq.set_review(call_id, "yes", "r")
    lq.set_slack(call_id, "C123", f"{call_id}.ts")
    if status:
        lq.set_human(call_id, status, by or "David Wood", "2026-10-17T10:00:00Z")


def _thread(ts: str, *replies: dict, blocks: list | None = None) -> dict:
    """conversations.replies payload: the card itself first, then the replies."""
    return {"ok": True, "messages": [{"ts": ts, "bot_id": "B1", "blocks": blocks or []}, *replies]}


def test_reactions_are_not_read_and_replies_become_notes(ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123")
    _seed_posted("vulcan-a", "A")
    client = FakeClient({"conversations.replies": [_thread(
        "vulcan-a.ts",
        {"ts": "1700000001.000100", "user": "UDAVID", "text": "Note: hardware-heavy, not us"},
        {"ts": "1700000002.000100", "user": "UOTHER", "text": "Just to note, this one seems hardware heavy"},
        {"ts": "1700000003.000100", "user": "UBOT", "bot_id": "B1", "text": "bot echo, ignored"},
        {"ts": "1700000004.000100", "user": "USYS", "subtype": "channel_join", "text": "joined"},
    )]})
    changes = sink.collect_feedback(client, sleep=lambda s: None)

    assert "reactions.get" not in client.methods()
    a = lq.get_call("vulcan-a")
    assert a and a["human_status"] is None
    assert a["human_notes"] == (
        "[2023-11-14T22:13:21Z UDAVID] hardware-heavy, not us"
        + "\n[2023-11-14T22:13:22Z UOTHER] Just to note, this one seems hardware heavy"
    )
    assert changes == [{
        "id": "vulcan-a", "title": "A", "card_updated": False,
        "notes": ["hardware-heavy, not us", "Just to note, this one seems hardware heavy"],
    }]
    assert "chat.update" not in client.methods()   # undecided card already matches


def test_card_is_edited_once_to_show_a_dashboard_decision(ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123")
    _seed_posted("vulcan-b", "B", status="not_relevant")
    client = FakeClient({"conversations.replies": [_thread("vulcan-b.ts")]})
    changes = sink.collect_feedback(client, sleep=lambda s: None)

    updates = client.params_of("chat.update")
    assert len(updates) == 1 and updates[0]["channel"] == "C123" and updates[0]["ts"] == "vulcan-b.ts"
    assert updates[0]["blocks"][0]["block_id"] == "decision:not_relevant:2026-10-17T10:00:00Z"
    assert updates[0]["text"].startswith("Decision: Not relevant by David Wood")
    assert changes == [{"id": "vulcan-b", "title": "B", "notes": [], "card_updated": True}]

    again = FakeClient({"conversations.replies": [_thread("vulcan-b.ts", blocks=updates[0]["blocks"])]})
    assert sink.collect_feedback(again, sleep=lambda s: None) == []
    assert "chat.update" not in again.methods()


def test_dismissed_on_the_dashboard_is_shown_not_deleted(ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123")
    _seed_posted("vulcan-c", "C", status="dismissed")
    client = FakeClient({"conversations.replies": [_thread("vulcan-c.ts")]})
    sink.collect_feedback(client, sleep=lambda s: None)
    assert "chat.update" in client.methods() and "chat.delete" not in client.methods()
    assert "Decision: Dismissed" in client.params_of("chat.update")[0]["blocks"][0]["text"]["text"]


def test_a_cleared_decision_is_removed_from_the_card(ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123")
    _seed_posted("vulcan-d", "D")
    stale = sink.render_card({**lq.get_call("vulcan-d"), "human_status": "pursue", "human_by": "David Wood",   # type: ignore[dict-item]
                              "human_at": "2026-10-17T09:00:00Z"})
    client = FakeClient({"conversations.replies": [_thread("vulcan-d.ts", blocks=stale)]})
    sink.collect_feedback(client, sleep=lambda s: None)
    updates = client.params_of("chat.update")
    assert len(updates) == 1
    assert not any(str(b.get("block_id", "")).startswith("decision:") for b in updates[0]["blocks"])


def test_cards_deleted_by_the_old_x_reaction_are_skipped(ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123")
    _seed_posted("vulcan-e", "E", status="dismissed", by="U08V7ULPH1N")
    client = FakeClient()
    assert sink.collect_feedback(client, sleep=lambda s: None) == []
    assert client.calls == []


def test_notes_are_not_duplicated_across_polls(ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123")
    _seed_posted("vulcan-f", "F")
    reply = {"ts": "1700000001.5", "user": "U1", "text": "note: keep an eye on this"}
    client = FakeClient({"conversations.replies": [_thread("vulcan-f.ts", reply), _thread("vulcan-f.ts", reply)]})
    sink.collect_feedback(client, sleep=lambda s: None)
    sink.collect_feedback(client, sleep=lambda s: None)
    assert lq.get_call("vulcan-f")["human_notes"].count("keep an eye on this") == 1   # type: ignore[index]


def test_an_unreadable_thread_changes_nothing(ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C123")
    _seed_posted("vulcan-g", "G", status="pursue")
    client = FakeClient({"conversations.replies": [None]})
    assert sink.collect_feedback(client, sleep=lambda s: None) == []
    assert client.methods() == ["conversations.replies"]   # no blind chat.update


def test_client_without_token_skips() -> None:
    client = sink.SlackClient(token="")
    assert client.call("chat.postMessage", {"channel": "C1", "text": "x"}) is None
