"""LLM review of filtered calls: one verdict with a one-sentence reason per call.

    passed, dropped = review_calls(rows, AnthropicModel())

The fail-safe is always "maybe", never "no": a model outage must not discard leads.
Each call gets one retry after a second; both failing yields verdict "maybe" with a
"Review error" reason. Two prompt slots stay empty for now: past_experience_block (the
library component, later) and feedback_examples_block (Phase 8). A third, extra_context,
carries the team's note when a person approves a re-review (docs/ASSISTANT.md).

The answer also carries a TAGS line: each judge tags the call from review/tags.yaml in the same
call (PRO-556). Tagging is best-effort and never changes a verdict.
"""
from __future__ import annotations

import json
import logging
import re
import time
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from ledger.queries import add_judgment, set_review, set_summary, set_tags
from review.tags import parse_tags, prompt_block, tag_list

log = logging.getLogger("review")

MODEL_ID = "claude-haiku-5-5"
CALL_TIMEOUT_S = 35.0
RETRY_DELAY_S = 1.0
BETWEEN_CALLS_S = 0.5
VERDICTS = ("yes", "no", "maybe")
UNPARSEABLE_REASON = "Could not parse LLM response"
GROK_MODEL_ID = "grok-4.7"   # the second judge; its key is limited to this model
GROK_URL = "https://api.x.ai/v1/responses"
GROK_TIMEOUT_S = 120.0       # Grok reasons before it answers; the 20 Oct trial averaged about 20 s a call
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

# Listing types that are events, not contracts (SSC Front Door writes these). The company context
# says Velocity does not do event participation; for an event the question is whether its topic is
# worth attending, so these listings get one more instruction.
EVENT_TYPES = ("Industry day", "Webinar", "Conference", "Event")
EVENT_GUIDANCE = (
    "This listing is an event (an industry day, webinar or conference), not a contract to bid on. "
    "Rate it on its topic: yes if the topic is close to Velocity's core work, so attending would help "
    "find or win related work; maybe if it is partly related; no if it is unrelated. Do not rate it no "
    "only because it is an event."
)

PROMPT_TEMPLATE = """{company_context}{past_experience_block}{feedback_examples_block}

Evaluate this government opportunity for Velocity Explorations:

Title: {title}
Portal: {portal}
Type: {type}
NAICS: {naics_code}
Agency: {department}
Description: {description}
{extra_context_block}
Respond with exactly this format (no other text):
VERDICT: yes|no|maybe
REASON: [one sentence explaining why]
TAGS: [tags from the list below, separated by commas]
SUMMARY: [{summary_ask}]

Use "yes" if clearly relevant, "no" if clearly not, "maybe" if uncertain.
If past experience shows similar work has been pursued or won, weight that positively.

{tags_block}"""

# The summary alone, for calls reviewed before summaries began (run.py --backfill-summaries, phase 9c).
SUMMARY_PROMPT_TEMPLATE = """Summarize this government opportunity for an executive who has a minute to decide whether to read it.

Title: {title}
Portal: {portal}
Type: {type}
Agency: {department}
Due: {due_date}
Description: {description}

Respond with exactly one line (no other text):
SUMMARY: [{summary_ask}]"""

# Tags alone, for calls reviewed before tagging began (run.py --backfill-tags).
TAG_PROMPT_TEMPLATE = """Tag this government opportunity.

Title: {title}
Portal: {portal}
Type: {type}
NAICS: {naics_code}
Agency: {department}
Description: {description}

{tags_block}

Respond with exactly one line (no other text):
TAGS: [tags from the list, separated by commas]"""


SUMMARY_ASK = ("two short, plain sentences for an executive, 45 words at most in all: what the agency wants, then the kind "
               "of award, its size if the call gives it, and the date that matters. No em dashes or en dashes")
SUMMARY_CHARS = 600


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


class GrokModel:
    """Grok through xAI's Responses API, the second judge. Raises on any failure; the caller retries.

    Uses BD_XAI_API_KEY, never XAI_API_KEY: on David's PC that name holds another project's key
    and the process environment overrides .env.
    """

    def __init__(self, model: str = GROK_MODEL_ID, api_key: str | None = None) -> None:
        from config import require

        self.model = model
        self._key = api_key or require("BD_XAI_API_KEY")

    def complete(self, prompt: str, timeout: float) -> str:
        body = json.dumps({"model": self.model, "input": prompt}).encode("utf-8")
        request = urllib.request.Request(GROK_URL, data=body, method="POST", headers={
            "Authorization": f"Bearer {self._key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=max(timeout, GROK_TIMEOUT_S)) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if isinstance(payload.get("output_text"), str):
            return payload["output_text"]
        return "\n".join(part["text"] for item in payload.get("output") or [] for part in item.get("content") or []
                         if part.get("type") in ("output_text", "text") and part.get("text"))


@dataclass
class Reviewed:
    id: str
    title: str
    verdict: str
    reason: str
    match_tier: str | None = None


def build_prompt(
    row: Mapping[str, Any],
    past_experience_block: str = "",
    feedback_examples_block: str = "",
    extra_context: str = "",
) -> str:
    context = " ".join((extra_context or "").split())
    blocks = [f"{EVENT_GUIDANCE}\n"] if (row.get("type") or "") in EVENT_TYPES else []
    if context:
        blocks.append(f"Context from the team: {context}\n")
    return PROMPT_TEMPLATE.format(
        company_context=COMPANY_CONTEXT,
        past_experience_block=past_experience_block or "",
        feedback_examples_block=feedback_examples_block or "",
        extra_context_block="".join(blocks),
        title=row.get("title") or "",
        portal=row.get("portal") or "",
        type=row.get("type") or "",
        naics_code=row.get("naics_code") or "",
        department=row.get("department") or "",
        description=(row.get("description") or "")[:DESCRIPTION_CHARS],
        tags_block=prompt_block(tag_list()),
        summary_ask=SUMMARY_ASK,
    )


def build_tag_prompt(row: Mapping[str, Any]) -> str:
    return TAG_PROMPT_TEMPLATE.format(
        title=row.get("title") or "",
        portal=row.get("portal") or "",
        type=row.get("type") or "",
        naics_code=row.get("naics_code") or "",
        department=row.get("department") or "",
        description=(row.get("description") or "")[:DESCRIPTION_CHARS],
        tags_block=prompt_block(tag_list()),
    )


def build_summary_prompt(row: Mapping[str, Any]) -> str:
    """The prompt that asks only for a call's summary (phase 9c)."""
    return SUMMARY_PROMPT_TEMPLATE.format(
        title=row.get("title") or "",
        portal=row.get("portal") or "",
        type=row.get("type") or "",
        department=row.get("department") or "",
        due_date=row.get("due_date") or "not given",
        description=(row.get("description") or "")[:DESCRIPTION_CHARS],
        summary_ask=SUMMARY_ASK,
    )


def parse_summary(text: str) -> str | None:
    """The answer's SUMMARY line in plain words, dashes replaced, or None when there is none."""
    for raw in (text or "").splitlines():
        line = raw.strip()
        if line.upper().startswith("SUMMARY:"):
            summary = line.split(":", 1)[1].strip()
            summary = re.sub(r"(\d)\s*[\u2013\u2014]\s*(\d)", r"\1 to \2", summary)
            summary = re.sub(r"\s*[\u2013\u2014]\s*", ", ", summary)
            if len(summary) > SUMMARY_CHARS:
                summary = summary[:SUMMARY_CHARS].rsplit(" ", 1)[0].rstrip(",;:") + "."
            return summary or None
    return None


def store_summary(call_id: str, text: str) -> bool:
    """Keep an answer's summary. An answer without one changes nothing, and a failure to store it only logs."""
    summary = parse_summary(text)
    if not summary:
        return False
    try:
        set_summary(call_id, summary)
    except Exception as exc:
        log.warning("Could not store the summary of %s: %s", call_id, type(exc).__name__)
        return False
    return True


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


def is_judgment(reason: str) -> bool:
    """False for the fail-safe answers ask_model gives when the model failed or could not be read."""
    return not (reason.startswith("Review error") or reason == UNPARSEABLE_REASON)


def complete_text(prompt: str, model: ModelClient, sleep: Callable[[float], None] = time.sleep) -> tuple[str, str]:
    """(text, error): the model's answer after at most one retry, or "" and the first error."""
    first_error = ""
    for attempt in (1, 2):
        try:
            text = model.complete(prompt, timeout=CALL_TIMEOUT_S)
            if text and text.strip():
                return text, ""
            raise RuntimeError("empty response")
        except Exception as exc:
            message = f"{type(exc).__name__}: {str(exc)[:200]}"
            first_error = first_error or message
            log.warning("Model call attempt %d failed: %s", attempt, message[:160])
            if attempt == 1:
                sleep(RETRY_DELAY_S)
    return "", first_error


def ask(prompt: str, model: ModelClient, sleep: Callable[[float], None] = time.sleep) -> tuple[str, str, str]:
    """ask_model, plus the answer's text for its TAGS line ("" after a failure)."""
    text, error = complete_text(prompt, model, sleep)
    if not text:
        return "maybe", f"Review error: {error[:80]}", ""
    verdict, reason = parse_response(text)
    return verdict, reason, text


def ask_model(prompt: str, model: ModelClient, sleep: Callable[[float], None] = time.sleep) -> tuple[str, str]:
    """One call plus one retry. Any failure on both -> ("maybe", "Review error: ...")."""
    verdict, reason, _ = ask(prompt, model, sleep)
    return verdict, reason


def store_tags(call_id: str, source: str, text: str) -> list[str]:
    """Keep the tags an answer picked. An answer without them changes nothing, and a failure to
    store them only logs: tagging never stops a review."""
    picked = parse_tags(text, tag_list())
    if picked:
        try:
            set_tags(call_id, source, picked)
        except Exception as exc:
            log.warning("Could not store %s's tags on %s: %s", source, call_id, type(exc).__name__)
            return []
    return picked


def review_calls(
    rows: list[Mapping[str, Any]],
    model_client: ModelClient,
    past_experience_fn: Callable[[Mapping[str, Any]], str] | None = None,
    feedback_examples_block: str = "",
    sleep: Callable[[float], None] = time.sleep,
    extra_context: str = "",
) -> tuple[list[Reviewed], list[Reviewed]]:
    """Review every row, write verdicts to the ledger, return (passed, dropped)."""
    passed: list[Reviewed] = []
    dropped: list[Reviewed] = []
    for n, row in enumerate(rows):
        past = past_experience_fn(row) if past_experience_fn else ""
        prompt = build_prompt(row, past, feedback_examples_block, extra_context)
        if n == 0:
            log.debug("Rendered prompt for first row:\n%s", prompt)
        verdict, reason, text = ask(prompt, model_client, sleep)
        set_review(row["id"], verdict, reason)
        if is_judgment(reason):
            add_judgment(row["id"], "claude", getattr(model_client, "model", MODEL_ID), verdict, reason)
            store_tags(row["id"], "claude", text)
            store_summary(row["id"], text)
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


def judge_calls(
    rows: list[Mapping[str, Any]],
    model_client: ModelClient,
    judge: str,
    feedback_examples_block: str = "",
    sleep: Callable[[float], None] = time.sleep,
    extra_context: str = "",
) -> list[Reviewed]:
    """A second judge: rate each row with the review's own prompt and record only its judgment.

    calls.ai_verdict, which decides what is posted, stays the Claude review's. A call the judge
    could not rate (a model error, an unreadable answer) gets no judgment.
    """
    judged: list[Reviewed] = []
    name = getattr(model_client, "model", judge)
    for n, row in enumerate(rows):
        prompt = build_prompt(row, "", feedback_examples_block, extra_context)
        verdict, reason, text = ask(prompt, model_client, sleep)
        title = str(row.get("title") or "")
        if is_judgment(reason):
            add_judgment(row["id"], judge, name, verdict, reason)
            store_tags(row["id"], judge, text)
            judged.append(Reviewed(row["id"], title, verdict, reason, row.get("match_tier")))
            log.info("%s judged [%s]: %s", judge, verdict, title[:80])
        else:
            log.warning("%s could not judge %s: %s", judge, row["id"], reason[:120])
        if n < len(rows) - 1:
            sleep(BETWEEN_CALLS_S)
    return judged


def summarize_calls(rows: list[Mapping[str, Any]], model_client: ModelClient, sleep: Callable[[float], None] = time.sleep) -> int:
    """Have Claude summarize calls reviewed before summaries began, asking for the summary alone (phase 9c). Returns
    how many it summarized; a call it could not summarize is asked again on the next pass."""
    done = 0
    for n, row in enumerate(rows):
        text, error = complete_text(build_summary_prompt(row), model_client, sleep)
        if store_summary(row["id"], text):
            done += 1
        elif error:
            log.warning("Could not summarize %s: %s", row["id"], error[:120])
        if n < len(rows) - 1:
            sleep(BETWEEN_CALLS_S)
    return done


def tag_calls(
    rows: list[Mapping[str, Any]],
    model_client: ModelClient,
    source: str,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Have one judge tag calls reviewed before tagging began, asking for tags alone. Returns how many
    it tagged; a call it could not tag gets none and is asked again on the next pass."""
    tagged = 0
    for n, row in enumerate(rows):
        text, error = complete_text(build_tag_prompt(row), model_client, sleep)
        if store_tags(row["id"], source, text):
            tagged += 1
        elif error:
            log.warning("%s could not tag %s: %s", source, row["id"], error[:120])
        if n < len(rows) - 1:
            sleep(BETWEEN_CALLS_S)
    return tagged
