"""Drafts held to the call's page limit (PRO-565): the outline's page counts become a word budget at Velocity's own rate,
the First draft, the Compliance check and the reviewers write to it, and Final checks reports the fit and has the
formatting pass tighten a draft that runs over."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from drafting import write
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


def test_reviewers_see_the_drafts_length_against_the_budget(ledger_db: str, tmp_path: Path) -> None:
    """In the 1 Nov rerun the reviewers' 56 changes took the draft from 5,067 words to 6,357."""
    model = Model()
    long = "# Draft\n\nClaim 1. Claim 2. Claim 3. " + "word " * 5_000
    ctx = _context(tmp_path, model, "reviews", {**EARLIER, "draft_v2.md": long})
    outline_step(ctx.pursuit["id"], OUTLINE)
    write.reviews(ctx)
    words = len(long.split())
    for n, name in enumerate(("External evaluator", "Second independent evaluator", "Velocity leadership"), start=1):
        user = model.prompt(f"review {n} of 3: {name}").user
        assert f"It now runs {words:,} words, {words - 4_550:,} over: cut before you add" in user, name


def test_final_checks_tighten_an_overlong_draft_and_report_the_page_fit(ledger_db: str, tmp_path: Path) -> None:
    # about 5,200 words for 4,550, in paragraphs: Final checks holds the opening paragraph for a person to write
    long = "# Edge AI white paper v3\n\nThe opening.\n\n" + "\n\n".join(["The approach is sound. " * 10] * 130)

    class Overlong(Model):   # the formatting pass gives the draft back as long as it came
        def __call__(self, prompt: Prompt, label: str, max_tokens: int) -> str:
            reply = super().__call__(prompt, label, max_tokens)
            return long if label == "formatting document" else reply

    model = Overlong()
    ctx = _context(tmp_path, model, "final", {**EARLIER, "outline.md": "# Outline", "draft_v3.md": long})
    outline_step(ctx.pursuit["id"], OUTLINE)
    result = write.final(ctx)
    assert "Tighten it to the budget of about 4,550 words" in model.prompt("formatting document").user
    fit = next(c for c in result.content["checks"] if c["check"] == "Page fit")
    assert (fit["ok"], fit["result"]) == (False, "over") and "cut about" in fit["detail"]


def test_a_draft_within_the_budget_is_formatted_as_it_is_and_fits(ledger_db: str, tmp_path: Path) -> None:
    model = Model()
    ctx = _context(tmp_path, model, "final", {**EARLIER, "outline.md": "# Outline", "draft_v3.md": "# Edge AI white paper v3"})
    outline_step(ctx.pursuit["id"], OUTLINE)
    result = write.final(ctx)
    assert "Tighten it" not in model.prompt("formatting document").user
    fit = next(c for c in result.content["checks"] if c["check"] == "Page fit")
    assert (fit["ok"], fit["result"]) == (True, "fits") and "for a limit of 13 pages" in fit["detail"]
