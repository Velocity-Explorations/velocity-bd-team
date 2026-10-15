"""
Yukon — AI Review Layer
Two-stage review of opportunities before they hit Discord/Sheet:

Stage 1 — Rule-based blocklist (fast, free)
  Eliminates obvious non-starters: hardware repair, medical equipment,
  physical construction, events, admin support, etc.

Stage 2 — LLM review (Claude API)
  Reads each remaining opportunity and reasons about Velocity fit.
  Returns a verdict (yes/no/maybe) + 1-sentence reasoning.
"""

import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Tuple

log = logging.getLogger(__name__)

LLM_REVIEW_TIMEOUT = int(os.environ.get("YUKON_LLM_REVIEW_TIMEOUT", "35"))
LLM_REVIEW_RETRIES = int(os.environ.get("YUKON_LLM_REVIEW_RETRIES", "1"))
LLM_REVIEW_COOLDOWN_SEC = float(os.environ.get("YUKON_LLM_REVIEW_COOLDOWN_SEC", "0.5"))

# ─── STAGE 1: RULE-BASED BLOCKLIST ────────────────────────────────────────────

# Title/description patterns that are NEVER relevant to Velocity
# These indicate hardware, physical services, events, or admin work
BLOCKLIST_PATTERNS = [
    # Hardware / repair / parts
    r"\brepair\b", r"\bin repair\b", r"\bmodification of\b",
    r"\breplacement\b.*\b(part|panel|bolt|valve|seal|bearing|blade|pump|hose|filter|cooler|impeller|fan)\b",
    r"\bnsn\s+\d", r"\b\d{4}-\d{2,}-\d{2,}-\d{2,}\b",  # NSN part numbers
    r"\bparts kit\b", r"\bspare parts\b", r"\brepair kit\b",
    r"\bhose assembly\b", r"\bcable assy\b", r"\bcircuit card\b",
    r"\bgenerator.*unit\b", r"\bimpeller\b", r"\baxial flow\b",
    r"\btailpiece\b", r"\bunion.*coupling\b", r"\bshaft.*shoulder\b",
    r"\bvalve.*swing\b", r"\bseal.*assy\b", r"\bretainer.*seal\b",
    r"\bcontainer.*collaps\b", r"\bslat.*aircraft\b",
    r"\bwindshield panel\b", r"\bchassis electric\b",
    r"\bprojector.*sonar\b", r"\bradio.*upgrade.*hardware\b",

    # Medical / lab equipment (not AI medical coding)
    r"\bscanning.*microscope\b", r"\bosmolality\b", r"\bstrainer.*roche\b",
    r"\bhemochron\b", r"\bventana slide\b", r"\bmedical cart\b",
    r"\banimal care facility\b", r"\bboiler replacement\b",
    r"\bair purif\b", r"\bflooring.*abatement\b",
    r"\bdoor access control\b",

    # Physical construction / facilities
    r"\bconstruction\b.*\b(facility|building|pavement|airfield|runway|taxiway)\b",
    r"\blighting.*improvement\b", r"\bairfield lighting\b",
    r"\bfuel supplier\b", r"\baviation fuel\b",
    r"\bspaceport.*planning.*engineering\b",
    r"\bdredging\b", r"\bharbor.*channel\b",
    r"\bwaste.*water\b", r"\bprocess water\b",

    # Events / industry days / reverse industry days
    r"\bindustry day\b", r"\breverse industry day\b",
    r"\bconference\b.*\bregistration\b",
    r"\bspeaking.*engagement\b",
    r"\bpanel.*discussion\b",

    # Admin / management support (not software/AI)
    r"\bdocument destruction\b", r"\bsensitive document\b",
    r"\binspector general\b.*\bsupport\b",
    r"\bprogram analysis.*administrative\b",
    r"\bstrategic.*operational.*planning.*support\b",
    r"\bfinancial investigation\b",
    r"\bmotor bearing\b", r"\bturning tool\b",
    r"\bshipping.*storage\b",
    r"\bplc training\b", r"\brockwell.*training\b",
    r"\bappraisal service\b",

    # Logistics / supply chain hardware
    r"\bball joint\b", r"\bdrive shaft\b",
]

# Compile all patterns once
_COMPILED_BLOCKLIST = [re.compile(p, re.IGNORECASE) for p in BLOCKLIST_PATTERNS]


def stage1_blocklist(opp: Dict) -> Tuple[bool, str]:
    """
    Stage 1: Rule-based blocklist.
    Returns (passes, reason) — passes=True means keep it, False means drop it.
    """
    search_text = " ".join([
        str(opp.get("title", "")),
        str(opp.get("description", "")),
    ])

    for pattern in _COMPILED_BLOCKLIST:
        if pattern.search(search_text):
            return False, f"Blocklist match: {pattern.pattern}"

    return True, ""


# ─── STAGE 2: LLM REVIEW ──────────────────────────────────────────────────────

VELOCITY_CONTEXT = """
Velocity Explorations is a small defense technology company focused on:
- Software development and AI/ML development for DoD and government
- Legacy system modernization (COBOL, AS/400, mainframe → modern web/cloud)
- Command and control (C2) systems — Echo C2 AI is their flagship product
- Natural language processing, transcription, translation for operational environments
- Computer vision, autonomous systems software
- DevSecOps, cloud migration, data analytics platforms
- SBIR/STTR contracts and OTA agreements

Velocity IS a registered member of:
- S2MARTS OTA consortium (NSTXL) — can submit to S2MARTS opportunities
- SpEC OTA consortium (NSTXL) — can submit to Space Enterprise Consortium opportunities
- These are free OTA vehicles managed by NSTXL for DoD prototype development

Velocity does NOT do:
- Hardware development or manufacturing
- Physical construction or facilities work
- IT management or administrative support services
- Medical devices or healthcare equipment
- Training/education services
- Events or conference participation
- Logistics, supply chain, or parts procurement
- Financial software unrelated to defense

A good opportunity for Velocity involves: building software, developing AI/ML models,
modernizing legacy systems, creating C2 tools, or conducting R&D in AI/autonomy/NLP.
"""


def get_rag_context(opp: Dict, n_results: int = 4) -> str:
    """Query ChromaDB for similar past Velocity pursuits."""
    try:
        import chromadb
        import requests as _req

        # Build query text from opp
        query = f"{opp.get('title', '')} {opp.get('description', '')} {opp.get('type', '')} {opp.get('department', '')}"
        query = query.strip()[:500]

        # Embed the query via Ollama
        resp = _req.post("http://localhost:11434/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": query}, timeout=15)
        if resp.status_code != 200:
            return ""
        query_emb = resp.json().get("embedding", [])
        if not query_emb:
            return ""

        client = chromadb.PersistentClient(path=str(Path(__file__).parent.parent / "data" / "chroma"))

        context_parts: List[str] = []

        # Search bd_activities (BD history)
        try:
            acts = client.get_collection("bd_activities")
            r1 = acts.query(query_embeddings=[query_emb], n_results=n_results)
            if r1["documents"][0]:
                context_parts.append("## Similar past Velocity BD pursuits:")
                for doc, meta in zip(r1["documents"][0], r1["metadatas"][0]):
                    status = meta.get("status", "")
                    title = meta.get("title", "")[:80]
                    context_parts.append(f"- [{status}] {title}")
        except Exception:
            pass

        # Search bd_documents (proposals/one-pagers)
        try:
            docs_col = client.get_collection("bd_documents")
            r2 = docs_col.query(query_embeddings=[query_emb], n_results=3)
            if r2["documents"][0]:
                context_parts.append("\n## Relevant past Velocity documents:")
                seen_files: set = set()
                for doc, meta in zip(r2["documents"][0], r2["metadatas"][0]):
                    fname = meta.get("filename", "")
                    if fname not in seen_files:
                        seen_files.add(fname)
                        doc_type = meta.get("doc_type", "")
                        context_parts.append(f"- [{doc_type}] {fname}")
                        snippet = doc[:200].replace("\n", " ").strip()
                        if snippet:
                            context_parts.append(f"  > {snippet}")
        except Exception:
            pass

        return "\n".join(context_parts) if context_parts else ""

    except Exception as e:
        log.debug(f"RAG context retrieval failed: {e}")
        return ""


def _build_profile_context(profile_name: str) -> str:
    """Build company context from profile config instead of hardcoded Velocity context."""
    if profile_name == "velocity":
        return VELOCITY_CONTEXT

    try:
        from scanner.profile import load_profile
        profile = load_profile(profile_name)
        raw = {}
        config_path = Path(__file__).parent.parent / "configs" / profile_name / "profile.yaml"
        if config_path.exists():
            import yaml
            with open(config_path) as f:
                raw = yaml.safe_load(f) or {}

        company = raw.get("company_meta", {})
        name = company.get("legal_name") or profile.name
        desc = company.get("company_description", "")
        naics_display = company.get("naics_display", ", ".join(profile.naics))
        keywords = ", ".join(profile.keywords[:15])

        return f"""
{name} is {desc}.

Core NAICS codes: {naics_display}
Key capability areas: {keywords}

A good opportunity for {profile.name} involves work directly related to their capability areas.
Opportunities outside their domain should be marked "no".
"""
    except Exception as e:
        log.warning(f"Failed to build profile context for {profile_name}: {e}")
        return VELOCITY_CONTEXT


def stage2_llm_review(opps: List[Dict], profile_name: str = "velocity") -> List[Dict]:
    """
    Stage 2: LLM review of each opportunity.
    Calls Claude to evaluate fit for the given profile.
    Returns opps with 'ai_verdict' (yes/no/maybe) and 'ai_reasoning' added.
    Only opps marked yes/maybe are kept.
    """
    try:
        import anthropic
    except ImportError:
        log.warning("anthropic package not installed — skipping LLM review")
        for opp in opps:
            opp["ai_verdict"] = "maybe"
            opp["ai_reasoning"] = "LLM review skipped"
        return opps

    api_key = os.environ.get("ANTHROPIC_API_KEY") or _load_anthropic_key()

    company_context = _build_profile_context(profile_name)

    from scanner.feedback_examples import get_feedback_block
    feedback_block = get_feedback_block(profile_name)
    feedback_section = f"\n\n{feedback_block}\n" if feedback_block else ""

    reviewed = []

    for idx, opp in enumerate(opps, start=1):
        title = opp.get("title", "")
        portal = opp.get("portal", "")
        opp_type = opp.get("type", "")
        naics = opp.get("naics_code", "")
        agency = opp.get("department", "")
        description = opp.get("description", "")[:500]
        attachment_text = opp.get("attachment_text", "")
        if attachment_text:
            description = f"{description}\n\nATTACHMENT CONTENT:\n{attachment_text[:2000]}"

        rag_context = get_rag_context(opp)
        rag_block = f"\n\n--- PAST EXPERIENCE ---\n{rag_context}\n---\n" if rag_context else ""

        prompt = f"""{company_context}{rag_block}{feedback_section}
Evaluate this government opportunity for {profile_name}:

Title: {title}
Portal: {portal}
Type: {opp_type}
NAICS: {naics}
Agency: {agency}
Description: {description}

Respond with exactly this format (no other text):
VERDICT: yes|no|maybe
REASON: [one sentence explaining why]

Use "yes" if clearly relevant, "no" if clearly not, "maybe" if uncertain.
If past experience shows similar work has been pursued, weight that positively."""

        log.info(f"LLM review {idx}/{len(opps)}: {title[:60]}")
        verdict = None
        reason = None

        for attempt in range(LLM_REVIEW_RETRIES + 1):
            try:
                import subprocess as _sp
                _result = _sp.run(
                    ["openclaw", "agent", "--message", prompt, "--agent", "main", "--json"],
                    capture_output=True, text=True, timeout=LLM_REVIEW_TIMEOUT
                )
                if _result.returncode != 0:
                    raise RuntimeError(f"openclaw agent failed: {_result.stderr[:200]}")
                import json as _json
                _data = _json.loads(_result.stdout)
                _payloads = _data.get("result", {}).get("payloads", [])
                response = _payloads[0].get("text", "").strip() if _payloads else ""
                if not response:
                    raise RuntimeError("Empty response from openclaw agent")

                verdict = "maybe"
                reason = "Could not parse LLM response"

                for line in response.split("\n"):
                    if line.startswith("VERDICT:"):
                        v = line.replace("VERDICT:", "").strip().lower()
                        if v in ("yes", "no", "maybe"):
                            verdict = v
                    elif line.startswith("REASON:"):
                        reason = line.replace("REASON:", "").strip()
                break

            except Exception as e:
                if attempt < LLM_REVIEW_RETRIES:
                    log.warning(
                        f"LLM review retry {attempt + 1}/{LLM_REVIEW_RETRIES} for '{title[:40]}' after error: {e}"
                    )
                    time.sleep(1)
                    continue
                log.error(f"LLM review error for '{title[:40]}': {e}")
                verdict = "maybe"
                reason = f"Review error: {str(e)[:80]}"

        opp["ai_verdict"] = verdict or "maybe"
        opp["ai_reasoning"] = reason or "LLM review fallback"
        log.info(f"AI review [{opp['ai_verdict']}]: {title[:60]}")

        if opp["ai_verdict"] == "no":
            log.info(f"  → Dropped: {opp['ai_reasoning']}")
        else:
            reviewed.append(opp)

        if idx < len(opps):
            time.sleep(LLM_REVIEW_COOLDOWN_SEC)

    log.info(f"LLM review: {len(reviewed)}/{len(opps)} passed")
    return reviewed


def _load_anthropic_key() -> str:
    from pathlib import Path
    env_path = Path(__file__).parent.parent / "configs" / "velocity" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            for prefix in ("ANTHROPIC_API_KEY=", "ANTHROPIC_TOKEN_MANUAL="):
                if line.startswith(prefix):
                    return line.split("=", 1)[1].strip()
    return ""


def review_opportunities(opps: List[Dict], use_llm: bool = True,
                         profile: str = "velocity") -> List[Dict]:
    """
    Full two-stage review pipeline.
    Returns only opportunities that pass both stages.
    """
    if not opps:
        return []

    # Stage 1: blocklist
    stage1_passed = []
    stage1_dropped = 0
    for opp in opps:
        passes, reason = stage1_blocklist(opp)
        if passes:
            stage1_passed.append(opp)
        else:
            stage1_dropped += 1
            log.debug(f"Stage1 drop: {opp.get('title','?')[:50]} — {reason}")

    log.info(f"Stage 1 (blocklist): {len(stage1_passed)} passed, {stage1_dropped} dropped")

    if not stage1_passed:
        return []

    # Stage 2: LLM review
    if use_llm:
        final = stage2_llm_review(stage1_passed, profile_name=profile)
    else:
        final = stage1_passed
        for opp in final:
            opp["ai_verdict"] = "maybe"
            opp["ai_reasoning"] = "LLM review disabled"

    log.info(f"Stage 2 (LLM): {len(final)} passed total review")
    return final
