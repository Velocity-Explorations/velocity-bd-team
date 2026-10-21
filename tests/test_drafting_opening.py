"""A person writes each draft's opening (PRO-494): finding it, holding it, and the points to land."""
from __future__ import annotations

from drafting import opening

FULL = """# Edge AI Logistics
## Technical Proposal

**Solicitation**: N00024-26-R-0001
**Company**: Velocity Explorations

---

## Volume I: Technical Approach

### 1. Executive Summary

Velocity Explorations proposes Echo C2 for NAVSEA. It fuses sustainment data in the field. The U.S. Navy gains one view. It ships in six months.

- Discriminator one
- Discriminator two

### 2. Understanding of the Requirement

NAVSEA needs one picture of sustainment data across four systems that disagree today.
"""

OTA = """# Agentic C2 White Paper
## White Paper Submission

**Company**: Velocity Explorations

## Part 1: Introduction

Short line.

The Army's brigades need command and control that keeps working when links drop. Velocity builds it.

## Part 2: Military Benefits

Benefits paragraph with enough words in it to count as prose for this test today.
"""

SBIR = """# Edge AI
## Volume II: Technical Volume

## 1. Table of Contents

Sections one through ten are listed here with their page numbers for the reviewers.

## 2. Glossary

C2 means command and control, as used throughout this proposal and its appendices.

## 3. Identification and Significance of the Problem

Navy maintainers lose hours each week reconciling parts data from four systems that disagree.
"""

TWO = """# Proposal

## 1. Introduction

Velocity Explorations is a small defense software company that builds command and control tools.

## 2. Executive Summary

We propose Echo C2. It runs at the edge.

It works without links. The U.S. Army fielded it in 2025. It costs less.
"""

ODD = """# Title

**Company**: Velocity Explorations, with a long label line that has many words in it

- A list item that is long enough to have twelve words in it for sure
| a | table | row | with | many | words | in | it | to | be | sure | ok |

[NEEDS INPUT: tailor this section to the evaluation criteria of the solicitation please]

The real opening paragraph comes here, and it has more than twelve words in it.
"""


SAMPLE_LIKE = """# AI-Enabled Logistics Forecasting (FICTIONAL TEST)

## White Paper | BAA Response

**Solicitation:** N00000-26-S-B999 (FICTIONAL TEST NOTICE, NOT A REAL SOLICITATION) | **Agency:** Naval Expeditionary Logistics Command

*Submitted by Velocity Explorations to the Naval Expeditionary Logistics Command for its review*

[DELETE BEFORE SUBMISSION: Limit is not to exceed 5 pages, Times New Roman 12 pt, single-spaced, 1-inch margins.]

---

## 1. Summary and Understanding

Expeditionary units may have no reach-back for up to 72 hours. They need predictive logistics that keeps working.

Velocity proposes a software-only forecasting capability built around four functions:

- Forecast consumption
"""


def held(draft: str, points: list[list[str]] | None = None) -> tuple[list[opening.Place], str]:
    places = opening.find_places(draft)
    return places, opening.render(draft, places, points or [["point a", "point b"]] * len(places))


def test_an_executive_summary_that_opens_the_draft_is_held_once() -> None:
    places, text = held(FULL)
    assert len(places) == 1
    assert places[0].what == "the opening paragraph and the first three sentences of the executive summary"
    assert places[0].taken.startswith("Velocity Explorations proposes Echo C2") and places[0].taken.endswith("six months.")
    assert "[PERSON WRITES: the opening paragraph and the first three sentences of the executive summary." in text
    assert "> Points to land (not text to use):\n> - point a\n> - point b" in text
    assert "proposes Echo C2" not in text
    start, end = places[0].start, places[0].end
    assert text.startswith(FULL[:start]) and text.endswith(FULL[end:])   # everything else is untouched


def test_a_white_paper_holds_its_introduction_and_skips_short_lines() -> None:
    places, text = held(OTA)
    assert [p.what for p in places] == ["the opening paragraph"]
    assert places[0].taken.startswith("The Army's brigades") and "Short line." in text
    assert "Benefits paragraph" in text


def test_a_table_of_contents_and_a_glossary_are_never_the_opening() -> None:
    places, _ = held(SBIR)
    assert [p.taken for p in places] == ["Navy maintainers lose hours each week reconciling parts data from four systems that disagree."]


def test_a_separate_executive_summary_holds_its_first_three_sentences_across_paragraphs() -> None:
    places, text = held(TWO)
    assert [p.what for p in places] == ["the opening paragraph", "the first three sentences of the executive summary"]
    assert places[1].taken.split() == "We propose Echo C2. It runs at the edge. It works without links.".split()
    assert "We propose Echo C2" not in text and "It works without links" not in text
    assert "The U.S. Army fielded it in 2025. It costs less." in text   # "U.S." does not end a sentence
    assert text.count("[PERSON WRITES:") == 2


def test_labels_lists_tables_and_placeholders_are_never_the_opening() -> None:
    places, _ = held(ODD)
    assert [p.taken for p in places] == ["The real opening paragraph comes here, and it has more than twelve words in it."]


def test_a_title_block_never_holds_the_opening_and_a_first_summary_counts_as_the_abstract() -> None:
    places, text = held(SAMPLE_LIKE)
    assert [p.what for p in places] == ["the opening paragraph and the first three sentences of the summary"]
    assert places[0].taken.split() == ("Expeditionary units may have no reach-back for up to 72 hours. They need predictive "
                                       "logistics that keeps working. Velocity proposes a software-only forecasting "
                                       "capability built around four functions:").split()
    assert "**Solicitation:**" in text and "*Submitted by" in text and "[DELETE BEFORE SUBMISSION:" in text
    assert text.endswith("- Forecast consumption\n")


def test_a_held_draft_is_left_alone_and_a_draft_without_prose_holds_nothing() -> None:
    _, text = held(FULL)
    assert opening.find_places(text) == []
    assert opening.find_places("# Final Draft\n\n[NEEDS INPUT: rates]\n") == []


def test_points_are_read_per_place_with_a_generic_note_when_the_reply_has_none() -> None:
    reply = "PLACE 1:\n- NAVSEA's problem: data in four systems\n- Echo C2 fuses it\nPLACE 2:\n- Proof: the 2025 pilot\n"
    assert opening.parse_points(reply, 2) == [["NAVSEA's problem: data in four systems", "Echo C2 fuses it"],
                                              ["Proof: the 2025 pilot"]]
    assert opening.parse_points("- just bullets\n- two", 1) == [["just bullets", "two"]]
    assert opening.parse_points("no idea", 2) == [opening.GENERIC_POINTS, opening.GENERIC_POINTS]
    many = "PLACE 1:\n" + "\n".join(f"- point {n}" for n in range(9))
    assert len(opening.parse_points(many, 1)[0]) == 5


def test_the_framing_prompt_asks_for_points_from_the_requirements_and_the_draft() -> None:
    places = opening.find_places(TWO)
    prompt = opening.frame_prompt({"company_name": "Velocity Explorations"}, "Edge AI", "NAVSEA",
                                  "# Requirements\nKEYWORDS: edge AI", "# Alignment\nStrong Fit", places)
    assert "Velocity Explorations" in prompt.system and "never write the opening" in prompt.system
    for text in ("Edge AI (NAVSEA)", "KEYWORDS: edge AI", "Strong Fit", "PLACE 2 (the first three sentences of the executive summary)",
                 "We propose Echo C2."):
        assert text in prompt.user, text
