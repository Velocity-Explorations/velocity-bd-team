"""Response templates and the company profile they are filled from (Writer Plan W0)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from drafting import company, templates
from tests.drafting_reference import DASHES, TEMPLATES, reference_constants, undash


def test_template_map_matches_the_reference() -> None:
    assert templates.TEMPLATE_MAP == reference_constants()["TEMPLATE_MAP"]


@pytest.mark.parametrize("opp_type", sorted(reference_constants()["TEMPLATE_MAP"]))
def test_every_mapped_type_selects_its_template(opp_type: str) -> None:
    name, text, is_fallback = templates.select_template(opp_type)
    assert name == templates.TEMPLATE_MAP[opp_type] and not is_fallback
    assert text.strip() and not re.search(r"\{[a-z_]+\}", text)
    assert company.profile()["legal_name"] in text and company.profile()["cage"] == "[F-03: CAGE]" in text   # filled from Drive


def test_an_unknown_type_falls_back_to_the_full_proposal() -> None:
    name, text, is_fallback = templates.select_template("Something New")
    assert (name, is_fallback) == ("full_proposal", True) and text.strip()
    assert templates.select_template("")[0] == "full_proposal"


def test_templates_keep_the_reference_wording_without_dashes() -> None:
    for ref in sorted(TEMPLATES.glob("*.md")):
        ours = Path(templates.__file__).parent / ref.name
        text = ours.read_text(encoding="utf-8")
        assert text == undash(ref.read_text(encoding="utf-8")), ref.name
        assert not any(d in text for d in DASHES), ref.name


def test_unknown_placeholders_are_left_empty_not_fatal() -> None:
    assert templates.fill("Hi {company_name}, {not_a_field}!", {"company_name": "Acme"}) == "Hi Acme, !"
    assert templates.fill("broken {", {"company_name": "Acme"}) == "broken {"


def test_the_company_profile_has_every_field_the_prompts_use() -> None:
    p = company.profile()
    for key in ("company_name", "legal_name", "short_name", "cage", "uei", "duns", "business_size", "poc_name",
                "poc_title", "poc_email", "poc_phone", "naics_display", "company_description"):
        assert isinstance(p.get(key), str) and p[key], key
