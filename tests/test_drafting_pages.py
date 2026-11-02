"""Drafts held to the call's page limit (PRO-565): the outline's page counts become a word budget at Velocity's own rate,
the First draft, the Compliance check and the reviewers write to it, and Final checks cuts a draft that runs over in a
pass of its own and reports the fit. Placeholders are left out of every count, since filling one replaces its words."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from drafting import steps, write
from drafting.prompts import Prompt
from tests.test_drafting_write import EARLIER, Model, _context

OUTLINE = {"pages": 13, "page_limit": "13 designated pages plus a glossary",
           "sections": [{"title": "1. Small Business Concern", "pages": 1, "share": "1 page"},
                        {"title": "2. Technical Merit", "share": "3 pages, about 1,350 words"},
                        {"title": "10. Glossary", "share": "Beyond p. 13"}]}


def outline_step(pursuit_id: int, content: dict[str, Any]) -> None:
    """An approved Outline, made directly in the ledger, whose content holds the page counts."""
    from ledger.db import now_iso, q, tx

    now = now_iso()
    with tx() as conn:
        q(conn, "INSERT INTO pursuit_steps (pursuit_id, step, attempt, state, requested_by, content, queued_at, updated_at) "
                "VALUES (?, 'outline', 1, 'approved', 'David Wood', ?, ?, ?)", (pursuit_id, json.dumps(content), now, now))


def test_the_outlines_page_counts_become_a_word_budget_at_velocitys_rate(ledger_db: str, tmp_path: Path) -> None:
    """Velocity's submitted technical volumes run about 380 words a page, and the winner the 29 Oct trial was set
    against ran 315; the outline had guessed 450."""
    ctx = _context(tmp_path, Model(), "draft", EARLIER)
    assert write.page_budget(ctx) is None                      # no outline yet: no budget
    outline_step(ctx.pursuit["id"], OUTLINE)
    budget = write.page_budget(ctx)
    assert write.WORDS_PER_PAGE == 350 and (budget.pages, budget.words) == (13, 4_550)
    assert budget.sections == (("1. Small Business Concern", 1.0), ("2. Technical Merit", 3.0))   # the glossary has none


def test_a_page_limit_given_only_in_words_is_read_from_the_text(ledger_db: str, tmp_path: Path) -> None:
    ctx = _context(tmp_path, Model(), "draft", EARLIER)
    outline_step(ctx.pursuit["id"], {"page_limit": "a white paper of no more than 5 pages", "sections": []})
    assert write.page_budget(ctx).pages == 5


def test_the_outline_counts_pages_at_velocitys_rate(ledger_db: str, tmp_path: Path) -> None:
    model = Model()
    write.outline(_context(tmp_path, model, "outline", EARLIER))
    assert "about 350 words a page" in model.prompt("building outline").user
    assert '"pages"' in write.OUTLINE_SPEC


def test_the_first_draft_and_the_compliance_check_write_to_the_budget(ledger_db: str, tmp_path: Path) -> None:
    model = Model()
    ctx = _context(tmp_path, model, "draft", {**EARLIER, "outline.md": "# Outline"})
    outline_step(ctx.pursuit["id"], OUTLINE)
    write.draft(ctx)
    write.compliance(ctx)
    for label in ("drafting response", "compliance check"):
        user = model.prompt(label).user
        assert "PAGE BUDGET: the call allows 13 pages" in user and "about 4,550 words" in user, label
        assert "- 2. Technical Merit: 3 pages, about 1,050 words" in user, label
    assert "It now runs" in model.prompt("compliance check").user   # the check sees the draft's length too


def test_reviewers_see_the_drafts_length_and_what_earlier_changes_add(ledger_db: str, tmp_path: Path) -> None:
    """In the 1 Nov rerun the reviewers' 56 changes took the draft from 5,067 words to 6,357, and on 2 Nov each
    reviewer saw the same "under" while their 53 changes added 860."""
    model = Model()
    long = "# Draft\n\nClaim 1. Claim 2. Claim 3. " + "word " * 5_000
    ctx = _context(tmp_path, model, "reviews", {**EARLIER, "draft_v2.md": long})
    outline_step(ctx.pursuit["id"], OUTLINE)
    write.reviews(ctx)
    words = len(long.split())   # each stand-in reviewer adds two words: "Claim n." becomes "Claim n, with evidence."
    assert f"It now runs {words:,} words, not counting placeholders, {words - 4_550:,} over: cut before you add" in model.prompt(
        "review 1 of 3: External evaluator").user
    assert (f"It now runs {words:,} words, not counting placeholders, and the changes proposed so far would make it "
            f"{words + 2:,}, {words + 2 - 4_550:,} over: cut before you add") in model.prompt(
        "review 2 of 3: Second independent evaluator").user
    assert f"would make it {words + 4:,}" in model.prompt("review 3 of 3: Velocity leadership").user


LONG = "# Edge AI white paper v3\n\nThe opening.\n\n## 1. Approach\n\n" + "\n\n".join(["The approach is sound. " * 10] * 130)
SHORT = "# Edge AI white paper v3\n\nThe opening.\n\n## 1. Approach\n\n" + "\n\n".join(["The approach is sound. " * 10] * 100)


class Tightening(Model):
    """A Final checks model whose tightening pass gives back what the test sets, and whose formatting pass keeps it."""

    def __init__(self, cut: str) -> None:
        super().__init__()
        self.cut = cut

    def __call__(self, prompt: Prompt, label: str, max_tokens: int) -> str:
        if label == "tightening to the page budget":
            self.asked.append((label, prompt, max_tokens))
            return self.cut
        reply = super().__call__(prompt, label, max_tokens)
        return prompt.user.split("DOCUMENT TO FORMAT:\n", 1)[-1] if label == "formatting document" else reply


def test_final_checks_cut_an_overlong_draft_to_the_budget_before_formatting(ledger_db: str, tmp_path: Path) -> None:
    """The formatting pass may not change wording, so on 2 Nov it left a draft 770 words over; a pass of its own cuts."""
    model = Tightening(SHORT)
    ctx = _context(tmp_path, model, "final", {**EARLIER, "outline.md": "# Outline", "draft_v3.md": LONG})
    outline_step(ctx.pursuit["id"], OUTLINE)
    result = write.final(ctx)
    cut = model.prompt("tightening to the page budget")   # aimed a twentieth under: a pass cuts about half of what it is asked
    assert "Cut, never add" in cut.system and f"Cut it to about {round(4_550 * 0.95):,} words" in cut.user
    assert cut.user.endswith(LONG) and model.labels().count("tightening to the page budget") == 1
    assert "Tighten" not in model.prompt("formatting document").user          # the formatter only formats
    fit = next(c for c in result.content["checks"] if c["check"] == "Page fit")
    assert (fit["ok"], fit["result"]) == (True, "fits")
    assert f"- Tightened from {len(LONG.split()):,} to " in result.summary and "for the 13-page limit" in result.summary


def test_a_second_pass_follows_when_the_first_cut_falls_short(ledger_db: str, tmp_path: Path) -> None:
    """On 2 Nov a pass asked to cut 5,243 words to 4,550 stopped at 4,912."""
    halfway = "# Edge AI white paper v3\n\nThe opening.\n\n## 1. Approach\n\n" + "\n\n".join(["The approach is sound. " * 10] * 122)

    class TwoPasses(Tightening):
        def __call__(self, prompt: Prompt, label: str, max_tokens: int) -> str:
            if label == "tightening to the page budget":
                self.cut = SHORT if self.labels().count(label) else halfway
            return super().__call__(prompt, label, max_tokens)

    model = TwoPasses(halfway)
    ctx = _context(tmp_path, model, "final", {**EARLIER, "outline.md": "# Outline", "draft_v3.md": LONG})
    outline_step(ctx.pursuit["id"], OUTLINE)
    result = write.final(ctx)
    passes = [p for label, p, _ in model.asked if label == "tightening to the page budget"]
    assert len(passes) == 2 and passes[1].user.endswith(halfway.strip())   # the second pass cuts the first one's result
    assert f"- Tightened from {len(LONG.split()):,} to {len(SHORT.split()):,} words in two passes for the 13-page limit" \
        in result.summary


@pytest.mark.parametrize("draft, cut, why", [
    (LONG, SHORT.replace("## 1. Approach\n\n", ""), "it dropped a heading"),
    (LONG + "\n\n[NEEDS INPUT: rates]", SHORT, "it dropped 1 NEEDS INPUT placeholder"),
    (LONG, LONG + " More.", "it cut nothing"),
], ids=["heading", "placeholder", "nothing cut"])
def test_a_cut_that_drops_a_placeholder_or_a_heading_or_cuts_nothing_is_thrown_away(
        ledger_db: str, tmp_path: Path, draft: str, cut: str, why: str) -> None:
    ctx = _context(tmp_path, Tightening(cut), "final", {**EARLIER, "outline.md": "# Outline", "draft_v3.md": draft})
    outline_step(ctx.pursuit["id"], OUTLINE)
    result = write.final(ctx)
    assert f"- Tightening kept Draft v3: {why}" in result.summary
    assert next(c for c in result.content["checks"] if c["check"] == "Page fit")["ok"] is False


def test_every_kind_of_placeholder_is_left_out_of_the_count() -> None:
    assert steps.text_words("Due [NEEDS FACT: the CAGE code] on [CONFIRM the date with the TPOC] by [F-03: CAGE] noon.") == 4


def test_placeholders_do_not_count_against_the_budget(ledger_db: str, tmp_path: Path) -> None:
    """On 2 Nov a final version ran 5,320 words, 1,110 of them inside 92 placeholders: its own text fit 13 pages."""
    gap = " [NEEDS INPUT: the stakeholder unit, its end user and its TPOC, confirmed with the program office]"
    draft = SHORT + gap * 60   # 4,011 words of text and 960 inside placeholders
    assert len(draft.split()) > 4_550 * 1.05 and steps.text_words(draft) == len(SHORT.split())
    model = Tightening(SHORT)
    ctx = _context(tmp_path, model, "final", {**EARLIER, "outline.md": "# Outline", "draft_v3.md": draft})
    outline_step(ctx.pursuit["id"], OUTLINE)
    result = write.final(ctx)
    assert "tightening to the page budget" not in model.labels()
    document = result.content["document"]
    room, open_items = 4_550 - steps.text_words(document), sum(steps.placeholder_counts(document).values())
    fit = next(c for c in result.content["checks"] if c["check"] == "Page fit")
    assert (fit["ok"], fit["result"], open_items >= 60) == (True, "fits", True)
    assert f"with about {room:,} words of room for the {open_items} placeholders still to fill" in fit["detail"]


@pytest.mark.parametrize("final, outline, found", [
    (LONG, OUTLINE, (False, "over", f"cut about {len(LONG.split()) - 4_550:,} words")),
    (SHORT, OUTLINE, (True, "fits", f"with about {4_550 - len(SHORT.split()):,} words of room")),
    (LONG, None, (None, "not run", "the outline found no page limit to check against")),
], ids=["over", "fits", "no limit"])
def test_the_submit_gate_checks_the_filled_final_version_against_the_budget(
        ledger_db: str, tmp_path: Path, final: str, outline: dict[str, Any] | None, found: tuple[bool | None, str, str]) -> None:
    """Filling placeholders adds words: on 2 Nov the final version had about 340 words of room for its 92. The owner
    fills them in the pursuit's folder, so the gate measures the version they left."""
    ctx = _context(tmp_path, Model(), "submit", {**EARLIER, "draft_final.md": final})
    if outline:
        outline_step(ctx.pursuit["id"], outline)
    result = write.submit(ctx)
    checks = result.content["checks"]
    assert [c["check"] for c in checks] == ["Checklist", "Placeholders", "Page fit", "AI slop check", "Dashes",
                                            "Internal submit-by date"]
    ok, word, detail = found
    assert (checks[2]["ok"], checks[2]["result"]) == (ok, word) and checks[2]["detail"].endswith(detail)
    assert ("- Page fit: " in result.summary) is (ok is False)   # the card lists what fails


def test_a_draft_within_the_budget_is_not_cut_and_fits(ledger_db: str, tmp_path: Path) -> None:
    model = Model()
    ctx = _context(tmp_path, model, "final", {**EARLIER, "outline.md": "# Outline", "draft_v3.md": "# Edge AI white paper v3"})
    outline_step(ctx.pursuit["id"], OUTLINE)
    result = write.final(ctx)
    assert "tightening to the page budget" not in model.labels()
    fit = next(c for c in result.content["checks"] if c["check"] == "Page fit")
    assert (fit["ok"], fit["result"]) == (True, "fits") and "for a limit of 13 pages" in fit["detail"]
