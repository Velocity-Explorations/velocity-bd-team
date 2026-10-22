"""
Yukon — Velocity/Echo Fit Scorer
Scores each opportunity 1-10 against Velocity Explorations/Echo C2 capabilities
using RAG context from ChromaDB + deterministic heuristics.

Score dimensions (fit only — urgency is computed separately for display):
  - Technology match (30%): RAG cosine similarity vs bd_documents
  - Velocity AI/software relevance (35%): Keyword match for C2/AI/software terms
  - Past performance relevance (20%): RAG similarity vs past submissions
  - Contract vehicle fit (15%): Opp type vs known vehicles (SBIR, OTA, BAA)
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from scanner.calibration import load_calibration

log = logging.getLogger(__name__)

CHROMA_PATH = str(Path(__file__).parent.parent / "data" / "chroma")
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"

# ─── VELOCITY AI / SOFTWARE KEYWORD SETS ─────────────────────────────────────

# Keywords that signal Velocity-relevant work: Echo C2, AI/ML, software dev
# Tier 1: Echo C2 / tactical AI (highest relevance)
# Tier 2: General AI/ML and software development (strong relevance)
VELOCITY_KEYWORDS = {
    # Echo C2 / tactical (tier 1)
    "command and control": 1.0,
    "c2": 0.9,
    "c4isr": 0.9,
    "c5isr": 0.9,
    "decision support": 0.9,
    "autonomous decision": 1.0,
    "multi-domain": 0.8,
    "joint all-domain": 0.9,
    "jadc2": 1.0,
    "datalink": 0.9,
    "tactical data link": 0.9,
    "link 16": 0.8,
    "ddil": 1.0,
    "denied degraded": 0.9,
    "edge ai": 0.9,
    "coalition interoperability": 0.8,
    "joint interoperability": 0.8,
    "mission command": 0.8,
    "battle management": 0.8,
    "kill chain": 0.7,
    "sensor to shooter": 0.8,
    "fires network": 0.7,
    "situational awareness": 0.6,
    "common operating picture": 0.8,
    # AI / ML / data science (tier 2)
    "artificial intelligence": 0.7,
    "machine learning": 0.7,
    "ai/ml": 0.8,
    "autonomous systems": 0.7,
    "computer vision": 0.6,
    "natural language processing": 0.6,
    "nlp": 0.5,
    "transcription": 0.5,
    "translation": 0.5,
    "large language model": 0.7,
    "chatbot": 0.7,
    "conversational ai": 0.8,
    "sensor fusion": 0.7,
    "data analytics": 0.5,
    "data pipeline": 0.5,
    "predictive analytics": 0.5,
    # Software development / modernization (tier 2)
    "software development": 0.6,
    "software engineering": 0.6,
    "legacy modernization": 0.8,
    "legacy system": 0.6,
    "code modernization": 0.7,
    "cloud migration": 0.6,
    "devsecops": 0.7,
    "devops": 0.5,
    "saas": 0.5,
    "platform as a service": 0.4,
    "web application": 0.5,
    "mobile application": 0.4,
    "api integration": 0.5,
    "microservices": 0.4,
    "agile development": 0.4,
    "full stack": 0.4,
    "digital transformation": 0.5,
    "digital engineering": 0.5,
}

# Contract vehicle type scoring
VEHICLE_SCORES = {
    "SBIR/STTR": 1.0,            # Direct path — AATS, DeltaV, KAIROS
    "SBIR": 1.0,
    "BAA": 0.85,                  # R&D aligned
    "tech experimentation": 0.85, # Vulcan — prototype/experiment path, strong Echo fit
    "ota prototype": 0.80,        # Vulcan OTA — good path
    "commercial solutions opening": 0.80,
    "cso": 0.80,
    "capability demonstration": 0.75,  # Vulcan — demo path
    "s2marts": 0.75,
    "spec ota": 0.70,
    "ota opportunity": 0.70,
    "market research": 0.65,
    "crada": 0.65,               # Cooperative R&D agreements — viable Velocity path
    "solicitation": 0.60,        # Standard open competition — neutral
    "combined synopsis": 0.60,
    "rfi": 0.60,                 # Worth tracking, no penalty for early-stage
    "sources sought": 0.55,
    "pre-solicitation": 0.55,
    "rfp": 0.55,
    "rfq": 0.50,
    "prize challenge": 0.40,
    "microelectronics commons": 0.25,
}

# Out-of-domain signals — when present WITH zero Velocity keyword hits, score near 1.0
OUT_OF_DOMAIN_KEYWORDS = [
    "manufacturing", "fabrication", "machining", "welding",
    "construction", "paving", "roofing", "plumbing", "electrical contractor",
    "janitorial", "custodial", "landscaping", "grounds maintenance",
    "laundry", "food service", "catering",
    "medical equipment", "medical device", "laboratory equipment",
    "fuel supply", "petroleum", "lubricant",
    "vehicle maintenance", "fleet maintenance", "forklift",
    "ammunition", "munitions", "ordnance disposal",
    "furniture", "office supplies",
    "guard service", "security guard", "physical security",
    "moving service", "relocation service",
    "printing service", "mail service",
]

# Past performance program names to look for in RAG results
PAST_PERFORMANCE_PROGRAMS = [
    "aats", "deltav", "delta v", "capella", "apfit", "echo",
    "sparx", "cobra gold", "indopacom", "niwc", "sbir", "phase ii",
    "phase iii", "ai talent", "finops", "peo c3t", "pm c2s",
]


# ─── EMBEDDING + RAG ─────────────────────────────────────────────────────────

def _embed(text: str) -> Optional[List[float]]:
    """Embed text via Ollama nomic-embed-text. Returns None on failure."""
    try:
        import requests
        resp = requests.post(
            OLLAMA_URL,
            json={"model": EMBED_MODEL, "prompt": text[:2000]},
            timeout=15,
        )
        if resp.status_code != 200:
            log.warning(f"Ollama embed failed: HTTP {resp.status_code}")
            return None
        emb = resp.json().get("embedding")
        return emb if emb else None
    except Exception as e:
        log.warning(f"Ollama embed error: {e}")
        return None


def _query_collection(collection_name: str, query_emb: List[float], n_results: int = 3,
                      where_filter: dict = None):
    """Query a ChromaDB collection. Returns (documents, metadatas, distances) or None."""
    try:
        import chromadb
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        col = client.get_collection(collection_name)
        kwargs = {"query_embeddings": [query_emb], "n_results": n_results}
        if where_filter:
            kwargs["where"] = where_filter
        results = col.query(**kwargs)
        return (
            results.get("documents", [[]])[0],
            results.get("metadatas", [[]])[0],
            results.get("distances", [[]])[0],
        )
    except Exception as e:
        log.warning(f"ChromaDB query ({collection_name}) failed: {e}")
        return None


def _cosine_similarity_from_distance(distances: List[float]) -> List[float]:
    """
    Convert ChromaDB L2 distances to absolute similarity scores.

    Recalibrated April 2026 against enriched Velocity RAG store
    (bd_documents: 49 proposal/capability docs, bd_activities: 16 past performance entries).

    Empirical distance ranges observed:
      dist <= 250  → strong match (core Velocity domain — C2, AI, SBIR)
      dist 250-290 → good match (adjacent tech — secure comms, TAK, COBOL)
      dist 290-330 → moderate (tangentially related)
      dist 330-370 → weak (different domain but some shared DoD language)
      dist >  370  → poor/no match
    """
    BREAKPOINTS = [
        (180, 0.95),
        (210, 0.82),
        (240, 0.65),
        (270, 0.50),
        (300, 0.38),
        (330, 0.26),
        (360, 0.16),
        (400, 0.08),
        (float('inf'), 0.03),
    ]

    sims = []
    for d in distances:
        for max_d, sim_val in BREAKPOINTS:
            if d <= max_d:
                sims.append(sim_val)
                break
    return sims


# ─── SCORING DIMENSIONS ──────────────────────────────────────────────────────

def _score_tech_match(query_emb: Optional[List[float]]) -> Tuple[float, str]:
    """
    Dimension 1 — Technology match (weight: 30%).
    RAG cosine similarity of opp description vs bd_documents.
    Returns (score 0-10, detail string).
    """
    if query_emb is None:
        return 5.0, "RAG unavailable"

    # Exclude contract boilerplate and non-capability docs from tech matching
    TECH_DOC_TYPES = [
        "proposal", "capability_statement", "capability_brief", "white_paper",
        "pws", "sow", "rfi", "charter", "other",
    ]
    result = _query_collection(
        "bd_documents", query_emb, n_results=15,
        where_filter={"doc_type": {"$in": TECH_DOC_TYPES}},
    )
    if result is None:
        result = _query_collection("bd_documents", query_emb, n_results=3)
    if result is None:
        return 5.0, "ChromaDB unavailable"

    # Filter out known noise sources that match everything generically
    NOISE_SOURCES = {
        "AI-Talent-2.0-BOA-Holder-POC-List.xlsx",
        "CDAO-AI-Talent-2.0-BOA-Ordering-Guide-January-2025 (1).docx",
        "VelocityExplorations_AAMAC_Vol2_CrossReference_Matrix.xlsx",
        "VelocityExplorations_AAMAC_Vol2_SelfScoring_Matrix.xlsx",
        "Statement+of+Work++Template+Version.docx",
        "Project Charter.docx",
        "SF254-D1204 LOS-VP-Draft.docx",
        "SF254_D1204_CoS_Velocity_Exploration.pptx",
        "SF254-D1204-Proposal Timeline (1).pptx",
    }
    docs, metas, distances = result
    filtered = [(d, m, dist) for d, m, dist in zip(docs, metas, distances)
                if m.get("source", "") not in NOISE_SOURCES]
    if filtered:
        docs, metas, distances = zip(*filtered)
        docs, metas, distances = list(docs), list(metas), list(distances)

    if not distances:
        return 3.0, "No document matches"

    sims = _cosine_similarity_from_distance(distances)
    avg_sim = sum(sims) / len(sims)
    best_sim = max(sims)

    # Map similarity to 1-10 scale
    # 0.95 sim → 10, 0.70 sim → 7, 0.38 sim → 4, 0.12 sim → 1.5
    score = min(10.0, max(1.0, best_sim * 10.5))

    # Get best matching doc info
    best_idx = sims.index(best_sim)
    best_doc_name = metas[best_idx].get("source", "doc") if metas else "doc"
    # Use last part of filename for readability
    best_doc_short = best_doc_name.replace("_", " ").replace(".docx","").replace(".pdf","").replace(".txt","")[:45]
    detail = f"Best match: {best_doc_short} (sim={best_sim:.2f})"

    return round(score, 1), detail


def _score_velocity_fit(search_text: str, kw_adj: Dict = None) -> Tuple[float, str]:
    """
    Dimension 2 — Velocity AI/software relevance (weight: 30%).
    Keyword match against Echo C2, AI/ML, and software development terms.
    Returns (score 0-10, detail string).
    """
    if kw_adj is None:
        kw_adj = {}
    text_lower = search_text.lower()
    hits = []
    total_weight = 0.0

    for kw, weight in VELOCITY_KEYWORDS.items():
        if kw in text_lower:
            hits.append(kw)
            adj = kw_adj.get(kw, 1.0)
            total_weight += weight * adj

    if not hits:
        return 1.0, "No Velocity keyword matches"

    score = min(10.0, max(1.0, 1.0 + total_weight * 3.0))
    top_hits = hits[:4]
    detail = f"Velocity fit: {', '.join(top_hits)}"
    return round(score, 1), detail


def _score_past_performance(query_emb: Optional[List[float]], search_text: str) -> Tuple[float, str]:
    """
    Dimension 3 — Past performance relevance (weight: 20%).
    RAG similarity vs past submissions + keyword detection of known programs.
    Returns (score 0-10, detail string).
    """
    program_hits = []
    text_lower = search_text.lower()
    for prog in PAST_PERFORMANCE_PROGRAMS:
        if prog in text_lower:
            program_hits.append(prog)

    rag_score = 0.0
    rag_detail = ""

    if query_emb is not None:
        # Search bd_activities for past BD pipeline matches
        result = _query_collection("bd_activities", query_emb, n_results=3)
        if result is not None:
            docs, metas, distances = result
            if distances:
                sims = _cosine_similarity_from_distance(distances)
                best_sim = max(sims)
                rag_score = min(10.0, max(0.0, best_sim * 10.5))
                best_idx = sims.index(best_sim)
                pp_name = (metas[best_idx].get("company") or metas[best_idx].get("title", "activity"))[:40] if metas else "activity"
                rag_detail = f"Similar to: {pp_name}"

    # Combine RAG score with program keyword hits
    keyword_bonus = min(4.0, len(program_hits) * 1.5)
    combined = min(10.0, max(1.0, rag_score * 0.6 + keyword_bonus + 1.0))

    details = []
    if program_hits:
        details.append(f"Programs: {', '.join(program_hits[:3])}")
    if rag_detail:
        details.append(rag_detail)
    if not details:
        details.append("No direct past performance match")

    return round(combined, 1), "; ".join(details)


def _score_vehicle_fit(opp_type: str) -> Tuple[float, str]:
    """
    Dimension 4 — Contract vehicle fit (weight: 15%).
    Maps opp type to known Velocity vehicles: SBIR, OTA, BAA, etc.
    Returns (score 0-10, detail string).
    """
    # Normalize type for matching
    type_upper = opp_type.upper() if opp_type else ""

    # Direct lookup first
    if opp_type in VEHICLE_SCORES:
        raw = VEHICLE_SCORES[opp_type]
        score = max(1.0, raw * 10.0)
        detail = f"{opp_type} vehicle"
        if raw >= 0.85:
            detail += " — strong Velocity fit"
        return round(score, 1), detail

    # Fuzzy type matching
    if "SBIR" in type_upper or "STTR" in type_upper:
        return 10.0, "SBIR/STTR — direct Velocity path (AATS, DeltaV)"
    if "OTA" in type_upper:
        return 7.0, "OTA vehicle — aligns with S2MARTS/SpEC membership"
    if "BAA" in type_upper:
        return 8.5, "BAA — R&D aligned"
    if "CSO" in type_upper:
        return 8.0, "CSO — DIU commercial pathway"
    if "RFI" in type_upper or "SOURCES" in type_upper:
        return 3.0, f"{opp_type} — early signal, low commitment"

    return 5.0, f"{opp_type or 'Unknown'} vehicle"


def _score_urgency(due_date: str) -> Tuple[float, str]:
    """
    Dimension 5 — Urgency / actionability (weight: 10%).
    Based on days until deadline.
    Returns (score 0-10, detail string).
    """
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


# ─── MAIN SCORER ──────────────────────────────────────────────────────────────

WEIGHTS = {
    "tech_match": 0.30,
    "velocity_fit": 0.35,
    "past_perf": 0.20,
    "vehicle": 0.15,
}


def score_opportunity(opp: dict, kw_adj: Dict = None, weights: Dict = None,
                      neg_kw: List = None) -> dict:
    """
    Score a single opportunity against Velocity/Echo capabilities.
    Returns the opp dict with yukon_score (1.0-10.0) and yukon_reasoning added.
    """
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

    att_len = len(full_attachment)
    if att_len > 2000:
        mid_start = att_len // 4
        att_excerpt = full_attachment[mid_start:mid_start + 1500]
    else:
        att_excerpt = full_attachment
    query_text = f"{title} {description} {att_excerpt}"[:800]
    query_emb = _embed(query_text)

    tech_score, tech_detail = _score_tech_match(query_emb)
    vel_score, vel_detail = _score_velocity_fit(search_text, kw_adj)
    perf_score, perf_detail = _score_past_performance(query_emb, search_text)
    vehicle_score, vehicle_detail = _score_vehicle_fit(opp_type)
    urgency_score, urgency_detail = _score_urgency(due_date)

    composite = (
        tech_score * weights.get("tech_match", 0.30)
        + vel_score * weights.get("velocity_fit", 0.35)
        + perf_score * weights.get("past_perf", 0.20)
        + vehicle_score * weights.get("vehicle", 0.15)
    )

    all_negatives = list(OUT_OF_DOMAIN_KEYWORDS) + neg_kw
    if vel_score < 2.0:
        title_desc = f"{title} {description}".lower()
        has_negative = any(kw in title_desc for kw in all_negatives)
        if has_negative:
            composite = min(composite, 1.5)
        else:
            composite = min(composite, 3.5)

    final_score = round(min(10.0, max(1.0, composite)), 1)

    # Build reasoning — include the strongest signals
    reasoning_parts = []
    scores = [
        (vel_score, vel_detail, "Velocity fit"),
        (tech_score, tech_detail, "Tech"),
        (perf_score, perf_detail, "Past perf"),
        (vehicle_score, vehicle_detail, "Vehicle"),
    ]
    scores.sort(key=lambda x: x[0], reverse=True)

    for dim_score, detail, label in scores:
        if dim_score >= 7.0:
            reasoning_parts.append(detail)
        elif dim_score >= 5.0 and len(reasoning_parts) < 2:
            reasoning_parts.append(detail)

    reasoning = " | ".join(reasoning_parts) if reasoning_parts else "Low overall fit"

    enriched = {
        **opp,
        "yukon_score": final_score,
        "yukon_reasoning": reasoning,
        "yukon_urgency": urgency_detail,
        "score_tech": tech_score,
        "score_echo": vel_score,
        "score_past": perf_score,
        "score_vehicle": vehicle_score,
        "score_urgency": urgency_score,
    }
    return enriched


def score_opportunities(opps: list, project_root: Path = None) -> list:
    """
    Score and sort a list of opportunities by Velocity/Echo fit.
    Returns list sorted by yukon_score descending.
    """
    if not opps:
        return []

    if project_root is None:
        project_root = Path(__file__).parent.parent

    cal = load_calibration("velocity", project_root)
    kw_adj = cal.get("keyword_adjustments", {}) if cal else {}
    wt_adj = cal.get("weight_adjustments", {}) if cal else {}
    neg_kw = cal.get("negative_keywords", []) if cal else []

    effective_weights = dict(WEIGHTS)
    for dim, mult in wt_adj.items():
        if dim in effective_weights:
            effective_weights[dim] = round(effective_weights[dim] * mult, 3)

    if cal:
        log.info(f"Calibration loaded: {len(kw_adj)} keyword adjustments, "
                 f"{len(wt_adj)} weight adjustments, {len(neg_kw)} negative keywords")

    log.info(f"Velocity scoring {len(opps)} opportunities...")
    scored = []
    for opp in opps:
        try:
            scored.append(score_opportunity(opp, kw_adj, effective_weights, neg_kw))
        except Exception as e:
            log.error(f"Scoring failed for '{opp.get('title', '?')[:50]}': {e}")
            scored.append({
                **opp,
                "yukon_score": 3.0,
                "yukon_reasoning": f"Scoring error — fallback ({e})",
            })

    ranked = sorted(scored, key=lambda x: x["yukon_score"], reverse=True)
    log.info(f"Velocity scoring complete. Top score: {ranked[0]['yukon_score'] if ranked else 'N/A'}")
    return ranked
