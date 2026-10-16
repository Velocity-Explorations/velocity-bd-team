"""LLM review of filtered calls: one verdict with a one-sentence reason per call.

    passed, dropped = review_calls(rows, AnthropicModel())

The fail-safe is always "maybe", never "no": a model outage must not discard leads.
Each call gets one retry after a second; both failing yields verdict "maybe" with a
"Review error" reason. Two prompt slots stay empty for now: past_experience_block (the
corpus component, later) and feedback_examples_block (Phase 8).
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from ledger.queries import set_review

log = logging.getLogger("review")

MODEL_ID = "claude-haiku-5-5"
CALL_TIMEOUT_S = 35.0
RETRY_DELAY_S = 1.0
BETWEEN_CALLS_S = 0.5
VERDICTS = ("yes", "no", "maybe")
UNPARSEABLE_REASON = "Could not parse LLM response"
DESCRIPTION_CHARS = 1500   # the spec said 500; the ledger now stores 1,500 and the model asked for more

# Company profile, used verbatim in every review prompt.
COMPANY_CONTEXT = """Velocity Explorations is a small defense technology company focused on:
- Software development and AI/ML development for DoD and government
- Legacy system modernization (COBOL, AS/400, mainframe -> modern web/cloud)
- Command and control (C2) systems, Echo C2 AI is their flagship product
- Natural language processing, transcription, translation for operational environments
- Computer vision, autonomous systems software
- DevSecOps, cloud migration, data analytics platforms
- SBIR/STTR contracts and OTA agreements

Velocity IS a registered member of the S2MARTS and SpEC OTA consortia (managed by NSTXL) and can submit to their opportunities.

Velocity does NOT do: hardware development or manufacturing; physical construction or facilities work; IT management or administrative support services; medical devices or healthcare equipment; training/education services; events or conference participation; logistics, supply chain, or parts procurement; financial software unrelated to defense.

A good opportunity for Velocity involves: building software, developing AI/ML models, modernizing legacy systems, creating C2 tools, or conducting R&D in AI/autonomy/NLP.
"""

PROMPT_TEMPLATE = """{company_context}{past_experience_block}{feedback_examples_block}

Evaluate this government opportunity for Velocity Explorations:

Title: {title}
Portal: {portal}
Type: {type}
NAICS: {naics_code}
Agency: {department}
Description: {description}

Respond with exactly this format (no other text):
VERDICT: yes|no|maybe
REASON: [one sentence explaining why]

Use "yes" if clearly relevant, "no" if clearly not, "maybe" if uncertain.
If past experience shows similar work has been pursued or won, weight that positively."""


class ModelClient(Protocol):
    def complete(self, prompt: str, timeout: float) -> str: ...


class AnthropicModel:
    """Thin wrapper over the Anthropic SDK. Raises on any failure; the caller retries."""

    def __init__(self, model: str = MODEL_ID, api_key: str | None = None) -> None:
        import anthropic

        from config import require

        self._anthropic = anthropic
        self.model = model
        self._client = anthropic.Anthropic(api_key=api_key or require("ANTHROPIC_API_KEY"), max_retries=0)

    def complete(self, prompt: str, timeout: float) -> str:
        response = self._client.with_options(timeout=timeout).messages.create(
            model=self.model,
            max_tokens=1024,   # adaptive thinking shares this budget; 256 truncated reasons
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": prompt}],
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("model refused the request")
        return "".join(block.text for block in response.content if block.type == "text")


@dataclass
class Reviewed:
    id: str
    title: str
    verdict: str
    reason: str
    match_tier: str | None = None


def build_prompt(row: Mapping[str, Any], past_experience_block: str = "", feedback_examples_block: str = "") -> str:
    return PROMPT_TEMPLATE.format(
        company_context=COMPANY_CONTEXT,
        past_experience_block=past_experience_block or "",
        feedback_examples_block=feedback_examples_block or "",
        title=row.get("title") or "",
        portal=row.get("portal") or "",
        type=row.get("type") or "",
        naics_code=row.get("naics_code") or "",
        department=row.get("department") or "",
        description=(row.get("description") or "")[:DESCRIPTION_CHARS],
    )


def parse_response(text: str) -> tuple[str, str]:
    """(verdict, reason). Unparseable verdict -> ("maybe", UNPARSEABLE_REASON)."""
    verdict: str | None = None
    reason: str | None = None
    for raw in (text or "").splitlines():
        line = raw.strip()
        upper = line.upper()
        if upper.startswith("VERDICT:"):
            candidate = line.split(":", 1)[1].strip().lower().strip(".")
            if candidate in VERDICTS:
                verdict = candidate
        elif upper.startswith("REASON:"):
            reason = line.split(":", 1)[1].strip()
    if verdict is None:
        return "maybe", UNPARSEABLE_REASON
    return verdict, reason or ""


def ask_model(prompt: str, model: ModelClient, sleep: Callable[[float], None] = time.sleep) -> tuple[str, str]:
    """One call plus one retry. Any failure on both -> ("maybe", "Review error: ...")."""
    first_error = ""
    for attempt in (1, 2):
        try:
            text = model.complete(prompt, timeout=CALL_TIMEOUT_S)
            if text and text.strip():
                return parse_response(text)
            raise RuntimeError("empty response")
        except Exception as exc:
            message = f"{type(exc).__name__}: {str(exc)[:200]}"
            first_error = first_error or message
            log.warning("Model call attempt %d failed: %s", attempt, message[:160])
            if attempt == 1:
                sleep(RETRY_DELAY_S)
    return "maybe", f"Review error: {first_error[:80]}"


def review_calls(
    rows: list[Mapping[str, Any]],
    model_client: ModelClient,
    past_experience_fn: Callable[[Mapping[str, Any]], str] | None = None,
    feedback_examples_block: str = "",
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[list[Reviewed], list[Reviewed]]:
    """Review every row, write verdicts to the ledger, return (passed, dropped)."""
    passed: list[Reviewed] = []
    dropped: list[Reviewed] = []
    for n, row in enumerate(rows):
        past = past_experience_fn(row) if past_experience_fn else ""
        prompt = build_prompt(row, past, feedback_examples_block)
        if n == 0:
            log.debug("Rendered prompt for first row:\n%s", prompt)
        verdict, reason = ask_model(prompt, model_client, sleep)
        set_review(row["id"], verdict, reason)
        reviewed = Reviewed(row["id"], str(row.get("title") or ""), verdict, reason, row.get("match_tier"))
        log.info("AI review [%s]: %s", verdict, reviewed.title[:80])
        if verdict == "no":
            log.info("-> Dropped: %s", reason)
            dropped.append(reviewed)
        else:
            passed.append(reviewed)
        if n < len(rows) - 1:
            sleep(BETWEEN_CALLS_S)
    return passed, dropped
