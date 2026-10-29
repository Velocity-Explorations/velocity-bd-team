"""What a model call costs in US dollars, for each pursuit's spending cap (PW19, PRO-577).

    dollars = cost_of(usage)

Prices per million tokens, from https://platform.claude.com/docs/en/about-claude/pricing as of
2026-10-28 and, for Grok, https://docs.x.ai/docs/models as of 2026-10-29. `input_tokens` excludes
the cached part of the prompt, which is priced as cache reads and cache writes (five-minute
writes; the pipeline never asks for longer; xAI charges no writes). Haiku 5.5 costs more for a
prompt over 100,000 tokens, Grok 4.7 for one of 200,000 or more. A model missing here is priced
as the dearest, so the cap errs on the side of stopping. Update the table when prices change.
"""
from __future__ import annotations

from typing import NamedTuple

from drafting.llm import Usage


class Price(NamedTuple):
    input: float
    output: float
    cache_write: float
    cache_read: float


PRICES: dict[str, Price] = {
    "claude-fable-5-1": Price(10.0, 50.0, 12.5, 0.25),
    "claude-opus-5-5": Price(4.0, 20.0, 5.0, 0.20),
    "claude-sonnet-5-5": Price(2.0, 10.0, 2.5, 0.10),
    "claude-haiku-5-5": Price(0.10, 0.50, 0.125, 0.01),
    "grok-4.7": Price(2.0, 6.0, 2.0, 0.50),
}
# The dearer price, from the first prompt size it applies to.
LONG_PRICES: dict[str, tuple[int, Price]] = {
    "claude-haiku-5-5": (100_001, Price(0.50, 2.50, 0.625, 0.05)),
    "grok-4.7": (200_000, Price(4.0, 12.0, 4.0, 1.0)),
}
UNKNOWN = Price(10.0, 50.0, 12.5, 1.0)   # the dearest of each kind, for a model not listed


def cost_of(usage: Usage) -> float:
    """One call's cost in dollars."""
    prompt = usage.input_tokens + usage.cache_read_tokens + usage.cache_write_tokens
    price = PRICES.get(usage.model, UNKNOWN)
    long = LONG_PRICES.get(usage.model)
    if long is not None and prompt >= long[0]:
        price = long[1]
    return (usage.input_tokens * price.input + usage.output_tokens * price.output
            + usage.cache_write_tokens * price.cache_write + usage.cache_read_tokens * price.cache_read) / 1_000_000
