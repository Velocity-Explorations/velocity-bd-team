"""
Yukon — Opportunity filter
Matches opportunities against a profile's NAICS codes and keywords.

Matching logic:
  - Opp HAS a NAICS code → must be in profile.naics list (strict gate)
  - Opp has NO NAICS code → keyword match using the appropriate keyword set
  - EXCLUSION: reject opps matching known noise patterns regardless of NAICS/keyword
  - SET-ASIDE: if profile.set_asides non-empty, opp must match or have no restriction
"""

import logging
import re
from typing import List, Dict

from scanner.profile import Profile

log = logging.getLogger(__name__)

# Portal IDs that use bidnet_keywords instead of scrape_keywords
BIDNET_PORTAL_IDS = {"bidnet_colorado", "bidnet_florida"}

# Title/description patterns that indicate irrelevant opportunities
# These are applied AFTER NAICS/keyword match as a final rejection filter
EXCLUSION_PATTERNS = [
    # Hardware repair and modification
    r"\bin repair\b", r"\bmodification of\b", r"repair\/modification",
    r"\brepair of\b", r"\boverhaul\b",

    # Physical/mechanical parts and equipment
    r"\bhose assembly\b", r"\bcable assy\b", r"\bvalve\b",
    r"\bpump assy\b", r"\bgenerator\b", r"\bcooler unit\b",
    r"\bfilter element\b", r"\bseal assy\b", r"\bshaft\b",
    r"\bimpeller\b", r"\bslat;aircraft\b", r"\bwindshield panel\b",
    r"\bchassis electrical\b", r"\btailpiece\b", r"\belbow\b",
    r"\bplate assy\b", r"\bcircuit card\b(?!.*software)",
    r"\bcontainer;collapsib\b", r"\blight;navigational\b",

    # Medical equipment (not medical AI/software)
    r"\bhemochron\b", r"\bventana\b", r"\bosmolality\b",
    r"\bmedical cart\b", r"\bmedical equipment\b", r"\blab equipment\b",
    r"\bsurgical\b", r"\bpathology\b",

    # Physical construction/facilities
    r"\bflooring\b", r"\bpainting\b", r"\bconstruction\b(?!.*software)",
    r"\babatement\b", r"\bbolt replacement\b", r"\bairfield lighting\b",
    r"\bboiler\b", r"\bplumbing\b", r"\belectrical circuit\b",

    # Logistics/shipping
    r"\bshipping and storage\b", r"\bfreight\b", r"\btransportation\b(?!.*software)",
    r"\bdrayage\b",

    # Admin/management services (not software dev)
    r"\bdocument destruction\b", r"\bsensitive document\b",
    r"\bmotor bearings\b", r"\bturning tool\b",

    # Events/industry days (not contracts)
    r"\breverse industry day\b", r"\bindustry day\b",
    r"\bconference\b(?!.*software)", r"\bsymposium\b",

    # Financial investigation (not Velocity's domain)
    r"\bfinancial investigation\b",

    # IT management/admin (not software development)
    r"\bit management\b(?!.*software|.*development)",
    r"\bstrategic.*planning.*administrative\b",
    r"\badministrative support\b(?!.*software)",
    r"\binspector general\b",

    # PLC/industrial training
    r"\bplc training\b", r"\bprogrammable logic controller\b",
]

# Compile patterns once
_COMPILED_EXCLUSIONS = [re.compile(p, re.IGNORECASE) for p in EXCLUSION_PATTERNS]


def is_excluded(opp: Dict) -> bool:
    """Return True if the opportunity matches a noise exclusion pattern."""
    search_text = " ".join([
        str(opp.get("title", "")),
        str(opp.get("description", "")),
    ])
    for pattern in _COMPILED_EXCLUSIONS:
        if pattern.search(search_text):
            return True
    return False


def _exclusion_reason(opp: Dict) -> str:
    """Return the exclusion pattern that matched, or empty string."""
    search_text = " ".join([
        str(opp.get("title", "")),
        str(opp.get("description", "")),
    ])
    for pattern in _COMPILED_EXCLUSIONS:
        m = pattern.search(search_text)
        if m:
            return f"noise pattern: {pattern.pattern}"
    return ""


def matches_profile(opp: Dict, profile: Profile, portal_id: str = "") -> bool:
    """Return True if an opportunity is relevant to this profile."""

    opp_naics = str(opp.get("naics_code", "")).strip()

    if opp_naics:
        # PRIMARY gate: NAICS must match
        if opp_naics not in profile.naics:
            return False
    else:
        # No NAICS — use portal-appropriate keyword set
        if portal_id in BIDNET_PORTAL_IDS:
            keywords = profile.bidnet_keywords
        else:
            keywords = profile.scrape_keywords

        search_text = " ".join([
            str(opp.get("title", "")),
            str(opp.get("description", "")),
        ]).lower()

        if not any(kw in search_text for kw in keywords):
            return False

    # EXCLUSION filter — reject known noise even if NAICS/keyword matched
    if is_excluded(opp):
        return False

    # SET-ASIDE filter
    if profile.set_asides:
        opp_setaside = str(opp.get("set_aside", "")).upper().strip()
        if opp_setaside and not any(sa in opp_setaside for sa in profile.set_asides):
            return False

    return True


def rejection_reason(opp: Dict, profile: Profile, portal_id: str = "") -> str:
    """Return why an opp was rejected, or empty string if it passes."""
    opp_naics = str(opp.get("naics_code", "")).strip()

    if opp_naics:
        if opp_naics not in profile.naics:
            return f"NAICS {opp_naics} not in profile"
    else:
        if portal_id in BIDNET_PORTAL_IDS:
            keywords = profile.bidnet_keywords
        else:
            keywords = profile.scrape_keywords

        search_text = " ".join([
            str(opp.get("title", "")),
            str(opp.get("description", "")),
        ]).lower()

        if not any(kw in search_text for kw in keywords):
            return "no keyword match"

    excl = _exclusion_reason(opp)
    if excl:
        return excl

    if profile.set_asides:
        opp_setaside = str(opp.get("set_aside", "")).upper().strip()
        if opp_setaside and not any(sa in opp_setaside for sa in profile.set_asides):
            return f"set-aside {opp_setaside} not in profile"

    return ""


def filter_opportunities(opps: List[Dict], profile: Profile, portal_id: str = "") -> List[Dict]:
    """Filter a list of opportunities down to those relevant to the profile.

    Sets '_filter_reason' on rejected opps for raw listing tracking.
    """
    matched = []
    naics_matched = 0
    keyword_matched = 0
    excluded = 0
    rejected = 0

    for opp in opps:
        opp_naics = str(opp.get("naics_code", "")).strip()
        reason = rejection_reason(opp, profile, portal_id=portal_id)
        if not reason:
            matched.append(opp)
            if opp_naics:
                naics_matched += 1
            else:
                keyword_matched += 1
        else:
            opp["_filter_reason"] = reason
            if is_excluded(opp):
                excluded += 1
            else:
                rejected += 1

    keyword_set = "bidnet" if portal_id in BIDNET_PORTAL_IDS else "scrape"
    log.info(
        f"Filter [{portal_id or 'generic'}]: {len(matched)}/{len(opps)} matched "
        f"({naics_matched} by NAICS, {keyword_matched} by {keyword_set} keyword, "
        f"{excluded} excluded by noise filter, {rejected} rejected)"
    )
    return matched
