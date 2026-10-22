"""
Yukon — Opportunity Scorer
Scores and ranks opportunities by relevance to Velocity Explorations.
Used to select the Top 5 daily picks for Discord highlight.

Scoring factors:
  - NAICS match (exact) → high signal
  - High-value keywords in title/description → weighted
  - Opportunity type (SBIR/STTR > BAA > Solicitation > Sources Sought)
  - Due date proximity (urgent = more important to surface now)
  - Portal prestige (SAM.gov federal > DIU > NSTXL > state)
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Tuple

log = logging.getLogger(__name__)

# Keywords that strongly signal Velocity relevance — weighted higher
HIGH_VALUE_KEYWORDS = {
    "artificial intelligence": 15,
    "machine learning": 15,
    "autonomous systems": 12,
    "command and control": 12,
    "c2": 8,
    "natural language processing": 12,
    "computer vision": 12,
    "cobol modernization": 15,
    "legacy modernization": 12,
    "software modernization": 10,
    "c5isr": 10,
    "autonomous": 8,
    "ai": 6,
    "nlp": 8,
    "sensor fusion": 10,
    "edge computing": 8,
    "devSecOps": 8,
    "transcription": 10,
    "translation": 8,
    "data analytics": 6,
    "cloud migration": 6,
    "sbir": 5,
    "sttr": 5,
    "phase ii": 8,    # Phase II = existing traction, higher value
    "small business": 4,
    "set-aside": 4,
}

# Opportunity type scores
TYPE_SCORES = {
    "SBIR/STTR": 20,
    "BAA": 18,
    "Sources Sought": 10,   # early signal, good to respond to RFI
    "Pre-solicitation": 12,
    "Combined Synopsis": 14,
    "Solicitation": 14,
    "RFP": 14,
    "RFQ": 10,
    "DIU Commercial Solutions Opening (CSO)": 18,
    "S2MARTS OTA": 16,
    "SpEC OTA": 14,
    "OTA Opportunity": 12,
    "Microelectronics Commons OTA": 10,
    "RFI": 6,
}

# Portal prestige scores
PORTAL_SCORES = {
    "SAM.gov": 15,
    "DIU": 18,
    "NSTXL": 12,
    "Space Florida": 10,
    "BidNet Colorado": 6,
    "BidNet Florida": 6,
}

# NAICS codes Velocity cares about most
PRIORITY_NAICS = {
    "541511": 15,   # Custom Computer Programming
    "541512": 15,   # Computer Systems Design
    "541715": 12,   # R&D Engineering
    "541513": 10,
    "541330": 8,
    "541519": 8,
    "561990": 5,
}


def score_opportunity(opp: Dict) -> Tuple[int, str]:
    """
    Score an opportunity and return (score, reasoning).
    Higher score = more relevant to Velocity.
    """
    score = 0
    reasons = []

    title = str(opp.get("title", "")).lower()
    description = str(opp.get("description", "")).lower()
    search_text = f"{title} {description}"
    opp_type = opp.get("type", "")
    portal = opp.get("portal", "")
    naics = str(opp.get("naics_code", ""))
    due_date = opp.get("due_date", "")

    # NAICS score
    if naics in PRIORITY_NAICS:
        n = PRIORITY_NAICS[naics]
        score += n
        reasons.append(f"NAICS {naics} match (+{n})")

    # Keyword scores
    keyword_hits = []
    for kw, weight in HIGH_VALUE_KEYWORDS.items():
        if kw in search_text:
            score += weight
            keyword_hits.append(kw)
    if keyword_hits:
        top_hits = keyword_hits[:3]
        reasons.append(f"Keywords: {', '.join(top_hits)}")

    # Type score
    type_score = TYPE_SCORES.get(opp_type, 5)
    score += type_score
    if type_score >= 14:
        reasons.append(f"{opp_type} (+{type_score})")

    # Portal score
    portal_score = PORTAL_SCORES.get(portal, 5)
    score += portal_score

    # Due date urgency — boost opps due within 14 days
    if due_date:
        try:
            due = datetime.strptime(due_date[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            days_until = (due - datetime.now(timezone.utc)).days
            if 0 <= days_until <= 7:
                score += 20
                reasons.append(f"⚡ Due in {days_until}d — urgent")
            elif 8 <= days_until <= 14:
                score += 10
                reasons.append(f"Due in {days_until}d")
            elif days_until < 0:
                score -= 10  # Past due — deprioritize
        except ValueError:
            pass

    reasoning = " | ".join(reasons) if reasons else "General keyword match"
    return score, reasoning


def rank_opportunities(opps: List[Dict]) -> List[Dict]:
    """Score and sort opportunities by relevance. Returns list with score/reasoning added."""
    scored = []
    for opp in opps:
        s, r = score_opportunity(opp)
        enriched = {**opp, "yukon_score": s, "yukon_reasoning": r}
        scored.append(enriched)
    return sorted(scored, key=lambda x: x["yukon_score"], reverse=True)


def top_picks(opps: List[Dict], n: int = 5) -> List[Dict]:
    """Return the top N scored opportunities."""
    ranked = rank_opportunities(opps)
    return ranked[:n]
