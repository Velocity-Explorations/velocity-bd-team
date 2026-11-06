"""The fit score (PRO-487): how well a call suits Velocity, 0 to 100, from the team's rating of each tag, keyword and
NAICS code. Main work counts most. A Never rules a call out only on its main work, its type or its NAICS code, and on
what the judges name only when they agree. The ratings here are made up; the team's live in the ledger, never in the repo."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import run
from ledger import queries as lq
from review import fit
from tests.test_reviewer import FakeModel

RATINGS = {
    "work.software": "core", "work.services": "never", "work.hardware": "poor", "work.cyber": "neutral",
    "customer.ussf": "core", "customer.navy": "good", "customer.other-buyer": "neutral",
    "type.ota": "core", "type.proposal": "good", "type.sole-source": "never",
    "access.small-business-set-aside": "core",
    "keyword.ai": "core", "keyword.information": "neutral", "keyword.sensor": "poor",
    "naics.541511": "good", "naics.541715": "neutral", "naics-sector.23": "never",
    "notice.presolicitation": "poor", "notice.special-notice": "neutral",
}
BOTH_SOFTWARE = {"claude": "Software", "grok": "Software"}


def call(**fields: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"id": "c-1", "title": "A call", "description": "", "naics_code": "", "type": "",
                           "matched_keywords": "[]"}
    row.update(fields)
    if isinstance(row["matched_keywords"], list):
        row["matched_keywords"] = json.dumps(row["matched_keywords"])
    return row


def test_a_call_with_nothing_but_neutral_ratings_scores_fifty() -> None:
    got = fit.score_call(call(), {}, {"claude": "Cyber", "grok": "Cyber"}, RATINGS)
    assert got is not None and got.score == 50 and got.band == "possible"


def test_main_work_counts_most_and_every_rated_part_adds_to_the_score() -> None:
    plain = fit.score_call(call(), {}, BOTH_SOFTWARE, RATINGS)
    assert plain is not None and plain.score == 73 and plain.band == "strong"   # 0.45 at core, the rest neutral
    weak = fit.score_call(call(), {}, {"claude": "Hardware", "grok": "Hardware"}, RATINGS)
    assert weak is not None and weak.score == 39 and weak.band == "weak"
    full = fit.score_call(
        call(naics_code="541511", matched_keywords=["ai"], description="uses AI"),
        {"rule": ["USSF", "OTA", "Small business set-aside"], "claude": ["Software"]}, BOTH_SOFTWARE, RATINGS)
    assert full is not None and full.score == 98   # all core but the NAICS code at good
    assert "Main work Software: core" in full.why and "NAICS 541511: good" in full.why and "Customer USSF: core" in full.why


def test_a_call_no_judge_has_named_the_main_work_of_has_no_score_yet() -> None:
    assert fit.score_call(call(), {"claude": ["Software"]}, {}, RATINGS) is None
    assert fit.score_call(call(), {"claude": ["Software"]}, {"claude": None, "grok": None}, RATINGS) is None


def test_never_on_main_work_rules_a_call_out_only_when_the_judges_agree() -> None:
    both = fit.score_call(call(), {}, {"claude": "Services", "grok": "Services"}, RATINGS)
    assert both is not None and both.score == 0 and both.band == fit.RULED_OUT
    assert both.why == ["Ruled out: main work Services is rated never"]
    alone = fit.score_call(call(), {}, {"claude": "Services"}, RATINGS)
    assert alone is not None and alone.band == fit.RULED_OUT   # the only judge to answer
    split = fit.score_call(call(), {}, {"claude": "Services", "grok": "Software"}, RATINGS)
    assert split is not None and split.band != fit.RULED_OUT and split.score == 39   # counts as poor, the lower of the two
    assert "Main work Services or Software: judges differ" in split.why


def test_a_work_tag_that_is_not_the_main_work_never_rules_a_call_out() -> None:
    got = fit.score_call(call(), {"claude": ["Software", "Services"], "grok": ["Services"]}, BOTH_SOFTWARE, RATINGS)
    assert got is not None and got.band == "strong"


def test_never_on_a_naics_code_or_its_sector_rules_a_call_out() -> None:
    got = fit.score_call(call(naics_code="236220"), {}, BOTH_SOFTWARE, RATINGS)
    assert got is not None and got.band == fit.RULED_OUT and got.why == ["Ruled out: NAICS 236220 is rated never"]
    assert fit.sector_of("236220") == "23" and fit.sector_of("325120") == "31-33" and fit.sector_of("481212") == "48-49"
    unrated = fit.score_call(call(naics_code="541611"), {}, BOTH_SOFTWARE, RATINGS)
    assert unrated is not None and unrated.score == 73   # a code nobody rated counts as neutral


def test_never_on_a_type_rules_a_call_out_when_a_rule_set_it_or_the_judges_agree() -> None:
    agreed = fit.score_call(call(), {"claude": ["Sole source"], "grok": ["Sole source"]}, BOTH_SOFTWARE, RATINGS)
    assert agreed is not None and agreed.band == fit.RULED_OUT
    split = fit.score_call(call(), {"claude": ["Sole source"], "grok": ["Proposal"]}, BOTH_SOFTWARE, RATINGS)
    assert split is not None and split.band != fit.RULED_OUT
    ruled = fit.score_call(call(), {"rule": ["OTA"], "claude": ["Sole source"]}, BOTH_SOFTWARE, RATINGS)
    assert ruled is not None and ruled.band != fit.RULED_OUT and "Type OTA: core" in ruled.why   # the rule's type wins


def test_a_keyword_counts_only_as_a_whole_word_and_a_neutral_one_adds_nothing() -> None:
    inside = fit.score_call(call(matched_keywords=["ai"], description="more details are available by email"),
                            {}, BOTH_SOFTWARE, RATINGS)
    assert inside is not None and inside.score == 73
    whole = fit.score_call(call(matched_keywords=["ai"], title="AI-enabled tool"), {}, BOTH_SOFTWARE, RATINGS)
    assert whole is not None and whole.score == 78
    neutral = fit.score_call(call(matched_keywords=["ai", "information"], title="AI information"), {}, BOTH_SOFTWARE, RATINGS)
    assert neutral is not None and neutral.score == 78
    mixed = fit.score_call(call(matched_keywords=["ai", "sensor"], title="AI sensor"), {}, BOTH_SOFTWARE, RATINGS)
    assert mixed is not None and mixed.score == 74   # the mean of core and poor


def test_a_rated_notice_type_moves_the_type_part_and_a_neutral_one_does_not() -> None:
    neutral = fit.score_call(call(type="Special notice"), {"claude": ["OTA"]}, BOTH_SOFTWARE, RATINGS)
    plain = fit.score_call(call(), {"claude": ["OTA"]}, BOTH_SOFTWARE, RATINGS)
    poor = fit.score_call(call(type="Presolicitation"), {"claude": ["OTA"]}, BOTH_SOFTWARE, RATINGS)
    assert neutral is not None and plain is not None and poor is not None
    assert neutral.score == plain.score and poor.score < plain.score


def test_the_best_customer_counts_and_a_tag_nobody_rated_is_neutral() -> None:
    both = fit.score_call(call(), {"rule": ["Navy"], "grok": ["USSF"]}, BOTH_SOFTWARE, RATINGS)
    one = fit.score_call(call(), {"rule": ["Navy"]}, BOTH_SOFTWARE, RATINGS)
    unrated = fit.score_call(call(), {"rule": ["Army"]}, BOTH_SOFTWARE, RATINGS)
    assert both is not None and one is not None and unrated is not None
    assert both.score > one.score > unrated.score == 73


def test_both_judges_saying_no_makes_a_call_weak_at_best() -> None:
    both_no = fit.score_call(call(), {}, BOTH_SOFTWARE, RATINGS, {"claude": "no", "grok": "no"})
    assert both_no is not None and both_no.score == 49 and both_no.band == "weak" and "Both judges said no" in both_no.why
    split = fit.score_call(call(), {}, BOTH_SOFTWARE, RATINGS, {"claude": "yes", "grok": "no"})
    alone = fit.score_call(call(), {}, BOTH_SOFTWARE, RATINGS, {"claude": "no"})
    assert split is not None and alone is not None and split.score == alone.score == 73
    already_weak = fit.score_call(call(), {}, {"claude": "Hardware", "grok": "Hardware"}, RATINGS, {"claude": "no", "grok": "no"})
    assert already_weak is not None and already_weak.score == 39


def seed(call_id: str, **fields: Any) -> None:
    run_id = lq.start_run("Vulcan SOF")
    lq.upsert_call({"id": call_id, "portal": "Vulcan SOF", "title": "C2 software", "description": "software", **fields}, run_id)
    lq.set_filter(call_id, "kept", tier="broad", keywords=["software"])
    lq.set_review(call_id, "maybe", "ok")


def test_the_ratings_load_from_the_page_export_and_replace_the_last_ones(ledger_db: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    export = tmp_path / "ratings"
    export.mkdir()
    (export / "work.software.json").write_text(json.dumps({"key": "work.software", "section": "work", "name": "Software",
                                                           "rating": "core", "note": "yes"}), encoding="utf-8")
    (export / "work.cyber.json").write_text(json.dumps({"id": "work.cyber", "data": {
        "key": "work.cyber", "section": "work", "name": "Cyber", "rating": "poor", "note": ""}}), encoding="utf-8")
    (export / "noted.json").write_text(json.dumps({"key": "work.space", "section": "work", "name": "Space", "rating": None,
                                                   "note": "ask"}), encoding="utf-8")
    assert run.load_fit_ratings(str(export)) == 0
    assert "Loaded 2 fit rating(s)" in capsys.readouterr().out
    assert lq.fit_ratings() == {"work.software": "core", "work.cyber": "poor"}
    (export / "work.cyber.json").unlink()
    assert run.load_fit_ratings(str(export)) == 0
    assert lq.fit_ratings() == {"work.software": "core"}   # a rating cleared on the page goes


def test_a_bad_rating_in_the_export_stops_the_load(ledger_db: str, tmp_path: Path) -> None:
    (tmp_path / "bad.json").write_text(json.dumps({"key": "work.software", "section": "work", "name": "Software",
                                                   "rating": "great"}), encoding="utf-8")
    with pytest.raises(ValueError, match="great"):
        run.load_fit_ratings(str(tmp_path))


def test_fit_scores_are_stored_with_their_reasons_for_calls_the_judges_have_named_a_main_work(ledger_db: str, capsys: pytest.CaptureFixture[str]) -> None:
    lq.save_fit_ratings([{"key": "work.software", "section": "work", "name": "Software", "rating": "core", "note": ""},
                         {"key": "work.services", "section": "work", "name": "Services", "rating": "never", "note": ""}])
    for call_id in ("named", "ruled-out", "unnamed"):
        seed(call_id)
    lq.add_judgment("named", "claude", "m", "yes", "ok")
    lq.set_main_work("named", "claude", "Software")
    lq.add_judgment("ruled-out", "claude", "m", "yes", "ok")
    lq.set_main_work("ruled-out", "claude", "Services")
    lq.add_judgment("unnamed", "claude", "m", "yes", "ok")
    assert run.fit_scores() == 0
    assert "Scored 2 of 3 call(s): 1 strong, 1 ruled out." in capsys.readouterr().out
    named = lq.get_call("named")
    assert named["fit_score"] == 73 and named["fit_band"] == "strong"
    assert "Main work Software: core" in json.loads(named["fit_why"])
    assert lq.get_call("ruled-out")["fit_band"] == fit.RULED_OUT
    assert lq.get_call("unnamed")["fit_score"] is None


def test_a_score_takes_the_judges_newest_verdicts(ledger_db: str) -> None:
    lq.save_fit_ratings([{"key": "work.software", "section": "work", "name": "Software", "rating": "core", "note": ""}])
    seed("named")
    for judge in ("claude", "grok"):
        lq.add_judgment("named", judge, "m", "no", "no")
        lq.set_main_work("named", judge, "Software")
    assert run.fit_scores() == 0
    assert lq.get_call("named")["fit_band"] == "weak"
    lq.add_judgment("named", "grok", "m", "yes", "yes")
    lq.set_main_work("named", "grok", "Software")
    assert run.fit_scores() == 0
    assert lq.get_call("named")["fit_band"] == "strong"


def test_a_dry_run_of_the_scores_writes_nothing(ledger_db: str, capsys: pytest.CaptureFixture[str]) -> None:
    lq.save_fit_ratings([{"key": "work.software", "section": "work", "name": "Software", "rating": "core", "note": ""}])
    seed("named")
    lq.add_judgment("named", "claude", "m", "yes", "ok")
    lq.set_main_work("named", "claude", "Software")
    assert run.fit_scores(dry_run=True) == 0
    assert "Would score 1 of 1 call(s): 1 strong." in capsys.readouterr().out
    assert lq.get_call("named")["fit_score"] is None


def test_without_ratings_nothing_is_scored(ledger_db: str, capsys: pytest.CaptureFixture[str]) -> None:
    seed("named")
    assert run.fit_scores() == 0
    assert "No fit ratings" in capsys.readouterr().out


def test_a_re_judgment_clears_the_old_main_work_until_the_judge_names_one_again(ledger_db: str) -> None:
    seed("named")
    lq.add_judgment("named", "claude", "m", "yes", "ok")
    lq.set_main_work("named", "claude", "Software")
    assert lq.main_work_by_call()["named"] == {"claude": "Software"}
    lq.add_judgment("named", "claude", "m", "no", "changed")
    assert lq.main_work_by_call().get("named", {}).get("claude") is None


def test_refilter_drops_calls_the_new_rules_no_longer_keep_and_a_dry_run_writes_nothing(
        ledger_db: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from portals.registry import Portal
    from portals.shared.keyword_filter import filter_calls

    settings = tmp_path / "keywords.yaml"
    settings.write_text("broad_keywords:\n  - ai\ntight_keywords: []\nblocklist_patterns: []\n", encoding="utf-8")
    run_id = lq.start_run("Test portal")
    for call_id, title in (("noise", "details are available by email"), ("real", "AI for operators")):
        lq.upsert_call({"id": call_id, "portal": "Test portal", "title": title, "description": ""}, run_id)
        lq.set_filter(call_id, "kept", tier="broad", keywords=["ai"])
    portal = Portal(slug="test", name="Test portal", fetch=lambda *_a, **_k: None,
                    filter=lambda rows: filter_calls(rows, settings), keywords=settings)
    monkeypatch.setattr(run.registry, "discover", lambda: [portal])
    assert run.refilter(dry_run=True) == 0
    assert "Would drop 1 and would keep 0 more call(s)." in capsys.readouterr().out
    assert lq.get_call("noise")["filter_result"] == "kept"
    assert run.refilter() == 0
    assert "Dropped 1 and kept 0 more call(s)." in capsys.readouterr().out
    assert lq.get_call("noise")["filter_result"] == "rejected" and lq.get_call("real")["filter_result"] == "kept"


def open_seed(call_id: str, due: str | None = "2099-01-15", status: str | None = None, closed: bool = False) -> None:
    seed(call_id, due_date=due, extra=json.dumps({"vulcan_closed": closed}))
    if status:
        lq.set_human(call_id, status, "David")


ANSWER = "VERDICT: yes\nREASON: software\nTAGS: Software\nMAIN WORK: Software\nSUMMARY: Short."


def test_rejudging_covers_open_undecided_calls_and_a_rerun_skips_those_already_done(
        ledger_db: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    open_seed("open-1")
    open_seed("no-deadline", due=None)
    open_seed("past", due="2020-01-01")
    open_seed("closed", closed=True)
    open_seed("decided", status="pursue")
    claude = FakeModel([ANSWER] * 2)
    grok = FakeModel([ANSWER, "not an answer", "not an answer"])
    grok.model = "grok-4.7"
    monkeypatch.setattr(run, "review_model", lambda: claude)
    monkeypatch.setattr(run, "grok_model", lambda: grok)
    monkeypatch.setattr(run, "grok_enabled", lambda: True)

    assert run.rejudge_open(dry_run=True) == 0
    planned = capsys.readouterr().out
    assert "2 open calls for Claude, 2 for Grok" in planned and "about $" in planned
    assert claude.prompts == [] and lq.get_call("open-1")["ai_verdict"] == "maybe"

    assert run.rejudge_open() == 0
    done = capsys.readouterr().out
    assert "Claude judged 2 of 2 call(s); Grok judged 1 of 2." in done
    assert lq.get_call("open-1")["ai_verdict"] == "yes" and lq.get_call("past")["ai_verdict"] == "maybe"
    named = lq.main_work_by_call()
    assert sorted(named) == ["no-deadline", "open-1"] and sum("grok" in judges for judges in named.values()) == 1

    grok.script = [ANSWER]
    assert run.rejudge_open() == 0   # only Grok's unanswered call is asked again
    assert "Claude judged 0 of 0 call(s); Grok judged 1 of 1." in capsys.readouterr().out
    assert len(claude.prompts) == 2
    assert lq.main_work_by_call() == {call_id: {"claude": "Software", "grok": "Software"} for call_id in ("no-deadline", "open-1")}
