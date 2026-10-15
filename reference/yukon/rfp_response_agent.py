#!/usr/bin/env python3
"""
Yukon — RFP Response Agent

Automated first-pass proposal drafting for BD opportunities. Triggered after
a thumbs-up in #bd-prospector creates a Google Drive folder.

Phases:
  1. Scrape listing page
  2. Download & extract attachments
  3. Extract structured requirements via Claude
  4. Retrieve RAG context from past submissions
  5. Draft response using matched template
  6. Deliver outputs to Google Drive + Slack

Usage:
  python scripts/rfp_response_agent.py \
    --opp-json '{"title":"...", "portal":"SAM.gov", "url":"...", ...}' \
    --drive-folder-id FOLDER_ID \
    --slack-channel C0AN8AMM4AW \
    --slack-thread 1234567890.123456
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import yaml
from dotenv import load_dotenv

# Profile-aware config — set from CLI args in main(), defaults to velocity
_PROFILE_NAME = "velocity"

def _load_profile_config():
    profile_path = BASE_DIR / "configs" / _PROFILE_NAME / "profile.yaml"
    if profile_path.exists():
        with open(profile_path) as f:
            return yaml.safe_load(f)
    return {}

load_dotenv(BASE_DIR / "configs" / "velocity" / ".env")

from scanner.rfp_attachments import (
    download_attachments,
    download_all_sam_attachments,
    extract_text,
    load_cached_attachments,
    scrape_listing_page,
    _extract_sam_notice_id,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / "logs" / "rfp-agent.log", mode="a"),
    ]
)
log = logging.getLogger(__name__)

TEMPLATES_DIR = BASE_DIR / "data" / "templates"
CHROMA_PATH = str(BASE_DIR / "data" / "chroma")
OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"

# Mutable globals — set from profile config in main()
SECRETS_DIR = BASE_DIR / "configs" / "velocity"
DRIVE_ACCOUNT = "david@velocityexplorations.com"
_COMPANY_CTX: dict = {
    "company_name": "Velocity Explorations",
    "legal_name": "Velocity Explorations, Inc.",
    "short_name": "Velocity Explorations",
    "cage": "9KCQ5",
    "uei": "HFEDQFZUJSZ6",
    "duns": "11-909-2408",
    "business_size": "Small Business (WOSB)",
    "poc_name": "Alec Leeseberg",
    "poc_title": "President",
    "poc_email": "alec@velocityexplorations.com",
    "poc_phone": "(888) 780-1888",
    "naics_display": "541511, 541512, 541715",
    "company_description": "a small defense technology company specializing in AI/ML, command & control (Echo C2), and software modernization",
}

# Draft run progress reporting
_DRAFT_RUN_ID: int | None = None
_API_URL: str = ""

def report_progress(phase: str, status: str, message: str = "",
                    drive_links: dict | None = None):
    if not _DRAFT_RUN_ID or not _API_URL:
        return
    try:
        token = os.environ.get("SCANNER_API_TOKEN", "")
        payload: dict = {"phase": phase, "status": status, "message": message}
        if drive_links:
            payload["driveLinks"] = drive_links
        requests.post(
            f"{_API_URL}/api/draft-runs/{_DRAFT_RUN_ID}/progress",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )
    except Exception as e:
        log.warning(f"Progress report failed: {e}")

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

# Fallback: infer type from title keywords when parsed type doesn't match TEMPLATE_MAP
TITLE_TYPE_HINTS = [
    (r"\bbaa\b|broad\s+agency\s+announcement", "BAA"),
    (r"\bsbir\b|\bsttr\b", "SBIR/STTR"),
    (r"\bota\b|other\s+transaction", "OTA"),
    (r"\bs2marts\b", "S2MARTS OTA"),
    (r"\bcso\b|commercial\s+solutions?\s+opening", "Commercial Solutions Opening"),
    (r"\brfi\b|request\s+for\s+information", "RFI"),
    (r"\bsources?\s+sought\b", "Sources Sought"),
]


def _resolve_opp_type(opp: dict) -> str:
    """Resolve the opp type, falling back to title-based inference."""
    opp_type = opp.get("type", "")
    if opp_type in TEMPLATE_MAP:
        return opp_type
    title = opp.get("title", "")
    for pattern, inferred_type in TITLE_TYPE_HINTS:
        if re.search(pattern, title, re.IGNORECASE):
            log.info(f"Inferred opp type '{inferred_type}' from title (parsed type was '{opp_type[:50]}')")
            return inferred_type
    return opp_type


# ─── SLACK HELPERS ─────────────────────────────────────────────────────────────

def _load_bot_token() -> str:
    token_file = SECRETS_DIR / "slack_tokens.json"
    if token_file.exists():
        data = json.loads(token_file.read_text())
        return data.get("SLACK_YUKON_BOT_TOKEN", data.get("SLACK_BOT_TOKEN", ""))
    return ""


def slack_reply(channel: str, thread_ts: str, text: str):
    if not channel or not thread_ts:
        log.info(f"[no-slack] {text}")
        return
    token = _load_bot_token()
    if not token:
        log.warning("No Slack bot token, skipping reply")
        return
    try:
        requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"channel": channel, "thread_ts": thread_ts, "text": text},
            timeout=10
        )
    except Exception as e:
        log.warning(f"Slack reply error: {e}")


# ─── CLAUDE CLI ────────────────────────────────────────────────────────────────

CLAUDE_MAX_TIMEOUT = 1800  # 30-minute safety net
CLAUDE_KEEPALIVE_INTERVAL = 60  # log/Slack keepalive every 60s
CLAUDE_MAX_RETRIES = 3

def _claude_generate(prompt: str, system_prompt: str = "",
                     phase_label: str = "", channel: str = "", thread_ts: str = "") -> str:
    """Call Claude via the claude -p CLI (uses Claude Code's auth).
    Polls the process with keepalive messages instead of a hard timeout.
    Retries up to CLAUDE_MAX_RETRIES times on empty output."""
    full_prompt = f"{system_prompt}\n\n---\n\n{prompt}" if system_prompt else prompt
    log.info(f"claude -p: prompt length={len(full_prompt)} chars (~{len(full_prompt)//4} tokens)")
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDECODE", "AI_AGENT", "ANTHROPIC_API_KEY")
           and not k.startswith("CLAUDE_CODE_")}

    label = phase_label or "generating"

    for attempt in range(1, CLAUDE_MAX_RETRIES + 1):
        try:
            proc = subprocess.Popen(
                ["/opt/homebrew/bin/claude", "-p", "--model", "claude-sonnet-4-6"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, env=env,
            )
            proc.stdin.write(full_prompt)
            proc.stdin.close()

            elapsed = 0
            while proc.poll() is None:
                time.sleep(CLAUDE_KEEPALIVE_INTERVAL)
                elapsed += CLAUDE_KEEPALIVE_INTERVAL
                minutes = elapsed // 60
                log.info(f"claude -p: still {label}... ({minutes}m elapsed)")
                if channel and thread_ts:
                    slack_reply(channel, thread_ts,
                               f"⏳ Still {label}... ({minutes}m elapsed)")
                if elapsed >= CLAUDE_MAX_TIMEOUT:
                    proc.kill()
                    proc.wait()
                    raise subprocess.TimeoutExpired(cmd="claude -p", timeout=CLAUDE_MAX_TIMEOUT)

            stdout = proc.stdout.read()
            stderr = proc.stderr.read()

            if proc.returncode != 0:
                log.error(f"claude -p stderr: {stderr[:1000]}")
                log.error(f"claude -p stdout: {stdout[:500]}")
                raise RuntimeError(f"claude -p failed (rc={proc.returncode}): {stderr[:500]}")
            output = stdout.strip()
            if output:
                return output
            log.warning(f"claude -p returned empty output (attempt {attempt}/{CLAUDE_MAX_RETRIES}). stderr: {stderr[:300]}")
            if attempt < CLAUDE_MAX_RETRIES:
                time.sleep(2)
        except subprocess.TimeoutExpired:
            log.warning(f"claude -p hit {CLAUDE_MAX_TIMEOUT}s safety limit (attempt {attempt}/{CLAUDE_MAX_RETRIES})")
            if attempt >= CLAUDE_MAX_RETRIES:
                raise RuntimeError(f"claude -p exceeded {CLAUDE_MAX_TIMEOUT}s safety limit ({CLAUDE_MAX_RETRIES} attempts)")
            time.sleep(2)
        except FileNotFoundError:
            raise RuntimeError("claude CLI not found — is Claude Code installed?")

    log.error(f"claude -p returned empty output after {CLAUDE_MAX_RETRIES} attempts")
    return ""


def _load_knowledge_base() -> str:
    kb_dir = BASE_DIR / "configs" / _PROFILE_NAME / "knowledge-base"
    parts = []
    if not kb_dir.exists():
        return ""
    for md in sorted(kb_dir.glob("*.md")):
        content = md.read_text().strip()
        if content:
            parts.append(f"## {md.stem.replace('_', ' ').title()}\n\n{content}")
    return "\n\n---\n\n".join(parts)


def _apply_company_ctx(text: str) -> str:
    """Substitute {company_meta} variables in template text, ignoring unknown keys."""
    from collections import defaultdict
    safe_ctx = defaultdict(lambda: "", _COMPANY_CTX)
    try:
        return text.format_map(safe_ctx)
    except (KeyError, ValueError):
        return text


def _load_template(opp_type: str) -> tuple[str, str, bool]:
    """Returns (template_name, template_content, is_fallback)."""
    if opp_type in TEMPLATE_MAP:
        template_name = TEMPLATE_MAP[opp_type]
        template_path = TEMPLATES_DIR / f"{template_name}.md"
        if template_path.exists():
            return template_name, _apply_company_ctx(template_path.read_text()), False

    # Fallback — record the unmapped type
    if opp_type:
        _record_unmapped_type(opp_type)

    fallback = TEMPLATES_DIR / "full_proposal.md"
    if fallback.exists():
        return "full_proposal", _apply_company_ctx(fallback.read_text()), True
    return "full_proposal", "", True


def _record_unmapped_type(opp_type: str):
    """Append unmapped opp types to a log file so new templates can be created."""
    log_path = TEMPLATES_DIR / "unmapped_types.log"
    existing = set()
    if log_path.exists():
        existing = {line.split("|")[0].strip() for line in log_path.read_text().splitlines() if line.strip()}
    if opp_type not in existing:
        with open(log_path, "a") as f:
            f.write(f"{opp_type} | {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        log.info(f"Recorded unmapped opp type: {opp_type}")


# ─── RAG ───────────────────────────────────────────────────────────────────────

def _embed(text: str) -> list[float] | None:
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": EMBED_MODEL, "prompt": text[:2000]},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get("embedding")
    except Exception as e:
        log.warning(f"Embedding error: {e}")
    return None


def _query_chroma(query_text: str, n_results: int = 5) -> list[dict]:
    emb = _embed(query_text)
    if not emb:
        return []
    try:
        import chromadb
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        col = client.get_collection("bd_documents")
        results = col.query(query_embeddings=[emb], n_results=n_results)
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        return [
            {"text": doc, "source": meta.get("source", ""), "doc_type": meta.get("doc_type", "")}
            for doc, meta in zip(docs, metas)
        ]
    except Exception as e:
        log.warning(f"ChromaDB query error: {e}")
        return []


# ─── PHASE 1: SCRAPE LISTING PAGE ─────────────────────────────────────────────

def phase_scrape_listing(opp: dict, channel: str, thread_ts: str) -> str:
    slack_reply(channel, thread_ts, "🔍 _Reviewing listing page..._")
    report_progress("scrape", "running", "Reviewing listing page...")
    url = opp.get("url", "")
    if not url:
        fallback = opp.get("description", "")
        if not fallback and len(opp.get("type", "")) > 100:
            fallback = opp["type"]
            log.info("No URL or description — using type field as listing text (long type detected)")
        else:
            log.warning("No URL provided, using description as listing text")
        return fallback

    listing_text = scrape_listing_page(url)
    if listing_text:
        log.info(f"Phase 1: Scraped {len(listing_text)} chars from listing page")
        report_progress("scrape", "complete", f"Listing page scraped ({len(listing_text)} chars)")
    else:
        log.warning("Phase 1: Could not scrape listing page, falling back to description")
        listing_text = opp.get("description", "")
        report_progress("scrape", "complete", "Using description as listing text")

    return listing_text


# ─── PHASE 2: DOWNLOAD ATTACHMENTS ────────────────────────────────────────────

def phase_download_attachments(opp: dict, opp_dir: Path, drive_folder_id: str,
                                channel: str, thread_ts: str) -> list[dict]:
    slack_reply(channel, thread_ts, "📎 _Loading solicitation documents..._")
    report_progress("attachments", "running", "Loading solicitation documents...")
    url = opp.get("url", "")
    portal = opp.get("portal", "")
    attachments = []

    # Step 1: Check local cache (nightly scanner or prior valid-marking download)
    if url and "sam.gov" in url.lower():
        notice_id = _extract_sam_notice_id(url)
        if notice_id:
            attachments = load_cached_attachments(notice_id, drive_folder_id)
            if attachments:
                log.info(f"Phase 2: Loaded {len(attachments)} cached attachments for {notice_id}")

    # Step 2: If no cache, try downloading with dedicated key
    if not attachments and url and "sam.gov" in url.lower():
        log.info("Phase 2: No cache found, downloading with dedicated key...")
        attachments = download_all_sam_attachments(url)
        for att in attachments:
            if drive_folder_id and not att.get("drive_link"):
                from scanner.rfp_attachments import _upload_to_drive
                att["drive_link"] = _upload_to_drive(Path(att["local_path"]), drive_folder_id)

    # Step 3: Fall back to original download logic
    if not attachments:
        att_dir = opp_dir / "attachments"
        attachments = download_attachments(portal, url, att_dir, drive_folder_id)

    if attachments:
        with_text = [a for a in attachments if a.get("text")]
        names = [a["name"] for a in with_text]
        msg = f"Loaded {len(attachments)} document(s) ({len(with_text)} with extractable text): {', '.join(names[:5])}"
        slack_reply(channel, thread_ts, f"📎 {msg}")
        report_progress("attachments", "complete", msg)
        log.info(f"Phase 2: {len(attachments)} attachments, "
                 f"{len(with_text)} with extractable text")
    else:
        slack_reply(channel, thread_ts, "📎 No solicitation documents found — proceeding with listing text only.")
        report_progress("attachments", "complete", "No solicitation documents found")
        log.info("Phase 2: No attachments found")

    return attachments


# ─── PHASE 3: EXTRACT REQUIREMENTS ────────────────────────────────────────────

REQUIREMENTS_SYSTEM_PROMPT = """You are a senior BD analyst at {company_name}. Your job is to produce a requirements analysis that helps the BD team decide how to pursue an opportunity and prepare a winning response.

ABOUT {company_name_upper}:
{knowledge_base}

RELEVANT PAST SUBMISSIONS (for context on what {company_name} has done before):
{rag_context}

Your analysis must be thorough, strategic, and actionable. Adapt the output format to the opportunity type — an active RFP with concrete requirements deserves a compliance matrix; a framework/umbrella announcement deserves a strategic readiness document. Match the format to what's most useful.

CRITICAL: Output ONLY the analysis document. Do NOT include any preamble, commentary, thinking, or meta-discussion. Start directly with the document heading."""

REQUIREMENTS_USER_PROMPT = """Produce a requirements analysis for the following government solicitation.

OPPORTUNITY:
- Title: {title}
- Agency: {agency}
- Portal: {portal}
- Type: {opp_type}
- Due Date: {due_date}

Your analysis should cover:

## 1. OPPORTUNITY ASSESSMENT
- What type of solicitation is this? (active RFP/BAA/CSO, umbrella/framework/MAA, RFI/sources sought, etc.)
- Is this requesting proposals now, or is it a future pipeline vehicle to monitor?
- Key dates, deadlines, and submission mechanics
- Award type and contract vehicle (FAR, OTA, grant, cooperative agreement, etc.)

## 2. REQUIREMENTS ANALYSIS
- For active solicitations: structured requirements with IDs, categories, mandatory vs. desirable, evaluation criteria
- For framework/umbrella announcements: what's known now vs. what will be defined in future individual solicitations
- Technical areas, scope, and performance requirements
- Compliance requirements (security clearances, CMMC, accounting systems, export control, DD254, etc.)

## 3. SUBMISSION FORMAT & DOCUMENT REQUIREMENTS
This section is critical — non-compliance with format requirements can disqualify a submission. Extract ALL of the following:
- **Mandatory templates**: Does the solicitation provide a template or form that MUST be used? If so, identify the specific attachment filename.
- **Volume structure**: How must the response be organized? (e.g., separate technical, management, cost volumes)
- **Page limits**: Maximum pages per volume or total. Include what counts toward page limits.
- **Font/spacing/margin requirements**: Font type and size, line spacing, margin sizes
- **File format**: Required submission format (PDF, Word, etc.) and naming conventions
- **Submission method**: Portal upload, email, physical delivery, etc.
- **Evaluation criteria weighting**: How will proposals be scored? (e.g., Technical 60%, Cost 30%, Past Performance 10%)
- If no specific format requirements are stated, explicitly note "No mandatory format requirements identified."

## 4. FIT ASSESSMENT
- Which requirements or technical areas align with {company_name}'s capabilities?
- Which past programs are most relevant and why?
- Gaps or risks in {company_name}'s ability to respond
- Recommended role: prime, sub, or teaming partner
- Strength of fit: strong / moderate / weak

## 5. RECOMMENDED NEXT STEPS
- If active solicitation: key actions to prepare the response, critical path items
- If framework/umbrella: what to prepare now, what to monitor for
- Bid/no-bid considerations and recommendation
- Internal readiness checklist (admin, technical, cost, compliance)

## 6. SOLICITATION TERMINOLOGY & KEYWORDS — SOURCE OF TRUTH

This section is critical — it will be used to verify the draft for compliance. Extract the following from the solicitation, using the EXACT text from the solicitation (never paraphrase, never invent expansions):

### Exact Keywords
List every keyword from the solicitation's KEYWORDS field verbatim. Include a usage note for each.

### Required Function Names
List the exact terms the solicitation uses for what the system/solution must do. These function names must appear in the draft exactly as written — not synonyms or substitutes.

### Named Technologies and Interfaces
List any specific technologies, protocols, standards, or interfaces the solicitation names.

### Performance Thresholds
List every quantitative requirement with the solicitation's exact notation (e.g., '>=8 PB' not '8 PB', '>400 GB/s' not '400 GB/s'). Getting the operator wrong (dropping a > or >=) is an evaluation penalty.

### Reference Number Mapping
Map any reference numbers (Ref 1, Ref 2, etc.) to their full document titles as cited in the solicitation.

### Security & Compliance Citations
List every regulation, certification, clearance level, or compliance requirement with its exact citation (e.g., '22 CFR Parts 120-130' not just 'ITAR').

### Phase Scope Markers
Identify what the solicitation assigns to each phase (Phase I Base, Phase I Option, Phase II, etc.). Note specific deliverables, activities, and scope boundaries for each. This prevents Phase II scope from creeping into Phase I drafts.

Accuracy in this section is more important than completeness in the rest of the document. Every item here will be checked against the final draft word-for-word.

---

LISTING PAGE TEXT:
{listing_text}

---

SOLICITATION DOCUMENTS:
{attachment_text}"""


def phase_extract_requirements(listing_text: str, attachments: list[dict],
                                opp: dict, opp_dir: Path,
                                channel: str, thread_ts: str,
                                knowledge_base: str = "",
                                rag_context: str = "") -> str:
    slack_reply(channel, thread_ts, "📋 _Analyzing solicitation requirements..._")
    report_progress("requirements", "running", "Analyzing solicitation requirements...")

    attachment_text = "\n\n---\n\n".join(
        f"[{a['name']}]\n{a['text']}" for a in attachments if a.get("text")
    )

    if not listing_text and not attachment_text:
        log.warning("Phase 4: No text to extract requirements from")
        return ""

    combined_text = f"{listing_text}\n\n{attachment_text}".strip()
    total_chars = len(combined_text)
    log.info(f"Phase 4: {total_chars} chars of source text for requirements extraction")

    if total_chars > 600_000:
        log.info("Phase 4: Large document — truncating to 600K chars")

    try:
        system_prompt = REQUIREMENTS_SYSTEM_PROMPT.format(
            knowledge_base=knowledge_base if knowledge_base else "(No knowledge base loaded)",
            rag_context=rag_context[:20_000] if rag_context else "(No past submissions found)",
            company_name_upper=_COMPANY_CTX["company_name"].upper(),
            **_COMPANY_CTX,
        )

        user_prompt = REQUIREMENTS_USER_PROMPT.format(
            title=opp.get("title", ""),
            agency=opp.get("agency", ""),
            portal=opp.get("portal", ""),
            opp_type=opp.get("type", ""),
            due_date=opp.get("due", ""),
            listing_text=listing_text[:80_000] if listing_text else "(not available)",
            attachment_text=attachment_text[:80_000] if attachment_text else "(no solicitation documents available)",
            **_COMPANY_CTX,
        )

        requirements_md = _claude_generate(user_prompt, system_prompt,
                                           phase_label="analyzing requirements", channel=channel, thread_ts=thread_ts)

        req_path = opp_dir / "requirements.md"
        req_path.write_text(requirements_md)
        log.info(f"Phase 4: Requirements saved to {req_path}")

        word_count = len(requirements_md.split())
        slack_reply(channel, thread_ts,
                    f"📋 Requirements analysis complete ({word_count} words)")
        report_progress("requirements", "complete", f"Requirements analysis complete ({word_count} words)")

        return requirements_md
    except Exception as e:
        log.error(f"Phase 4 error: {e}")
        slack_reply(channel, thread_ts, f"⚠️ Requirements extraction failed: {e}")
        report_progress("requirements", "error", str(e))
        return ""


# ─── PHASE 4: RAG CONTEXT RETRIEVAL ───────────────────────────────────────────

def phase_rag_retrieval(listing_text: str, opp: dict) -> str:
    query = f"{opp.get('title', '')} {opp.get('description', '')} {opp.get('type', '')}"
    if listing_text:
        query = f"{query}\n{listing_text[:2000]}"

    rag_results = _query_chroma(query, n_results=8)
    if not rag_results:
        log.info("Phase 3: No RAG results found")
        return ""

    log.info(f"Phase 3: Retrieved {len(rag_results)} relevant chunks from past submissions")

    parts = []
    for i, r in enumerate(rag_results, 1):
        source = r.get("source", "unknown")
        doc_type = r.get("doc_type", "")
        parts.append(f"### Past Submission {i} ({doc_type} — {source})\n{r['text']}")

    return "\n\n---\n\n".join(parts)


# ─── PHASE 4.5: ALIGNMENT ASSESSMENT ────────────────────────────────────────

ALIGNMENT_SYSTEM_PROMPT = """You are a capture strategist at {company_name}. Your job is to assess how well {company_name}'s capabilities align with a specific government opportunity BEFORE outlining or drafting begins.

You are not writing the proposal. You are creating a strategic assessment that tells the outline and draft phases:
- Where {company_name} is strong (and what evidence to lead with)
- Where {company_name} is weak (and what mitigation strategies to use)
- Which past performance is most relevant and why
- What the evaluator is really looking for

{company_name_upper} CONTEXT:
{knowledge_base}

RELEVANT PAST SUBMISSIONS:
{rag_context}

CRITICAL: Output ONLY the alignment assessment document. Do NOT include any preamble, commentary, or meta-discussion."""

ALIGNMENT_USER_PROMPT = """Assess {company_name}'s alignment to the following opportunity. Be honest about gaps — the goal is to produce a stronger proposal, not to pretend we're a perfect fit.

OPPORTUNITY:
- Title: {title}
- Agency: {agency}
- Portal: {portal}
- Type: {opp_type}
- Due Date: {due_date}

REQUIREMENTS ANALYSIS:
{requirements}

---

Produce an alignment assessment with these sections:

## 1. OVERALL FIT RATING
Rate as Strong Fit / Moderate Fit / Stretch Fit / Poor Fit with a 2-3 sentence justification.

## 2. STRENGTH MAP
For each major requirement area where {company_name} has strong, demonstrable capability:
- **Requirement area**: What the solicitation asks for
- **{company_name} capability**: Specific capability that addresses it
- **Best evidence**: The strongest proof point (past contract, metric, deliverable)
- **Draft guidance**: How the proposal should present this (lead with evidence, cite specific contract, quantify impact)

## 3. GAP MAP
For each major requirement area where {company_name} is weak or has no direct experience:
- **Requirement area**: What the solicitation asks for
- **Gap severity**: Critical / Moderate / Minor
- **Mitigation strategy**: One of:
  - **Adjacent experience**: Similar work that demonstrates transferable capability
  - **Teaming**: Recommend a subcontractor or teaming partner type
  - **Rapid capability**: Training, certification, or hiring plan
  - **Reframe**: How to position existing capability as responsive
- **Draft guidance**: How the proposal should handle this section

## 4. PAST PERFORMANCE RANKING
Rank the most relevant past performance references from the knowledge base and RAG context:
1. **[Contract/Project Name]** — Relevance score (High/Medium/Low), which requirements it best supports, key metrics to cite
2. ...

## 5. EVALUATOR LENS
Based on the evaluation criteria (if stated in requirements) or standard government evaluation factors:
- What is the evaluator most likely weighting highest?
- What discriminators will separate winners from losers?
- What are the "table stakes" items that must be present but won't differentiate?
- Recommended win themes (2-3 max) that play to {company_name}'s strengths

## 6. STRATEGIC RECOMMENDATIONS
- Top 3 things this proposal MUST get right to be competitive
- Top 3 risks to address proactively
- Any compliance or eligibility concerns (set-asides, clearances, certifications)"""


def phase_alignment_assessment(requirements_md: str, opp: dict, opp_dir: Path,
                                knowledge_base: str, rag_context: str,
                                channel: str, thread_ts: str) -> str:
    slack_reply(channel, thread_ts, "🎯 _Assessing alignment to {company_name} capabilities..._".format(**_COMPANY_CTX))
    report_progress("alignment", "running", "Assessing alignment to capabilities...")

    opp_type = _resolve_opp_type(opp)

    try:
        system_prompt = ALIGNMENT_SYSTEM_PROMPT.format(
            knowledge_base=knowledge_base if knowledge_base else "(No knowledge base loaded)",
            rag_context=rag_context[:20_000] if rag_context else "(No past submissions found)",
            company_name_upper=_COMPANY_CTX["company_name"].upper(),
            **_COMPANY_CTX,
        )

        user_prompt = ALIGNMENT_USER_PROMPT.format(
            title=opp.get("title", ""),
            agency=opp.get("agency", ""),
            portal=opp.get("portal", ""),
            opp_type=opp_type,
            due_date=opp.get("due", ""),
            requirements=requirements_md[:30_000] if requirements_md else "(Requirements not available)",
            **_COMPANY_CTX,
        )

        alignment_md = _claude_generate(user_prompt, system_prompt,
                                        phase_label="assessing alignment", channel=channel, thread_ts=thread_ts)

        alignment_path = opp_dir / "alignment.md"
        alignment_path.write_text(alignment_md)
        log.info(f"Phase 4.5: Alignment assessment saved to {alignment_path}")

        word_count = len(alignment_md.split())
        slack_reply(channel, thread_ts,
                    f"🎯 Alignment assessment complete ({word_count} words)")
        report_progress("alignment", "complete", f"Alignment assessment complete ({word_count} words)")

        return alignment_md
    except Exception as e:
        log.error(f"Phase 4.5 (alignment) error: {e}")
        slack_reply(channel, thread_ts, f"⚠️ Alignment assessment failed: {e}")
        report_progress("alignment", "error", str(e))
        return ""


# ─── PHASE 5: PROPOSAL OUTLINE & COMPLIANCE PLAN ────────────────────────────

OUTLINE_SYSTEM_PROMPT = """You are a capture manager and proposal strategist at {company_name}. Your job is to create a structured proposal outline that a writing team can follow section-by-section.

You are NOT writing the proposal. You are creating the brief that tells writers:
- Which requirements to address in each section
- Which past performance to cite and why
- Which win themes to emphasize
- What gaps exist that need human input

{company_name_upper} CONTEXT:
{knowledge_base}

RELEVANT PAST SUBMISSIONS:
{rag_context}

CRITICAL: Output ONLY the outline document. Do NOT include any preamble, commentary, or meta-discussion."""

OUTLINE_USER_PROMPT = """Create a proposal outline and compliance plan for the following opportunity.

OPPORTUNITY:
- Title: {title}
- Agency: {agency}
- Portal: {portal}
- Type: {opp_type}
- Due Date: {due_date}

REQUIREMENTS ANALYSIS:
{requirements}

PROPOSAL TEMPLATE STRUCTURE (the sections available to work with):
{template}

---

Produce an actionable proposal outline with these sections:

## 1. SUBMISSION FORMAT & TEMPLATE ASSESSMENT
This section is CRITICAL — check the requirements analysis for submission format requirements.
- **Mandatory template**: Does the solicitation provide a template that MUST be used? If yes, state the filename and note that the draft must be reformatted into it before submission.
- **Volume structure**: How must the response be organized? Adapt the outline to match.
- **Page limits**: State the limit and allocate a page budget per section below.
- **Font/spacing/margins**: State any requirements (e.g., "Arial 11pt, single-spaced, 1-inch margins").
- **File format & submission method**: How and where to submit.
- If no format requirements were identified, state "No mandatory format requirements — using {company_name} standard format."

If the solicitation specifies page limits, include a PAGE BUDGET section. Calculate as follows:

- At 10pt font, single-spaced, 1-inch margins on US Letter: ~500-550 words of body text per page
- Tables, figures, and headers reduce this to ~400-450 effective words per page
- Total word budget = page limit × 450 (conservative estimate)

For each major section in the outline, allocate a word count target based on:
1. The evaluation criteria weighting (sections tied to higher-weighted criteria get more space)
2. The complexity of what needs to be covered
3. Space reserved for tables, figures, and diagrams

Format the budget as:

## Page Budget (X page limit = ~Y words)
| Section | Allocation | Word Target | Notes |
|---------|-----------|-------------|-------|
| 1. Technical Approach | 4 pages | ~1,800 words | Highest-weighted criterion |
| 2. Prior Work | 2 pages | ~900 words | Include evidence table |
| ... | ... | ... | ... |

The drafting phase will use these targets to ensure the proposal uses the available space effectively and doesn't run out of pages before covering all requirements.

## 2. SUBMISSION STRATEGY
- What type of response is this? (full proposal, white paper, capability statement, etc.)
- Recommended response format and approach
- Select 2-3 win themes from {company_name}'s win themes that are most relevant to this opportunity and explain why

## 3. COMPLIANCE MATRIX
Map EVERY requirement from the requirements analysis to a specific proposal section. Use a table:

| Req ID | Requirement Summary | Proposal Section | Approach Summary | Past Performance Reference |
|--------|-------------------|-----------------|------------------|---------------------------|

If a requirement doesn't map cleanly to a template section, note which section should be added or modified.

## 4. TAILORED SECTION OUTLINE
For each proposal section (adapted from the template), provide:
- **Requirements addressed**: Which requirement IDs this section covers
- **Content focus**: What specifically to write about (2-3 sentences)
- **{company_name} capability**: Which specific capability or product to highlight
- **Past performance**: Which program(s) to cite and their relevance
- **Win theme**: Which theme to emphasize
- **Discriminator**: What sets {company_name} apart for this section

Reorder, add, or remove template sections as needed to match the solicitation's expectations.

## 5. GAP ANALYSIS
- Requirements where {company_name} has no directly relevant past performance
- Compliance items with unknown status (clearances, certifications, systems)
- Sections that will need significant [NEEDS INPUT] from the BD team
- Teaming or subcontracting recommendations if gaps are significant

Do NOT write prose or proposal content. Structure only."""


def phase_build_outline(requirements_md: str, opp: dict, opp_dir: Path,
                        knowledge_base: str, rag_context: str,
                        channel: str, thread_ts: str,
                        alignment_md: str = "") -> str:
    slack_reply(channel, thread_ts, "📐 _Building proposal outline & compliance plan..._")
    report_progress("outline", "running", "Building proposal outline & compliance plan...")

    opp_type = _resolve_opp_type(opp)
    _, template_content, _ = _load_template(opp_type)

    if not template_content:
        template_content = "# Executive Summary\n\n# Technical Approach\n\n# Past Performance\n\n# Key Personnel\n\n# Management Approach\n\n# Cost Summary"

    try:
        system_prompt = OUTLINE_SYSTEM_PROMPT.format(
            knowledge_base=knowledge_base if knowledge_base else "(No knowledge base loaded)",
            rag_context=rag_context[:20_000] if rag_context else "(No past submissions found)",
            company_name_upper=_COMPANY_CTX["company_name"].upper(),
            **_COMPANY_CTX,
        )

        user_prompt = OUTLINE_USER_PROMPT.format(
            title=opp.get("title", ""),
            agency=opp.get("agency", ""),
            portal=opp.get("portal", ""),
            opp_type=opp_type,
            due_date=opp.get("due", ""),
            requirements=requirements_md[:30_000] if requirements_md else "(Requirements not available)",
            template=template_content,
            **_COMPANY_CTX,
        )

        if alignment_md:
            user_prompt += f"\n\n---\n\nALIGNMENT ASSESSMENT (use this to inform section prioritization, win themes, and gap mitigation):\n{alignment_md[:20_000]}"

        outline_md = _claude_generate(user_prompt, system_prompt,
                                      phase_label="building outline", channel=channel, thread_ts=thread_ts)

        outline_path = opp_dir / "outline.md"
        outline_path.write_text(outline_md)
        log.info(f"Phase 5: Outline saved to {outline_path}")

        word_count = len(outline_md.split())
        slack_reply(channel, thread_ts,
                    f"📐 Proposal outline complete ({word_count} words)")
        report_progress("outline", "complete", f"Proposal outline complete ({word_count} words)")

        return outline_md
    except Exception as e:
        log.error(f"Phase 5 (outline) error: {e}")
        slack_reply(channel, thread_ts, f"⚠️ Outline generation failed: {e}")
        report_progress("outline", "error", str(e))
        return ""


# ─── PHASE 6: DRAFT RESPONSE ──────────────────────────────────────────────────

DRAFT_SYSTEM_PROMPT = """You are a proposal writer at {company_name}, {company_description}.

{knowledge_base}

Write compelling, specific proposal content. Reference relevant past performance. Use active voice and concrete technical detail. Mark sections where you need more information with [NEEDS INPUT: description of what's needed].

CRITICAL: Output ONLY the document content. Do NOT include any preamble, commentary, thinking, or meta-discussion before or after the document. Start directly with the document title/heading."""

DRAFT_USER_PROMPT = """Draft a response to the following government solicitation.

OPPORTUNITY:
- Title: {title}
- Agency: {agency}
- Portal: {portal}
- Type: {opp_type}
- Due Date: {due_date}

REQUIREMENTS ANALYSIS:
{requirements}

PROPOSAL OUTLINE (your blueprint — follow this section-by-section):
{outline}

RELEVANT PAST SUBMISSIONS (for context and tone):
{rag_context}

IMPORTANT FORMATTING RULES:

1. Start with a TITLE PAGE containing:
   - The opportunity title (large heading)
   - Submission type (e.g., "BAA Response", "White Paper", "Capability Statement")
   - Company: {legal_name}
   - CAGE: {cage} | UEI: {uei}
   - POC: {poc_name}, {poc_title} | {poc_email} | {poc_phone}
   - Business Size: {business_size}
   - Solicitation number (or [NEEDS INPUT] if unknown)
   - Due date
   - Date of submission: [NEEDS INPUT]

2. After the title page, insert a horizontal rule (---) as a page break.

3. Then begin the actual submission content on the next section.

CRITICAL DRAFTING RULES — follow these for every section:

1. SUBSTANTIATE EVERY CLAIM. Never write '{company_name} has extensive experience in X' or '{company_name} is well-positioned to...' without citing a specific deployment, exercise, contract, or documented result. Instead write: '{company_name} demonstrated X during [specific exercise/contract], achieving [specific metric/result].' Pull evidence from the knowledge base and RAG context.

2. If you cannot find specific evidence for a claim in the provided context, mark it as [NEEDS EVIDENCE: description of what claim needs support] instead of fabricating or generalizing. It is better to flag a gap than to make an unsubstantiated assertion.

3. USE SOLICITATION TERMINOLOGY EXACTLY. Refer to the 'Solicitation Terminology & Keywords' section of the requirements document. Every keyword, function name, performance threshold, and acronym must appear in the draft exactly as the solicitation wrote it. Do NOT paraphrase keywords, invent acronym expansions, substitute function names, or soften performance thresholds.

4. RESPECT PHASE SCOPE. Refer to the 'Phase Scope Markers' section of the requirements document. Do not describe Phase II deliverables or activities in a Phase I proposal. If the solicitation says Phase II includes lab demonstrations or field testing, do not include those in the Phase I work plan.

5. WRITE TO THE PAGE LIMIT. If the solicitation specifies a page limit, aim for 90-100% of the allowed length. A proposal that comes in well under the page limit signals insufficient substance. Use the page budget from the outline to guide section lengths.

WRITING INSTRUCTIONS:
Follow the proposal outline section-by-section. Each section in the outline specifies:
- Which requirements to address
- Which past performance to cite and why
- Which win themes to emphasize
- What {company_name} capabilities to highlight

For each section, write polished proposal prose that:
- Addresses the specified requirements explicitly
- Cites the past performance references assigned in the outline
- Emphasizes the win themes and discriminators noted in the outline
- Uses specific technical details from {company_name}'s capabilities
- Flags sections needing human input with [NEEDS INPUT: ...]
- Does NOT fabricate past performance — only reference programs from the outline and past submissions above"""


def phase_draft_response(requirements_md: str, outline_md: str, rag_context: str,
                          opp: dict, opp_dir: Path, channel: str, thread_ts: str,
                          alignment_md: str = "") -> str:
    slack_reply(channel, thread_ts, "✍️ _Drafting response..._")
    report_progress("draft", "running", "Drafting response...")

    opp_type = _resolve_opp_type(opp)
    knowledge_base = _load_knowledge_base()

    log.info(f"Phase 6: Drafting response for opp type '{opp_type}'")

    if not outline_md:
        log.warning("Phase 6: No outline available — falling back to raw template")
        _, template_content, _ = _load_template(opp_type)
        outline_md = template_content or "# Executive Summary\n\n# Technical Approach\n\n# Past Performance\n\n# Key Personnel\n\n# Management Approach\n\n# Cost Summary"

    try:
        system_prompt = DRAFT_SYSTEM_PROMPT.format(
            knowledge_base=knowledge_base if knowledge_base else "(No knowledge base loaded)",
            **_COMPANY_CTX,
        )

        user_prompt = DRAFT_USER_PROMPT.format(
            title=opp.get("title", ""),
            agency=opp.get("agency", ""),
            portal=opp.get("portal", ""),
            opp_type=opp_type,
            due_date=opp.get("due", ""),
            requirements=requirements_md[:30_000] if requirements_md else "(Requirements not available)",
            rag_context=rag_context[:30_000] if rag_context else "(No past submissions found)",
            outline=outline_md[:30_000],
            **_COMPANY_CTX,
        )

        if alignment_md:
            user_prompt += f"\n\n---\n\nALIGNMENT ASSESSMENT (use strength map for evidence-first writing, gap map for mitigation strategies, and evaluator lens for emphasis):\n{alignment_md[:20_000]}"

        draft_md = _claude_generate(user_prompt, system_prompt,
                                    phase_label="drafting response", channel=channel, thread_ts=thread_ts)

        draft_path = opp_dir / "draft.md"
        draft_path.write_text(draft_md)
        log.info(f"Phase 6: Draft saved to {draft_path}")

        needs_input_count = draft_md.count("[NEEDS INPUT:")
        slack_reply(channel, thread_ts,
                    f"✍️ Draft complete ({len(draft_md)} chars, {needs_input_count} sections need input)")
        report_progress("draft", "complete", f"Draft complete ({len(draft_md)} chars, {needs_input_count} sections need input)")

        return draft_md
    except Exception as e:
        log.error(f"Phase 6 error: {e}")
        slack_reply(channel, thread_ts, f"⚠️ Draft generation failed: {e}")
        report_progress("draft", "error", str(e))
        return ""


# ─── PHASE 6.5: MULTI-PERSPECTIVE REVIEW ────────────────────────────────────

REVIEW_PASSES = [
    {
        "label": "External evaluator",
        "system": """You are an independent government evaluator scoring this proposal against the published evaluation criteria. You have never seen this proposal before and have no relationship with the proposer.

For each evaluation criterion from the requirements document:
- Assign a preliminary rating: Outstanding / Good / Acceptable / Marginal / Unacceptable
- List specific strengths an evaluator would note
- List specific weaknesses, gaps, or missing requirements
- Verify that every capability claim is substantiated with evidence, not just asserted

After your evaluation, revise the draft to address every weakness you identified. Do not remove content — strengthen it. Output the complete revised draft.

CRITICAL: Output ONLY the revised document. No preamble, no evaluation notes, no commentary — start directly with the document title/heading.""",
    },
    {
        "label": "Second independent evaluator",
        "system": """You are a second government evaluator reading this proposal fresh — you have not seen the first evaluator's notes. Different evaluators catch different things.

Focus your review on:
- Technical soundness: Is the proposed approach actually feasible? Are there logical gaps?
- Schedule realism: Can this work plan actually be completed in the proposed timeframe?
- Evidence quality: Are claims backed by specific deployments, contracts, or results — or just general assertions?
- Readability: Can a non-expert evaluator follow the argument? Are there jargon-heavy sections that need clarification?

After your evaluation, revise the draft to address issues found. Output the complete revised draft.

CRITICAL: Output ONLY the revised document. No preamble, no evaluation notes, no commentary — start directly with the document title/heading.""",
    },
    {
        "label": "{company_name} leadership review",
        "system": """You are a senior leader at {company_name} reviewing this proposal before it goes out. You know the company's actual capabilities, ongoing commitments, and strategic direction.

{knowledge_base}

Look for:
- OVERPROMISES: Anything the proposal commits to that {company_name} can't realistically deliver with current resources and capabilities
- MISSED STRENGTHS: {company_name} capabilities, differentiators, or past performance that weren't highlighted but should be
- STRATEGIC POSITIONING: Does this proposal position {company_name} well for Phase II, Phase III, and follow-on work?
- VOICE AND TONE: Does this sound like {company_name} — confident but honest, technically deep but accessible? Or does it sound generic?
- RESOURCE REALITY: Are the proposed personnel, facilities, and timelines realistic given other commitments?

After your review, revise the draft to address issues found. Output the complete revised draft.

CRITICAL: Output ONLY the revised document. No preamble, no review notes, no commentary — start directly with the document title/heading.""",
    },
    {
        "label": "Critical capability verification",
        "system": """You are conducting a final credibility check on this proposal. This is the most important review pass. Your job is to protect {company_name}'s credibility by catching any claims that aren't backed by real evidence.

{knowledge_base}

RELEVANT PAST SUBMISSIONS:
{rag_context}

Go line by line through EVERY claim about what {company_name} has done or can do. For each one, ask: 'Is this backed by a specific deployment, contract, exercise, or documented result in the knowledge base?'

Specifically look for:

1. CAPABILITY CLAIM INFLATION — Claims backed only by proposals {company_name} submitted (not won), general capability statements, or vague references. A submission is not evidence of capability — only a win, a deployment, or a documented result counts.

2. PLATFORM CAPABILITY STRETCH — Places where the proposal extends a proven capability (e.g., voice processing) to imply broader capability (e.g., multimodal sensor fusion) without acknowledging the development gap. The extension may be reasonable for R&D, but the proposal should be transparent about what's proven vs. what's new development.

3. FABRICATED REFERENCES — Any named contract, exercise, partner, or product that doesn't appear in the knowledge base. If you can't verify it, flag it with [UNVERIFIED: description].

4. UNCONTEXTUALIZED EVIDENCE — Any exercise or contract mentioned without explaining what {company_name} actually did there. '{company_name} participated in Exercise X' is not evidence — '{company_name} deployed [specific system] at Exercise X, demonstrating [specific capability]' is.

For each issue found, either fix it (if the fix is clear from available evidence) or flag it with [REVIEW NEEDED: explanation]. Then output the complete revised draft.

CRITICAL: Output ONLY the revised document. No preamble, no audit notes, no commentary — start directly with the document title/heading.""",
    },
]

REVIEW_USER_PROMPT = """Review and revise the following proposal draft.

OPPORTUNITY:
- Title: {title}
- Agency: {agency}
- Type: {opp_type}
- Due Date: {due_date}

REQUIREMENTS ANALYSIS:
{requirements}

{alignment_block}

DRAFT TO REVISE:
{draft}"""


def phase_review_and_revise(draft_md: str, outline_md: str, requirements_md: str,
                             opp: dict, opp_dir: Path,
                             channel: str, thread_ts: str,
                             alignment_md: str = "", rag_context: str = "") -> str:
    """Run 4-pass multi-perspective review cycle on the draft."""
    if not draft_md:
        log.warning("Phase 6.5: No draft to review — skipping")
        return draft_md

    slack_reply(channel, thread_ts, "🔍 _Starting 4-pass review cycle..._")
    report_progress("review", "running", "Starting 4-pass review cycle...")

    knowledge_base = _load_knowledge_base()
    current_draft = draft_md
    orig_words = len(draft_md.split())

    alignment_block = f"ALIGNMENT ASSESSMENT:\n{alignment_md[:15_000]}" if alignment_md else ""

    for i, review_pass in enumerate(REVIEW_PASSES, 1):
        pass_label = review_pass["label"].format(**_COMPANY_CTX)
        slack_reply(channel, thread_ts, f"🔍 _Review pass {i}/4: {pass_label}..._")
        report_progress("review", "running", f"Review pass {i}/4: {pass_label}...")

        try:
            system_prompt = review_pass["system"].format(
                knowledge_base=knowledge_base if knowledge_base else "(No knowledge base loaded)",
                rag_context=rag_context[:20_000] if rag_context else "(No past submissions found)",
                **_COMPANY_CTX,
            )

            user_prompt = REVIEW_USER_PROMPT.format(
                title=opp.get("title", ""),
                agency=opp.get("agency", ""),
                opp_type=_resolve_opp_type(opp),
                due_date=opp.get("due", ""),
                requirements=requirements_md[:20_000] if requirements_md else "(not available)",
                alignment_block=alignment_block,
                draft=current_draft[:50_000],
            )

            revised = _claude_generate(user_prompt, system_prompt,
                                        phase_label=f"review pass {i}/4: {pass_label}",
                                        channel=channel, thread_ts=thread_ts)

            if not revised:
                log.warning(f"Phase 6.5: Review pass {i}/4 returned empty — keeping previous draft")
                slack_reply(channel, thread_ts, f"⚠️ Review pass {i}/4 returned empty — skipping")
                continue

            pass_path = opp_dir / f"draft_review_pass{i}.md"
            pass_path.write_text(revised)
            log.info(f"Phase 6.5: Pass {i}/4 ({pass_label}) saved to {pass_path}")

            pass_words = len(revised.split())
            log.info(f"Phase 6.5: Pass {i}/4 — {pass_words} words ({pass_words - len(current_draft.split()):+d})")
            current_draft = revised

        except Exception as e:
            log.error(f"Phase 6.5 pass {i}/4 ({pass_label}) error: {e}")
            slack_reply(channel, thread_ts, f"⚠️ Review pass {i}/4 ({pass_label}) failed — continuing with current draft: {e}")

    v2_path = opp_dir / "draft_v2.md"
    v2_path.write_text(current_draft)
    log.info(f"Phase 6.5: Final reviewed draft saved to {v2_path}")

    final_words = len(current_draft.split())
    delta = final_words - orig_words
    slack_reply(channel, thread_ts,
                f"🔍 4-pass review complete ({final_words} words, {delta:+d} vs. original)")
    report_progress("review", "complete", f"4-pass review complete ({final_words} words, {delta:+d} vs. original)")

    return current_draft


# ─── PHASE 6.75: SOLICITATION COMPLIANCE CHECK ──────────────────────────────

COMPLIANCE_SYSTEM_PROMPT = """You are performing a mechanical compliance check on this proposal draft against the solicitation's exact requirements. This is NOT a subjective review — it is a checklist verification. Every item must be checked and reported.

{knowledge_base}

{alignment_context}

Using the 'Solicitation Terminology & Keywords' section from the requirements document as your source of truth, verify the following:

## 1. Keyword Verification
For EVERY keyword listed in the terminology section, confirm it appears in the draft using the solicitation's exact wording. Report:
- ✅ [keyword] — found in draft (cite location)
- ❌ [keyword] — MISSING or paraphrased (show what the draft says instead)

## 2. Required Functions Verification
For EVERY required function name, confirm the draft uses the exact term. Report:
- ✅ [function] — used correctly
- ❌ [function] — missing, substituted, or paraphrased (show the substitution)

## 3. Performance Threshold Verification
For EVERY performance number, confirm the draft matches the solicitation's exact notation. Report:
- ✅ [threshold] — matches exactly
- ❌ [threshold] — weakened or altered (e.g., draft says '400 GB/s' but solicitation says '>400 GB/s')

## 4. Phase Scope Verification
Confirm Phase I content doesn't include Phase II deliverables or activities. Report any scope creep found.

## 5. Reference Verification
Confirm all reference numbers map to the correct documents per the solicitation.

## 6. Standards & Compliance Verification
Confirm all regulation citations, certifications, and standards match the solicitation exactly.

## 7. Capability Claim Verification
For EVERY claim about the proposer's capabilities or past performance, confirm it is traceable to evidence in the knowledge base or alignment assessment. Report:
- ✅ [claim] — substantiated by [evidence source]
- ❌ [claim] — UNSUBSTANTIATED (no evidence found)
- ⚠️ [claim] — PARTIALLY SUBSTANTIATED (evidence exists but claim extends beyond it)

After completing the checklist, produce a corrected version of the draft with ALL failed items fixed. If a capability claim can't be substantiated, either remove it, weaken it to match available evidence, or flag it as [NEEDS EVIDENCE: ...].

OUTPUT FORMAT: First output the compliance report (sections 1-7 above), then output a separator line "---CORRECTED DRAFT---", then output the complete corrected draft. Both sections are required."""

COMPLIANCE_USER_PROMPT = """Run a solicitation compliance check on this proposal draft.

OPPORTUNITY:
- Title: {title}
- Agency: {agency}
- Type: {opp_type}
- Due Date: {due_date}

REQUIREMENTS ANALYSIS (the Solicitation Terminology & Keywords section is your source of truth):
{requirements}

DRAFT TO CHECK:
{draft}"""


def phase_compliance_check(draft_md: str, requirements_md: str,
                            opp: dict, opp_dir: Path,
                            channel: str, thread_ts: str,
                            alignment_md: str = "") -> str:
    """Mechanical compliance check against solicitation terminology and requirements."""
    if not draft_md:
        log.warning("Phase 6.75: No draft to check — skipping")
        return draft_md

    slack_reply(channel, thread_ts, "📋 _Running solicitation compliance check..._")
    report_progress("compliance", "running", "Running solicitation compliance check...")

    knowledge_base = _load_knowledge_base()

    try:
        system_prompt = COMPLIANCE_SYSTEM_PROMPT.format(
            knowledge_base=knowledge_base if knowledge_base else "(No knowledge base loaded)",
            alignment_context=f"ALIGNMENT ASSESSMENT:\n{alignment_md[:15_000]}" if alignment_md else "",
            **_COMPANY_CTX,
        )

        user_prompt = COMPLIANCE_USER_PROMPT.format(
            title=opp.get("title", ""),
            agency=opp.get("agency", ""),
            opp_type=_resolve_opp_type(opp),
            due_date=opp.get("due", ""),
            requirements=requirements_md[:25_000] if requirements_md else "(not available)",
            draft=draft_md[:50_000],
        )

        result = _claude_generate(user_prompt, system_prompt,
                                   phase_label="compliance check", channel=channel, thread_ts=thread_ts)

        if not result:
            log.warning("Phase 6.75: Compliance check returned empty — using previous draft")
            slack_reply(channel, thread_ts, "⚠️ Compliance check returned empty — using previous draft")
            return draft_md

        separator = "---CORRECTED DRAFT---"
        if separator in result:
            report_part, corrected_draft = result.split(separator, 1)
            corrected_draft = corrected_draft.strip()
        else:
            log.warning("Phase 6.75: No separator found — treating entire output as corrected draft")
            report_part = ""
            corrected_draft = result

        if report_part.strip():
            report_path = opp_dir / "compliance_report.md"
            report_path.write_text(report_part.strip())
            log.info(f"Phase 6.75: Compliance report saved to {report_path}")

        if corrected_draft:
            v3_path = opp_dir / "draft_v3.md"
            v3_path.write_text(corrected_draft)
            log.info(f"Phase 6.75: Corrected draft saved to {v3_path}")

            fail_count = report_part.count("❌") if report_part else 0
            warn_count = report_part.count("⚠️") if report_part else 0
            slack_reply(channel, thread_ts,
                        f"📋 Compliance check complete ({fail_count} issues fixed, {warn_count} warnings)")
            report_progress("compliance", "complete",
                            f"Compliance check complete ({fail_count} issues fixed, {warn_count} warnings)")
            return corrected_draft
        else:
            log.warning("Phase 6.75: Corrected draft was empty — using previous draft")
            slack_reply(channel, thread_ts, "⚠️ Compliance check produced no corrected draft — using previous draft")
            return draft_md

    except Exception as e:
        log.error(f"Phase 6.75 (compliance) error: {e}")
        slack_reply(channel, thread_ts, f"⚠️ Compliance check failed — using previous draft: {e}")
        report_progress("compliance", "error", str(e))
        return draft_md


# ─── PHASE 7: SUBMISSION CHECKLIST ───────────────────────────────────────────

CHECKLIST_SYSTEM_PROMPT = """You are a proposal compliance reviewer at {company_name}. Your job is to produce a clear, actionable checklist of everything the BD team needs to complete, verify, or fix before this submission is ready.

CRITICAL: Output ONLY the checklist document. Do NOT include any preamble, commentary, or meta-discussion."""

CHECKLIST_USER_PROMPT = """Review the following proposal documents and produce a submission-readiness checklist.

OPPORTUNITY:
- Title: {title}
- Agency: {agency}
- Due Date: {due_date}

REQUIREMENTS ANALYSIS:
{requirements}

PROPOSAL OUTLINE:
{outline}

DRAFT RESPONSE:
{draft}

---

Produce a checklist with these sections:

## 1. SUBMISSION FORMAT COMPLIANCE
Review the requirements analysis for format/document requirements and check the draft against them:
- [ ] Mandatory template identified and used (or flagged if not yet applied)
- [ ] Page limits met (state current page estimate vs. limit)
- [ ] Font, spacing, and margin requirements met
- [ ] Volume structure matches solicitation requirements
- [ ] File format and naming convention requirements noted
- [ ] Submission portal/method identified
- If no format requirements were specified, note "No mandatory format requirements identified."

## 2. CONTENT GAPS — NEEDS INPUT
Extract EVERY [NEEDS INPUT: ...] marker from the draft and list them grouped by category:
- **Personnel** (bios, certifications, clearances)
- **Cost/Pricing** (rates, CLINs, BOEs)
- **Past Performance** (POC contacts, contract numbers, values)
- **Technical** (specific data, metrics, architecture details)
- **Administrative** (solicitation numbers, dates, signatures)

## 3. COMPLIANCE VERIFICATION
Based on the requirements analysis, list compliance items that need verification:
- [ ] Security clearance requirements met
- [ ] CMMC/cybersecurity compliance documented
- [ ] SAM.gov registration current
- [ ] Required certifications and representations ready
- [ ] Teaming agreements in place (if applicable)
- [ ] Data rights strategy determined

## 4. REVIEW & APPROVAL ACTIONS
- [ ] Technical review by subject matter expert
- [ ] Past performance references contacted for permission
- [ ] Cost/pricing review and approval
- [ ] Executive review and sign-off
- [ ] Final formatting and compliance check
- [ ] Submission timeline with internal deadlines

Mark items that are already satisfied based on the documents as [x]. Leave items that need action as [ ].
Be specific — don't list generic items. Every checklist item should reference the specific requirement or gap it addresses."""


def phase_build_checklist(requirements_md: str, outline_md: str, draft_md: str,
                          opp: dict, opp_dir: Path,
                          channel: str, thread_ts: str) -> str:
    slack_reply(channel, thread_ts, "✅ _Building submission checklist..._")
    report_progress("checklist", "running", "Building submission checklist...")

    try:
        system_prompt = CHECKLIST_SYSTEM_PROMPT.format(**_COMPANY_CTX)
        user_prompt = CHECKLIST_USER_PROMPT.format(
            title=opp.get("title", ""),
            agency=opp.get("agency", ""),
            due_date=opp.get("due", ""),
            requirements=requirements_md[:20_000] if requirements_md else "(not available)",
            outline=outline_md[:15_000] if outline_md else "(not available)",
            draft=draft_md[:30_000] if draft_md else "(not available)",
        )

        checklist_md = _claude_generate(user_prompt, system_prompt,
                                        phase_label="building checklist", channel=channel, thread_ts=thread_ts)

        checklist_path = opp_dir / "checklist.md"
        checklist_path.write_text(checklist_md)
        log.info(f"Phase 7: Checklist saved to {checklist_path}")

        needs_input = draft_md.count("[NEEDS INPUT") if draft_md else 0
        slack_reply(channel, thread_ts,
                    f"✅ Submission checklist complete ({needs_input} items need input)")
        report_progress("checklist", "complete", f"Submission checklist complete ({needs_input} items need input)")

        return checklist_md
    except Exception as e:
        log.error(f"Phase 7 (checklist) error: {e}")
        slack_reply(channel, thread_ts, f"⚠️ Checklist generation failed: {e}")
        report_progress("checklist", "error", str(e))
        return ""


# ─── PHASE 7.5: FORMAT POLISH ───────────────────────────────────────────────

FORMAT_SYSTEM_PROMPT = """You are a document formatter. Your job is to reformat a proposal document's markdown for clean conversion to Google Docs. You must NOT change any content, wording, or meaning. You are only restructuring the markdown.

FORMATTING RULES:

1. HEADING HIERARCHY:
   - # = Document title only (one per document)
   - ## = Major numbered sections: "## 1. Executive Summary"
   - ### = Numbered subsections: "### 1.1 Subsection Title"
   - #### = Numbered sub-subsections: "#### 1.1.1 Sub-subsection Title"
   - Number all sections hierarchically. The title page is not numbered.

2. BOLD-INLINE HEADERS:
   When a line starts with "**Label:** description text" and the label functions as a subsection heading (introduces a block of content, stands alone or starts a paragraph), convert it to a proper heading:

   #### Label
   Description text

   When the bold label is a short inline field within metadata or a compact list (like "**Company:** Acme Corp" or "**Key Achievements:**"), leave it as-is.

3. SPACING:
   - One blank line before every heading
   - One blank line after every heading
   - One blank line between paragraphs
   - No triple+ blank lines anywhere

4. TITLE PAGE:
   The title page section (everything before the first ---) should use:
   - # for the document title
   - ## for the subtitle (e.g., "BAA Response", "White Paper")
   - Regular bold text for metadata fields (company, CAGE, POC, etc.)

5. PAGE BREAKS:
   Keep --- (horizontal rules) as page break markers. Do not add or remove them.

6. LISTS AND TABLES:
   - Bullet lists: use - (dash) consistently
   - Keep list items on their own lines
   - Tables should be preserved exactly as-is

CRITICAL: Output ONLY the reformatted document. Do not add, remove, or change any content words. Same text, better structure."""

FORMAT_USER_PROMPT = """Reformat the following proposal document according to the formatting rules. Do not change any content — only restructure the markdown for proper heading hierarchy, section numbering, and visual spacing.

DOCUMENT TO FORMAT:
{draft}"""


def phase_format_polish(draft_md: str, opp: dict, opp_dir: Path,
                         channel: str, thread_ts: str) -> str:
    """Reformat draft markdown for proper document structure."""
    if not draft_md:
        log.warning("Phase 7.5: No draft to format — skipping")
        return draft_md

    slack_reply(channel, thread_ts, "📄 _Polishing document formatting..._")
    report_progress("format", "running", "Polishing document formatting...")

    try:
        user_prompt = FORMAT_USER_PROMPT.format(draft=draft_md[:50_000])

        formatted = _claude_generate(user_prompt, FORMAT_SYSTEM_PROMPT,
                                      phase_label="formatting document", channel=channel, thread_ts=thread_ts)

        if not formatted:
            log.warning("Phase 7.5: Format pass returned empty — using unformatted draft")
            slack_reply(channel, thread_ts, "⚠️ Format polish returned empty — using unformatted draft")
            return draft_md

        final_path = opp_dir / "draft_final.md"
        final_path.write_text(formatted)
        log.info(f"Phase 7.5: Formatted draft saved to {final_path}")

        slack_reply(channel, thread_ts, "📄 Document formatting complete")
        report_progress("format", "complete", "Document formatting complete")

        return formatted
    except Exception as e:
        log.error(f"Phase 7.5 error: {e}")
        slack_reply(channel, thread_ts, f"⚠️ Format polish failed — using unformatted draft: {e}")
        report_progress("format", "error", str(e))
        return draft_md


# ─── PHASE 8: DELIVER OUTPUTS ─────────────────────────────────────────────────

def _get_docs_service():
    """Build and return an authenticated Google Docs API service."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds_path = Path.home() / "Library/Application Support/gogcli/credentials-wood-project.json"
    token_path = SECRETS_DIR / ".gog-token.json"

    if not token_path.exists():
        result = subprocess.run(
            ["/opt/homebrew/bin/gog", "auth", "tokens", "export",
             DRIVE_ACCOUNT, "--out", str(token_path), "--overwrite"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise RuntimeError(f"Could not export token: {result.stderr[:200]}")

    token_data = json.loads(token_path.read_text())
    creds_data = json.loads(creds_path.read_text())
    inner = creds_data.get("installed", creds_data.get("web", creds_data))

    creds = Credentials(
        token=None,
        refresh_token=token_data.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=inner["client_id"],
        client_secret=inner["client_secret"],
    )
    return build("docs", "v1", credentials=creds)


def _apply_document_formatting(doc_id: str):
    """Apply heading-aware spacing to a Google Doc for visual hierarchy."""
    HEADING_SPACING = {
        "HEADING_1": {"spaceAbove": 0,  "spaceBelow": 6},
        "HEADING_2": {"spaceAbove": 18, "spaceBelow": 6},
        "HEADING_3": {"spaceAbove": 14, "spaceBelow": 4},
        "HEADING_4": {"spaceAbove": 10, "spaceBelow": 2},
    }
    DEFAULT_SPACING = {"spaceAbove": 0, "spaceBelow": 4}

    try:
        service = _get_docs_service()
        doc = service.documents().get(documentId=doc_id).execute()
        elements = doc.get("body", {}).get("content", [])

        requests = []
        for el in elements:
            para = el.get("paragraph")
            if not para:
                continue
            start = el.get("startIndex")
            end = el.get("endIndex")
            if start is None or end is None or start >= end:
                continue

            style_type = para.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
            spacing = HEADING_SPACING.get(style_type, DEFAULT_SPACING)

            requests.append({
                "updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": {
                        "lineSpacing": 100,
                        "spaceAbove": {"magnitude": spacing["spaceAbove"], "unit": "PT"},
                        "spaceBelow": {"magnitude": spacing["spaceBelow"], "unit": "PT"},
                    },
                    "fields": "lineSpacing,spaceAbove,spaceBelow",
                }
            })

        if requests:
            service.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": requests}
            ).execute()
            log.info(f"Applied document formatting ({len(requests)} paragraphs) to doc {doc_id}")
        else:
            log.info(f"No paragraphs found in doc {doc_id} — skipping formatting")
    except Exception as e:
        log.warning(f"Document formatting failed (non-fatal): {e}")


def _insert_page_breaks(doc_id: str):
    """Replace horizontal rules with page breaks in a Google Doc."""
    try:
        service = _get_docs_service()
        doc = service.documents().get(documentId=doc_id).execute()

        elements = doc.get("body", {}).get("content", [])
        first_hr = None
        for el in elements:
            para = el.get("paragraph", {})
            if not para:
                continue
            for run in para.get("elements", []):
                if run.get("horizontalRule"):
                    first_hr = el
                    break
            if first_hr:
                break

        if first_hr:
            start = first_hr["startIndex"]
            end = first_hr["endIndex"]
            service.documents().batchUpdate(
                documentId=doc_id,
                body={"requests": [
                    {"deleteContentRange": {"range": {"startIndex": start, "endIndex": end}}},
                    {"insertPageBreak": {"location": {"index": start}}},
                ]}
            ).execute()
            log.info(f"Inserted title page break in doc {doc_id}")
        else:
            log.info(f"No horizontal rule found for title page break in doc {doc_id}")

    except Exception as e:
        log.warning(f"Page break insertion failed (non-fatal): {e}")


def _upload_md_as_doc(title: str, md_path: Path, drive_folder_id: str,
                      insert_page_breaks: bool = False) -> str | None:
    try:
        result = subprocess.run(
            ["/opt/homebrew/bin/gog", "docs", "create", title,
             "--file", str(md_path),
             "--parent", drive_folder_id,
             "-a", DRIVE_ACCOUNT, "-j"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            file_data = data.get("file", data.get("doc", {}))
            doc_id = file_data.get("id", file_data.get("documentId", ""))
            link = file_data.get("webViewLink", data.get("webViewLink", ""))
            log.info(f"Created Google Doc: {title}")
            if doc_id:
                _apply_document_formatting(doc_id)
                if insert_page_breaks:
                    _insert_page_breaks(doc_id)
            return link
        else:
            log.warning(f"Google Doc creation failed: {result.stderr[:200]}")
    except Exception as e:
        log.warning(f"Google Doc creation error: {e}")
    return None


def phase_deliver(opp: dict, opp_dir: Path, drive_folder_id: str,
                   channel: str, thread_ts: str):
    slack_reply(channel, thread_ts, "📤 _Uploading documents to Google Drive..._")
    report_progress("deliver", "running", "Uploading documents to Google Drive...")

    title = opp.get("title", "Opportunity")[:80]
    links = {}

    req_path = opp_dir / "requirements.md"
    if req_path.exists():
        link = _upload_md_as_doc(f"Requirements Analysis — {title}", req_path, drive_folder_id)
        if link:
            links["requirements"] = link

    alignment_path = opp_dir / "alignment.md"
    if alignment_path.exists():
        link = _upload_md_as_doc(f"Alignment Assessment — {title}", alignment_path, drive_folder_id)
        if link:
            links["alignment"] = link

    outline_path = opp_dir / "outline.md"
    if outline_path.exists():
        link = _upload_md_as_doc(f"Proposal Outline — {title}", outline_path, drive_folder_id)
        if link:
            links["outline"] = link

    draft_path = opp_dir / "draft_final.md"
    if not draft_path.exists():
        draft_path = opp_dir / "draft_v3.md"
    if not draft_path.exists():
        draft_path = opp_dir / "draft_v2.md"
    if not draft_path.exists():
        draft_path = opp_dir / "draft.md"
    if draft_path.exists():
        link = _upload_md_as_doc(f"Draft Response — {title}", draft_path, drive_folder_id,
                                insert_page_breaks=True)
        if link:
            links["draft"] = link

    compliance_path = opp_dir / "compliance_report.md"
    if compliance_path.exists():
        link = _upload_md_as_doc(f"Compliance Report — {title}", compliance_path, drive_folder_id)
        if link:
            links["compliance"] = link

    checklist_path = opp_dir / "checklist.md"
    if checklist_path.exists():
        link = _upload_md_as_doc(f"Submission Checklist — {title}", checklist_path, drive_folder_id)
        if link:
            links["checklist"] = link

    if links:
        parts = ["✅ *RFP Response Agent complete*\n"]
        if "requirements" in links:
            parts.append(f"📋 <{links['requirements']}|Requirements Analysis>")
        if "alignment" in links:
            parts.append(f"🎯 <{links['alignment']}|Alignment Assessment>")
        if "outline" in links:
            parts.append(f"📐 <{links['outline']}|Proposal Outline>")
        if "draft" in links:
            parts.append(f"✍️ <{links['draft']}|Draft Response>")
        if "compliance" in links:
            parts.append(f"📋 <{links['compliance']}|Compliance Report>")
        if "checklist" in links:
            parts.append(f"✅ <{links['checklist']}|Submission Checklist>")
        parts.append(f"\n_Documents saved to the opportunity's Google Drive folder._")
        slack_reply(channel, thread_ts, "\n".join(parts))
        links["folder"] = f"https://drive.google.com/drive/folders/{drive_folder_id}"
        report_progress("deliver", "complete", "Documents uploaded to Google Drive",
                        drive_links=links)
    else:
        slack_reply(channel, thread_ts, "⚠️ Could not upload documents to Google Drive. "
                    f"Local copies saved at: {opp_dir}")
        report_progress("deliver", "error", "Could not upload documents to Google Drive")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def make_opp_slug(opp: dict) -> str:
    title = opp.get("title", "untitled")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title)[:60].strip("-").lower()
    date = datetime.now().strftime("%Y%m%d")
    return f"{date}-{slug}"


def main():
    global _PROFILE_NAME, _DRAFT_RUN_ID, _API_URL, SECRETS_DIR, DRIVE_ACCOUNT, _COMPANY_CTX

    parser = argparse.ArgumentParser(description="Yukon RFP Response Agent")
    parser.add_argument("--opp-json", required=True, help="Opportunity data as JSON string")
    parser.add_argument("--drive-folder-id", required=True, help="Google Drive folder ID")
    parser.add_argument("--slack-channel", default="", help="Slack channel for progress updates")
    parser.add_argument("--slack-thread", default="", help="Slack thread timestamp")
    parser.add_argument("--draft-run-id", type=int, default=None, help="Draft run ID for web progress reporting")
    parser.add_argument("--api-url", default="http://localhost:3000", help="Prospector API URL")
    parser.add_argument("--profile", default="velocity", help="Profile name (folder under configs/)")
    args = parser.parse_args()

    # Profile-aware config loading
    _PROFILE_NAME = args.profile
    profile_env = BASE_DIR / "configs" / _PROFILE_NAME / ".env"
    if profile_env.exists():
        load_dotenv(profile_env, override=True)

    profile_config = _load_profile_config()
    SECRETS_DIR = BASE_DIR / "configs" / _PROFILE_NAME
    DRIVE_ACCOUNT = profile_config.get("google_drive_account", "david@velocityexplorations.com")

    meta = profile_config.get("company_meta", {})
    if meta:
        _COMPANY_CTX = {
            "company_name": meta.get("short_name", meta.get("legal_name", _PROFILE_NAME)),
            "legal_name": meta.get("legal_name", ""),
            "short_name": meta.get("short_name", ""),
            "cage": meta.get("cage", ""),
            "uei": meta.get("uei", ""),
            "duns": meta.get("duns", ""),
            "business_size": meta.get("business_size", "Small Business"),
            "poc_name": meta.get("poc_name", ""),
            "poc_title": meta.get("poc_title", ""),
            "poc_email": meta.get("poc_email", ""),
            "poc_phone": meta.get("poc_phone", ""),
            "naics_display": meta.get("naics_display", ""),
            "company_description": meta.get("company_description", ""),
        }

    # Web progress reporting
    _DRAFT_RUN_ID = args.draft_run_id
    _API_URL = args.api_url

    try:
        opp = json.loads(args.opp_json)
    except json.JSONDecodeError as e:
        log.error(f"Invalid --opp-json: {e}")
        sys.exit(1)

    drive_folder_id = args.drive_folder_id
    channel = args.slack_channel
    thread_ts = args.slack_thread

    slug = make_opp_slug(opp)
    opp_dir = BASE_DIR / "data" / "rfp-agent" / slug
    opp_dir.mkdir(parents=True, exist_ok=True)

    (opp_dir / "opp.json").write_text(json.dumps(opp, indent=2))

    log.info(f"RFP Response Agent started for: {opp.get('title', 'unknown')}")
    log.info(f"Output directory: {opp_dir}")
    t0 = time.monotonic()

    (BASE_DIR / "logs").mkdir(exist_ok=True)

    try:
        # Load Velocity context early (used by both requirements and draft phases)
        knowledge_base = _load_knowledge_base()

        # Phase 1: Scrape listing
        listing_text = phase_scrape_listing(opp, channel, thread_ts)

        # Phase 2: Load/download attachments (cache-first)
        attachments = phase_download_attachments(opp, opp_dir, drive_folder_id, channel, thread_ts)

        # Phase 3: RAG context retrieval (before requirements so we have Velocity context)
        att_text = " ".join(a.get("text", "")[:500] for a in attachments if a.get("text"))
        rag_context = phase_rag_retrieval(f"{listing_text}\n{att_text}"[:3000], opp)

        # Phase 4: Extract requirements (with full context: docs + Velocity KB + RAG)
        requirements_md = phase_extract_requirements(
            listing_text, attachments, opp, opp_dir,
            channel, thread_ts, knowledge_base, rag_context)

        # Phase 4.5: Alignment assessment
        alignment_md = phase_alignment_assessment(
            requirements_md, opp, opp_dir, knowledge_base, rag_context,
            channel, thread_ts)

        # Phase 5: Build proposal outline & compliance plan
        outline_md = phase_build_outline(
            requirements_md, opp, opp_dir, knowledge_base, rag_context,
            channel, thread_ts, alignment_md=alignment_md)

        # Phase 6: Draft response (guided by outline)
        draft_md = phase_draft_response(
            requirements_md, outline_md, rag_context, opp, opp_dir,
            channel, thread_ts, alignment_md=alignment_md)

        # Phase 6.5: 4-pass multi-perspective review
        draft_md = phase_review_and_revise(
            draft_md, outline_md, requirements_md, opp, opp_dir,
            channel, thread_ts, alignment_md=alignment_md, rag_context=rag_context)

        # Phase 6.75: Solicitation compliance check
        draft_md = phase_compliance_check(
            draft_md, requirements_md, opp, opp_dir,
            channel, thread_ts, alignment_md=alignment_md)

        # Phase 7: Build submission checklist
        checklist_md = phase_build_checklist(
            requirements_md, outline_md, draft_md, opp, opp_dir,
            channel, thread_ts)

        # Phase 7.5: Format polish
        draft_md = phase_format_polish(
            draft_md, opp, opp_dir, channel, thread_ts)

        # Phase 8: Deliver outputs
        phase_deliver(opp, opp_dir, drive_folder_id, channel, thread_ts)

        elapsed = time.monotonic() - t0
        log.info(f"RFP Response Agent completed in {elapsed:.1f}s")

    except Exception as e:
        log.error(f"RFP Response Agent failed: {e}", exc_info=True)
        slack_reply(channel, thread_ts,
                    f"❌ RFP Response Agent encountered an error: {e}\n"
                    f"_Partial outputs may be available at: {opp_dir}_")
        report_progress("error", "error", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
