"""
Yukon — Score Calibration from Triage Data
Analyzes valid/not_valid decisions to generate per-profile calibration adjustments.

Produces a calibration.json per profile at configs/<profile>/calibration.json:
  - keyword_adjustments: keyword -> multiplier (e.g., 0.3 = downweight 70%)
  - weight_adjustments: dimension weight overrides
  - generated_at: timestamp
  - sample_size: number of decisions used
"""

import json
import logging
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.request import Request, urlopen
from urllib.error import URLError

log = logging.getLogger(__name__)

MIN_SAMPLE_SIZE = 15
MIN_KEYWORD_OCCURRENCES = 3
MAX_ADJUSTMENT = 3.0
MIN_ADJUSTMENT = 0.15


def _api_base() -> str:
    return os.environ.get("YUKON_API_URL", "http://127.0.0.1:3000")


def _scanner_token() -> str:
    return os.environ.get("SCANNER_API_TOKEN", "")


def fetch_triage_data(profile: str) -> List[dict]:
    url = f"{_api_base()}/api/scanner/triage-data?profile={profile}&limit=500"
    headers = {
        "Authorization": f"Bearer {_scanner_token()}",
        "Content-Type": "application/json",
    }
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return data.get("decisions", [])
    except (URLError, Exception) as e:
        log.error(f"Failed to fetch triage data for {profile}: {e}")
        return []


def _extract_keywords_from_text(text: str) -> List[str]:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s/]", " ", text)
    words = text.split()
    unigrams = [w for w in words if len(w) >= 3]
    bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)]
    return unigrams + bigrams


def analyze_keyword_patterns(
    valid_opps: List[dict],
    not_valid_opps: List[dict],
    profile_keywords: List[str],
) -> Dict[str, float]:
    valid_kw_counts = Counter()
    not_valid_kw_counts = Counter()

    for opp in valid_opps:
        text = f"{opp.get('title', '')} {(opp.get('description') or '')[:500]}".lower()
        for kw in profile_keywords:
            if kw.lower() in text:
                valid_kw_counts[kw.lower()] += 1

    for opp in not_valid_opps:
        text = f"{opp.get('title', '')} {(opp.get('description') or '')[:500]}".lower()
        for kw in profile_keywords:
            if kw.lower() in text:
                not_valid_kw_counts[kw.lower()] += 1

    adjustments = {}
    all_keywords = set(valid_kw_counts.keys()) | set(not_valid_kw_counts.keys())

    for kw in all_keywords:
        v_count = valid_kw_counts.get(kw, 0)
        nv_count = not_valid_kw_counts.get(kw, 0)
        total = v_count + nv_count

        if total < MIN_KEYWORD_OCCURRENCES:
            continue

        valid_rate = v_count / total
        # valid_rate=1.0 → boost (2.0x), valid_rate=0.5 → neutral (1.0x), valid_rate=0.0 → suppress (0.2x)
        if valid_rate >= 0.7:
            multiplier = 1.0 + (valid_rate - 0.5) * 2.0
        elif valid_rate <= 0.3:
            multiplier = max(MIN_ADJUSTMENT, valid_rate * 2.0 + 0.1)
        else:
            continue

        multiplier = min(MAX_ADJUSTMENT, max(MIN_ADJUSTMENT, multiplier))
        if abs(multiplier - 1.0) > 0.1:
            adjustments[kw] = round(multiplier, 2)

    return adjustments


def compute_weight_adjustments(
    valid_opps: List[dict],
    not_valid_opps: List[dict],
) -> Dict[str, float]:
    def avg_scores(opps, key):
        vals = [o.get(key) for o in opps if o.get(key) is not None]
        return sum(vals) / len(vals) if vals else None

    adjustments = {}
    dimensions = [
        ("scoreTech", "tech_match" if True else "keyword_fit"),
        ("scoreEcho", "velocity_fit" if True else "naics_match"),
        ("scorePast", "past_perf" if True else "kb_match"),
        ("scoreVehicle", "vehicle"),
    ]

    for score_key, weight_key in dimensions:
        v_avg = avg_scores(valid_opps, score_key)
        nv_avg = avg_scores(not_valid_opps, score_key)

        if v_avg is None or nv_avg is None:
            continue

        separation = v_avg - nv_avg
        # If valid opps score much higher on this dimension, it's a good discriminator — boost it
        # If there's no separation, this dimension isn't helping — slightly reduce
        if separation > 2.0:
            adjustments[weight_key] = 1.2
        elif separation < 0.5:
            adjustments[weight_key] = 0.85

    return adjustments


def _discover_negative_keywords(not_valid_opps: List[dict], valid_opps: List[dict]) -> List[str]:
    nv_words = Counter()
    v_words = Counter()

    for opp in not_valid_opps:
        text = f"{opp.get('title', '')}".lower()
        for w in set(text.split()):
            if len(w) >= 4:
                nv_words[w] += 1

    for opp in valid_opps:
        text = f"{opp.get('title', '')}".lower()
        for w in set(text.split()):
            if len(w) >= 4:
                v_words[w] += 1

    negatives = []
    for word, nv_count in nv_words.most_common(100):
        if nv_count < 3:
            break
        v_count = v_words.get(word, 0)
        total = nv_count + v_count
        if total >= 4 and (nv_count / total) >= 0.85:
            negatives.append(word)

    return negatives[:20]


def generate_calibration(
    profile_name: str,
    project_root: Path,
    profile_keywords: Optional[List[str]] = None,
) -> Optional[dict]:
    decisions = fetch_triage_data(profile_name)
    if not decisions:
        log.warning(f"No triage data for {profile_name}")
        return None

    valid_opps = [d for d in decisions if d["reviewStatus"] == "valid"]
    not_valid_opps = [d for d in decisions if d["reviewStatus"] == "not_valid"]
    total = len(valid_opps) + len(not_valid_opps)

    log.info(f"Calibration for {profile_name}: {len(valid_opps)} valid, {len(not_valid_opps)} not_valid")

    if total < MIN_SAMPLE_SIZE:
        log.warning(f"Insufficient triage data ({total} < {MIN_SAMPLE_SIZE}) — skipping calibration")
        return None

    if profile_keywords is None:
        from scanner.profile import load_profile
        profile = load_profile(profile_name, project_root)
        profile_keywords = profile.keywords

    keyword_adj = analyze_keyword_patterns(valid_opps, not_valid_opps, profile_keywords)
    weight_adj = compute_weight_adjustments(valid_opps, not_valid_opps)
    negative_keywords = _discover_negative_keywords(not_valid_opps, valid_opps)

    calibration = {
        "profile": profile_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sample_size": total,
        "valid_count": len(valid_opps),
        "not_valid_count": len(not_valid_opps),
        "keyword_adjustments": keyword_adj,
        "weight_adjustments": weight_adj,
        "negative_keywords": negative_keywords,
    }

    out_path = project_root / "configs" / profile_name / "calibration.json"
    out_path.write_text(json.dumps(calibration, indent=2) + "\n")
    log.info(f"Calibration written to {out_path} ({len(keyword_adj)} keyword adjustments, "
             f"{len(weight_adj)} weight adjustments, {len(negative_keywords)} negative keywords)")

    return calibration


def load_calibration(profile_name: str, project_root: Path) -> Optional[dict]:
    path = project_root / "configs" / profile_name / "calibration.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception as e:
        log.warning(f"Failed to load calibration for {profile_name}: {e}")
        return None
