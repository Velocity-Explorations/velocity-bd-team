"""What a model call costs, for the pursuit's $200 cap (PW19, PRO-577)."""
from __future__ import annotations

import pytest

from drafting import costs, llm


def usage(model: str, i: int = 0, o: int = 0, cache_read: int = 0, cache_write: int = 0) -> llm.Usage:
    return llm.Usage(phase_label="x", model=model, input_tokens=i, output_tokens=o, cache_read_tokens=cache_read,
                     cache_write_tokens=cache_write, seconds=1.0, truncated=False, request_id="")


def test_sonnet_5_5_costs_two_dollars_in_and_ten_out_per_million_tokens() -> None:
    assert costs.cost_of(usage("claude-sonnet-5-5", i=1_000_000)) == pytest.approx(2.0)
    assert costs.cost_of(usage("claude-sonnet-5-5", o=1_000_000)) == pytest.approx(10.0)
    assert costs.cost_of(usage("claude-sonnet-5-5", cache_read=1_000_000, cache_write=1_000_000)) == pytest.approx(0.10 + 2.50)


def test_the_drafting_models_are_priced() -> None:
    assert llm.DEFAULT_MODEL in costs.PRICES and "grok-4.7" in costs.PRICES


def test_grok_4_7_costs_two_dollars_in_and_six_out_per_million_tokens() -> None:
    assert costs.cost_of(usage("grok-4.7", i=100_000)) == pytest.approx(0.20)
    assert costs.cost_of(usage("grok-4.7", o=1_000_000)) == pytest.approx(6.0)
    assert costs.cost_of(usage("grok-4.7", cache_read=100_000)) == pytest.approx(0.05)


def test_grok_4_7_prompts_from_200k_tokens_cost_double() -> None:
    assert costs.cost_of(usage("grok-4.7", i=199_999, o=1_000)) == pytest.approx(199_999 * 2.0 / 1e6 + 1_000 * 6.0 / 1e6)
    assert costs.cost_of(usage("grok-4.7", i=150_000, cache_read=50_000, o=1_000)) == pytest.approx(
        150_000 * 4.0 / 1e6 + 50_000 * 1.0 / 1e6 + 1_000 * 12.0 / 1e6)


def test_haiku_5_5_prompts_over_100k_tokens_cost_more() -> None:
    assert costs.cost_of(usage("claude-haiku-5-5", i=100_000, o=1_000)) == pytest.approx(100_000 * 0.10 / 1e6 + 1_000 * 0.50 / 1e6)
    assert costs.cost_of(usage("claude-haiku-5-5", i=90_000, cache_read=20_000, o=1_000)) == pytest.approx(
        90_000 * 0.50 / 1e6 + 20_000 * 0.05 / 1e6 + 1_000 * 2.50 / 1e6)


def test_a_model_without_a_price_counts_as_the_dearest() -> None:
    assert costs.cost_of(usage("claude-unknown-9", i=1_000_000, o=1_000_000)) == pytest.approx(10.0 + 50.0)
