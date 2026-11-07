"""What kind of listing a call is (David, 7 Nov 2026): a call to respond to now, an umbrella whose calls come under it, or
an announcement with nothing to submit yet. The Top 10 holds calls; umbrellas and announcements get a top 10 of their own."""
from __future__ import annotations

import json
from typing import Any

import pytest

import run as pipeline
from assistant import tools
from ledger import queries as lq
from portals import registry
from review import fit, tags
from tests.test_briefs import scored, seed, this_monday
from tests.test_pipeline import fake_portal, isolated, slack_posts   # noqa: F401  (fixtures)

TAGS = tags.load_tags()


@pytest.mark.parametrize(("by_source", "expected"), [
    ({"rule": ["Forecast", "Announcement"], "claude": ["Call"], "grok": ["Call"]}, "Announcement"),   # the portal says so
    ({"claude": ["Software", "Umbrella"], "grok": ["Call"]}, "Umbrella"),   # the judges differ: Claude's, as for verdicts
    ({"claude": ["Software"], "grok": ["Software", "Call"]}, "Call"),
    ({"rule": ["OTA"], "claude": ["Software"]}, None),   # nobody has said yet
    ({}, None),
])
def test_a_call_s_listing_is_the_rule_s_then_claude_s_then_grok_s(by_source: dict[str, list[str]], expected: str | None) -> None:
    assert tags.listing_of(by_source, TAGS) == expected


def test_scoring_stores_each_call_s_listing_even_before_anything_is_rated(ledger_db: str) -> None:
    seed("umbrella", "SAM.gov", "maybe", 20.5)
    seed("plain", "SAM.gov", "yes", 20.5)
    lq.set_tags("umbrella", "claude", ["Software", "Umbrella"])
    assert fit.score_rows(lq.calls_where()) is None   # nobody has rated anything
    assert lq.get_call("umbrella")["listing"] == "Umbrella"
    assert lq.get_call("plain")["listing"] is None
    lq.set_tags("umbrella", "rule", ["Announcement"])
    fit.score_rows(lq.calls_where())
    assert lq.get_call("umbrella")["listing"] == "Announcement"


def kinds(**listing: str) -> None:
    for call_id, kind in listing.items():
        lq.set_listing(call_id.replace("_", "-"), kind)


def test_the_top_10_holds_calls_and_umbrellas_and_announcements_have_a_top_10_of_their_own(ledger_db: str) -> None:
    scored("call", "yes", "yes", 60)
    scored("no-kind-yet", "maybe", "maybe", 90)   # counts as a call until a judge says otherwise
    scored("umbrella", "yes", "yes", 95)
    scored("announcement", "maybe", "no", 80)
    scored("ruled-out", "yes", "yes", 0)
    kinds(call="Call", umbrella="Umbrella", announcement="Announcement", ruled_out="Umbrella")
    assert [c["id"] for c in tools.top_calls(10)] == ["call", "no-kind-yet"]
    watch = tools.top_watch(10)
    assert [c["id"] for c in watch] == ["umbrella", "announcement"]   # ranked as the Top 10 is: a yes first
    assert [c["listing"] for c in watch] == ["Umbrella", "Announcement"]


def test_each_portal_s_top_picks_are_calls_and_its_waiting_count_takes_in_everything(ledger_db: str) -> None:
    scored("call", "yes", "no", 60)
    scored("umbrella", "yes", "yes", 95)
    kinds(umbrella="Umbrella")
    summary: dict[str, Any] = tools.weekly_summary(None)
    assert [c["id"] for c in summary["top_picks"]] == ["call"]
    assert summary["waiting"] == 2


def test_the_brief_stores_the_top_10_to_watch_beside_the_top_10(isolated, slack_posts, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline, "acquire_lock", lambda *a, **k: pytest.fail("a brief never takes the pipeline lock"))
    monkeypatch.setattr(registry, "discover", lambda: [fake_portal()])
    seed("fake-call", "Fake", "yes", 6.5)
    seed("fake-umbrella", "Fake", "yes", 6.5)
    lq.set_listing("fake-umbrella", "Umbrella")
    assert pipeline.main(["--write-brief"]) == 0
    top = json.loads(next(b for b in lq.briefs_for_week(this_monday()) if b["portal"] is None)["body"])
    assert [c["id"] for c in top["top"]] == ["fake-call"]
    assert [c["id"] for c in top["watch"]] == ["fake-umbrella"]
