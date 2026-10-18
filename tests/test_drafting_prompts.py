"""The ported prompts keep every word of the reference pipeline's prompts (Writer Plan W0)."""
from __future__ import annotations

from pathlib import Path

import pytest

from drafting import prompts
from tests.drafting_reference import DASHES, reference_constants, reference_source, undash

COMPANY = {
    "company_name": "Acme Defense", "legal_name": "Acme Defense, Inc.", "short_name": "Acme", "cage": "1ABC2",
    "uei": "UEI123", "duns": "00-000-0000", "business_size": "Small Business", "poc_name": "Pat Lee",
    "poc_title": "CEO", "poc_email": "pat@acme.example", "poc_phone": "(555) 010-0000",
    "naics_display": "541511", "company_description": "a small software company",
}

CONSTANTS = ["REQUIREMENTS_SYSTEM_PROMPT", "REQUIREMENTS_USER_PROMPT", "ALIGNMENT_SYSTEM_PROMPT",
             "ALIGNMENT_USER_PROMPT", "OUTLINE_SYSTEM_PROMPT", "OUTLINE_USER_PROMPT", "DRAFT_SYSTEM_PROMPT",
             "DRAFT_USER_PROMPT", "REVIEW_USER_PROMPT", "COMPLIANCE_SYSTEM_PROMPT", "COMPLIANCE_USER_PROMPT",
             "CHECKLIST_SYSTEM_PROMPT", "CHECKLIST_USER_PROMPT", "FORMAT_SYSTEM_PROMPT", "FORMAT_USER_PROMPT"]


@pytest.mark.parametrize("name", CONSTANTS)
def test_each_prompt_keeps_the_reference_wording(name: str) -> None:
    assert getattr(prompts, name) == undash(reference_constants()[name])


def test_the_review_passes_keep_the_reference_wording() -> None:
    reference = reference_constants()["REVIEW_PASSES"]
    assert len(prompts.REVIEW_PASSES) == len(reference) == 4
    for ours, theirs in zip(prompts.REVIEW_PASSES, reference):
        assert ours == {"label": undash(theirs["label"]), "system": undash(theirs["system"])}


def test_the_inline_prompt_text_matches_the_reference() -> None:
    source = reference_source()
    for text in (prompts.OUTLINE_ALIGNMENT_HEADER, prompts.DRAFT_ALIGNMENT_HEADER, prompts.DEFAULT_SECTIONS):
        assert text.encode("unicode_escape").decode() in source or text in source.replace("\\n", "\n")


def test_the_prompts_module_has_no_dashes() -> None:
    text = Path(prompts.__file__).read_text(encoding="utf-8")
    assert not any(d in text for d in DASHES)


def test_requirements_prompt_fills_every_field() -> None:
    p = prompts.p4_requirements(company=COMPANY, knowledge_base="KB TEXT", rag_context="RAG TEXT", title="Edge AI",
                                agency="NAVY", portal="SAM.gov", opp_type="BAA", due_date="2026-12-01",
                                listing_text="LISTING", attachment_text="ATTACH")
    assert p.system.startswith("You are a senior BD analyst at Acme Defense.")
    assert "ABOUT ACME DEFENSE:\nKB TEXT" in p.system and "RAG TEXT" in p.system
    assert "- Title: Edge AI" in p.user and "LISTING PAGE TEXT:\nLISTING" in p.user and p.user.endswith("ATTACH")
    assert "SOLICITATION TERMINOLOGY & KEYWORDS: SOURCE OF TRUTH" in p.user


def test_outline_and_draft_add_the_alignment_only_when_given() -> None:
    common = dict(company=COMPANY, knowledge_base="KB", rag_context="RAG", title="T", agency="A", portal="P",
                  opp_type="BAA", due_date="D", requirements="REQ")
    bare = prompts.p5_outline(**common, template="TEMPLATE", alignment="")
    assert "ALIGNMENT ASSESSMENT" not in bare.user and "TEMPLATE" in bare.user
    with_alignment = prompts.p5_outline(**common, template="TEMPLATE", alignment="ALIGN")
    assert with_alignment.user.endswith(prompts.OUTLINE_ALIGNMENT_HEADER + "ALIGN")
    draft = prompts.p6_draft(**common, outline="OUTLINE", alignment="ALIGN")
    assert "- POC: Pat Lee, CEO | pat@acme.example | (555) 010-0000" in draft.user
    assert draft.user.endswith(prompts.DRAFT_ALIGNMENT_HEADER + "ALIGN")
    assert draft.system.startswith("You are a proposal writer at Acme Defense, a small software company.")


def test_review_passes_render_their_labels_and_context() -> None:
    labels = [prompts.review_pass_label(n, COMPANY) for n in range(1, 5)]
    assert labels == ["External evaluator", "Second independent evaluator", "Acme Defense leadership review",
                      "Critical capability verification"]
    p = prompts.p65_review_pass(4, company=COMPANY, knowledge_base="KB", rag_context="RAG", title="T", agency="A",
                                opp_type="BAA", due_date="D", requirements="REQ", alignment_block="ALIGN",
                                draft="DRAFT")
    assert "RELEVANT PAST SUBMISSIONS:\nRAG" in p.system and p.user.endswith("DRAFT TO REVISE:\nDRAFT")
    with pytest.raises(ValueError):
        prompts.p65_review_pass(5, company=COMPANY, knowledge_base="", rag_context="", title="", agency="",
                                opp_type="", due_date="", requirements="", alignment_block="", draft="")


def test_compliance_checklist_and_polish_prompts() -> None:
    c = prompts.p675_compliance(company=COMPANY, knowledge_base="KB", alignment_context="", title="T", agency="A",
                                opp_type="BAA", due_date="D", requirements="REQ", draft="DRAFT")
    assert prompts.CORRECTED_DRAFT_SEPARATOR in c.system and c.user.endswith("DRAFT TO CHECK:\nDRAFT")
    k = prompts.p7_checklist(company=COMPANY, title="T", agency="A", due_date="D", requirements="REQ",
                             outline="OUT", draft="DRAFT")
    assert k.system.startswith("You are a proposal compliance reviewer at Acme Defense.")
    assert "PROPOSAL OUTLINE:\nOUT" in k.user
    f = prompts.p75_polish(draft="DRAFT")
    assert f.system == prompts.FORMAT_SYSTEM_PROMPT and f.user.endswith("DOCUMENT TO FORMAT:\nDRAFT")
