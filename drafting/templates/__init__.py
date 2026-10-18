"""Response templates per opportunity type, ported from the retired Yukon pipeline.

The .md files beside this module are the reference templates with every word unchanged
(only the em dashes are swapped, under David's no-dash rule). TEMPLATE_MAP is the
reference's map from opportunity type to template; anything unmapped falls back to
full_proposal, and the caller records that in the draft's phase log.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path

from drafting.company import profile

TEMPLATES_DIR = Path(__file__).resolve().parent
FALLBACK = "full_proposal"

TEMPLATE_MAP = {
    "SBIR/STTR": "sbir_phase1",
    "SBIR": "sbir_phase1",
    "BAA": "baa_response",
    "Solicitation": "full_proposal",
    "Combined Synopsis": "full_proposal",
    "Pre-solicitation": "full_proposal",
    "OTA": "ota_white_paper",
    "S2MARTS OTA": "ota_white_paper",
    "SpEC OTA": "ota_white_paper",
    "Commercial Solutions Opening": "cso_response",
    "Sources Sought": "capability_statement",
    "RFI": "capability_statement",
}


def fill(text: str, values: Mapping[str, str]) -> str:
    """Fill {placeholders} from values; unknown ones become empty, and malformed text is left as it is."""
    try:
        return text.format_map(defaultdict(str, values))
    except (KeyError, ValueError, IndexError):
        return text


def select_template(opp_type: str, company: Mapping[str, str] | None = None) -> tuple[str, str, bool]:
    """(template name, filled text, is_fallback) for an opportunity type."""
    values = company if company is not None else profile()
    name = TEMPLATE_MAP.get(opp_type)
    if name:
        path = TEMPLATES_DIR / f"{name}.md"
        if path.exists():
            return name, fill(path.read_text(encoding="utf-8"), values), False
    path = TEMPLATES_DIR / f"{FALLBACK}.md"
    text = fill(path.read_text(encoding="utf-8"), values) if path.exists() else ""
    return FALLBACK, text, True
