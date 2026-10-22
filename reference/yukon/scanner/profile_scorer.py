"""
Yukon — Profile-Aware Keyword Scorer
Scores opportunities 1-10 using the profile's own keywords from profile.yaml.

For profiles without a dedicated scorer (i.e., everything except Velocity),
this builds keyword weights dynamically from the profile config.

Score dimensions (fit only — urgency is computed separately for display):
  - Keyword match (50%): Profile keywords found in title/description/attachments
  - NAICS match (20%): Opp NAICS code matches profile's NAICS list
  - Contract vehicle fit (15%): Opp type vs common vehicles
  - Knowledge-base match (15%): Keyword overlap with profile knowledge-base docs
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from scanner.calibration import load_calibration

log = logging.getLogger(__name__)

VEHICLE_SCORES = {
    "SBIR/STTR": 0.7,
    "SBIR": 0.7,
    "BAA": 0.6,
    "solicitation": 0.8,
    "combined synopsis": 0.7,
    "rfp": 0.8,
    "rfq": 0.7,
    "rfi": 0.5,
    "sources sought": 0.5,
    "pre-solicitation": 0.5,
}

WEIGHTS = {
    "keyword_fit": 0.50,
    "naics_match": 0.20,
    "vehicle": 0.15,
    "kb_match": 0.15,
}


def _build_keyword_weights(keywords: List[str]) -> Dict[str, float]:
    if not keywords:
        return {}
    weights = {}
    for i, kw in enumerate(keywords):
        kw_lower = kw.lower().strip()
        if not kw_lower:
            continue
        rank_weight = max(0.4, 1.0 - (i * 0.05))
        weights[kw_lower] = round(rank_weight, 2)
    return weights


def _load_knowledge_base(profile_name: str, project_root: Path) -> str:
    kb_dir = project_root / "configs" / profile_name / "knowledge-base"
    if not kb_dir.exists():
        return ""
    parts = []
    for f in sorted(kb_dir.glob("*.md")):
        try:
            parts.append(f.read_text()[:2000])
        except Exception:
            continue
    return " ".join(parts).lower()


def _score_keyword_fit(search_text: str, keyword_weights: Dict[str, float],
                       kw_adj: Dict[str, float] = None) -> Tuple[float, str]:
    if kw_adj is None:
        kw_adj = {}
    text_lower = search_text.lower()
    hits = []
    total_weight = 0.0

    for kw, weight in keyword_weights.items():
        if kw in text_lower:
            hits.append(kw)
            adj = kw_adj.get(kw, 1.0)
            total_weight += weight * adj

    if not hits:
        return 1.0, "No keyword matches"

    score = min(10.0, max(1.0, 1.0 + total_weight * 2.5))
    top_hits = hits[:4]
    detail = f"Keywords: {', '.join(top_hits)}"
    return round(score, 1), detail


def _score_naics_match(opp_naics: str, profile_naics: List[str]) -> Tuple[float, str]:
    if not opp_naics or not profile_naics:
        return 5.0, "No NAICS data"

    opp_code = str(opp_naics).strip()
    for code in profile_naics:
        if opp_code == str(code).strip():
            return 10.0, f"NAICS {opp_code} — exact match"
        if opp_code.startswith(str(code).strip()[:4]):
            return 7.0, f"NAICS {opp_code} — partial match ({code})"

    return 2.0, f"NAICS {opp_code} — no match"


def _score_vehicle_fit(opp_type: str) -> Tuple[float, str]:
    if not opp_type:
        return 5.0, "Unknown vehicle"

    type_lower = opp_type.lower()
    for vehicle, score_pct in VEHICLE_SCORES.items():
        if vehicle in type_lower:
            score = max(1.0, score_pct * 10.0)
            return round(score, 1), f"{opp_type} vehicle"

    return 5.0, f"{opp_type} vehicle"


def _score_kb_match(search_text: str, kb_text: str, keywords: List[str]) -> Tuple[float, str]:
    if not kb_text:
        return 5.0, "No knowledge base"

    text_lower = search_text.lower()

    kb_terms = set()
    for kw in keywords:
        if kw.lower() in kb_text:
            kb_terms.add(kw.lower())

    hits = [t for t in kb_terms if t in text_lower]
    if not hits:
        return 2.0, "No knowledge-base overlap"

    score = min(10.0, max(1.0, 2.0 + len(hits) * 1.5))
    return round(score, 1), f"KB overlap: {', '.join(hits[:3])}"


def _score_urgency(due_date: str) -> Tuple[float, str]:
    if not due_date:
        return 5.0, "No deadline — medium urgency"
    try:
        due = datetime.strptime(due_date[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        days = (due - datetime.now(timezone.utc)).days
        if days < 0:
            return 2.0, f"Past due ({abs(days)}d ago)"
        elif days <= 14:
            return 10.0, f"Due in {days}d — urgent"
        elif days <= 60:
            return 7.0, f"Due in {days}d — actionable"
        elif days <= 180:
            return 4.0, f"Due in {days}d — long horizon"
        else:
            return 2.0, f"Due in {days}d — very far out"
    except ValueError:
        return 5.0, "Unparseable deadline"


def score_opportunity(opp: dict, keyword_weights: Dict[str, float],
                      profile_naics: List[str], kb_text: str,
                      keywords: List[str], kw_adj: Dict = None,
                      weights: Dict = None, neg_kw: List = None) -> dict:
    if kw_adj is None:
        kw_adj = {}
    if weights is None:
        weights = WEIGHTS
    if neg_kw is None:
        neg_kw = []

    title = str(opp.get("title", ""))
    description = str(opp.get("description", ""))
    full_attachment = str(opp.get("attachment_text", ""))
    search_text = f"{title} {description} {full_attachment}".strip()
    opp_type = opp.get("type", "")
    due_date = opp.get("due_date", "")
    opp_naics = opp.get("naics_code", "")

    kw_score, kw_detail = _score_keyword_fit(search_text, keyword_weights, kw_adj)
    naics_score, naics_detail = _score_naics_match(opp_naics, profile_naics)
    vehicle_score, vehicle_detail = _score_vehicle_fit(opp_type)
    kb_score, kb_detail = _score_kb_match(search_text, kb_text, keywords)
    urgency_score, urgency_detail = _score_urgency(due_date)

    composite = (
        kw_score * weights.get("keyword_fit", 0.50)
        + naics_score * weights.get("naics_match", 0.20)
        + vehicle_score * weights.get("vehicle", 0.15)
        + kb_score * weights.get("kb_match", 0.15)
    )

    title_desc = f"{title} {description}".lower()
    has_negative = any(kw in title_desc for kw in neg_kw) if neg_kw else False
    if kw_score < 2.0 and naics_score < 5.0:
        composite = min(composite, 1.5 if has_negative else 2.5)

    final_score = round(min(10.0, max(1.0, composite)), 1)

    reasoning_parts = []
    scores = [
        (kw_score, kw_detail, "Keywords"),
        (naics_score, naics_detail, "NAICS"),
        (vehicle_score, vehicle_detail, "Vehicle"),
        (kb_score, kb_detail, "KB"),
    ]
    scores.sort(key=lambda x: x[0], reverse=True)
    for dim_score, detail, label in scores:
        if dim_score >= 7.0:
            reasoning_parts.append(detail)
        elif dim_score >= 5.0 and len(reasoning_parts) < 2:
            reasoning_parts.append(detail)

    reasoning = " | ".join(reasoning_parts) if reasoning_parts else "Low overall fit"

    return {
        **opp,
        "yukon_score": final_score,
        "yukon_reasoning": reasoning,
        "yukon_urgency": urgency_detail,
        "score_tech": kw_score,
        "score_echo": naics_score,
        "score_past": kb_score,
        "score_vehicle": vehicle_score,
        "score_urgency": urgency_score,
    }


def score_opportunities(opps: list, profile_name: str, profile=None,
                        project_root: Path = None) -> list:
    if not opps:
        return []

    if project_root is None:
        project_root = Path(__file__).parent.parent

    if profile is None:
        from scanner.profile import load_profile
        profile = load_profile(profile_name, project_root)

    keyword_weights = _build_keyword_weights(profile.keywords)
    kb_text = _load_knowledge_base(profile_name, project_root)

    cal = load_calibration(profile_name, project_root)
    kw_adj = cal.get("keyword_adjustments", {}) if cal else {}
    wt_adj = cal.get("weight_adjustments", {}) if cal else {}
    neg_kw = cal.get("negative_keywords", []) if cal else []

    effective_weights = dict(WEIGHTS)
    for dim, mult in wt_adj.items():
        if dim in effective_weights:
            effective_weights[dim] = round(effective_weights[dim] * mult, 3)

    if cal:
        log.info(f"Calibration loaded: {len(kw_adj)} keyword adj, {len(wt_adj)} weight adj, {len(neg_kw)} negative kw")

    log.info(f"Profile scoring {len(opps)} opportunities for '{profile_name}' "
             f"({len(keyword_weights)} keywords, KB {'loaded' if kb_text else 'empty'})...")

    scored = []
    for opp in opps:
        try:
            scored.append(score_opportunity(
                opp, keyword_weights, profile.naics, kb_text, profile.keywords,
                kw_adj=kw_adj, weights=effective_weights, neg_kw=neg_kw,
            ))
        except Exception as e:
            log.error(f"Scoring failed for '{opp.get('title', '?')[:50]}': {e}")
            scored.append({
                **opp,
                "yukon_score": 3.0,
                "yukon_reasoning": f"Scoring error — fallback ({e})",
            })

    ranked = sorted(scored, key=lambda x: x["yukon_score"], reverse=True)
    log.info(f"Profile scoring complete. Top score: {ranked[0]['yukon_score'] if ranked else 'N/A'}")
    return ranked
