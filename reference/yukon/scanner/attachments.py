"""
Yukon — SAM.gov attachment downloader and text extractor.

Downloads the most relevant attachments (SOW/PWS/RFP) for filtered opportunities,
extracts text content, and enriches opp dicts with an `attachment_text` field
for use in AI review and scoring.
"""

import logging
import os
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

log = logging.getLogger(__name__)

MAX_PER_OPP = int(os.environ.get("YUKON_SAM_MAX_ATTACHMENTS_PER_OPP", "2"))
MAX_TOTAL_DOWNLOADS = int(os.environ.get("YUKON_SAM_MAX_ATTACHMENT_DOWNLOADS", "400"))
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
DOWNLOAD_TIMEOUT = 60
TEXT_LIMIT = 8000

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "attachments"

TIER1_PATTERNS = [
    r"\bsow\b", r"\bpws\b", r"\brfp\b", r"\brfq\b", r"\brfi\b",
    r"statement\s+of\s+work", r"performance\s+work\s+statement",
    r"\bscope\b", r"\bdescription\b", r"solicitation",
    r"\bsynopsis\b", r"requirement", r"section\s+c\b", r"section\s+j\b",
    r"\btechnical\b",
]

TIER2_PATTERNS = [
    r"\bsf[\s-]", r"standard\s+form", r"\bamendment\b", r"\bmodification\b",
    r"wage\s+determination", r"\bfar\b", r"\bdfar", r"\bclause\b",
    r"\bcertification\b", r"\brepresentation\b", r"\btemplate\b",
    r"\binstruction", r"\bpricing\b", r"\bclin\b", r"bid\s+schedule",
    r"\bresume\b", r"\bquestionnaire\b", r"\bdd[\s-]form", r"\bdd-\d",
]

_TIER1_RE = [re.compile(p, re.IGNORECASE) for p in TIER1_PATTERNS]
_TIER2_RE = [re.compile(p, re.IGNORECASE) for p in TIER2_PATTERNS]


def _score_attachment(name: str) -> Tuple[int, str]:
    """Score an attachment name. Higher = more likely to be the primary document.
    Returns (score, reason). Tier 2 (skip) is checked first so that standard
    forms matching a Tier 1 keyword (e.g. 'SF-1449 Solicitation') are still skipped."""
    for pat in _TIER2_RE:
        if pat.search(name):
            return (0, f"Tier 2 skip: {pat.pattern}")
    for pat in _TIER1_RE:
        if pat.search(name):
            return (2, f"Tier 1 match: {pat.pattern}")
    return (1, "No keyword match — fallback candidate")


def _is_extractable(name: str) -> bool:
    lower = name.lower()
    return lower.endswith(".pdf") or lower.endswith(".docx") or lower.endswith(".doc")


def _rank_attachments(resource_links: List[Dict]) -> List[Dict]:
    """Rank attachments by relevance. Returns sorted list (best first),
    filtered to extractable file types only."""
    scored = []
    for res in resource_links:
        name = res.get("name", "") or ""
        link = res.get("link", "") or ""
        if not link:
            continue
        if not _is_extractable(name) and not _is_extractable(link):
            continue
        score, reason = _score_attachment(name)
        scored.append((score, name, link, reason))

    scored.sort(key=lambda x: -x[0])

    if not scored:
        for res in resource_links:
            name = res.get("name", "") or ""
            link = res.get("link", "") or ""
            if not link:
                continue
            score, reason = _score_attachment(name)
            if score > 0:
                scored.append((score, name, link, reason))
        scored.sort(key=lambda x: -x[0])

    return [{"name": s[1], "link": s[2], "reason": s[3]} for s in scored]


def _download_file(link: str, dest_dir: Path, name: str, api_key: str) -> Optional[Path]:
    """Download a single attachment. Retries on 429 with backoff. Returns file path or None."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r'[^\w\-.]', '_', name or "attachment")[:100]
    if not safe_name:
        safe_name = "attachment"
    dest_path = dest_dir / safe_name

    sep = "&" if "?" in link else "?"
    url = f"{link}{sep}api_key={api_key}"

    max_retries = 3
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT)
            if resp.status_code == 429:
                if attempt < max_retries:
                    wait = 2 ** attempt * 10
                    log.warning(f"Attachment 429 rate-limited for {name}, retrying in {wait}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait)
                    continue
                log.warning(f"Attachment 429 rate-limited for {name}, exhausted retries")
                return None
            if resp.status_code != 200:
                log.warning(f"Attachment download failed ({resp.status_code}): {name}")
                return None

            content_length = int(resp.headers.get("Content-Length", 0))
            if content_length > MAX_FILE_BYTES:
                log.info(f"Attachment too large ({content_length / 1024 / 1024:.1f}MB), skipping: {name}")
                return None

            downloaded = 0
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    downloaded += len(chunk)
                    if downloaded > MAX_FILE_BYTES:
                        log.info(f"Attachment exceeded {MAX_FILE_BYTES / 1024 / 1024:.0f}MB during download, truncating: {name}")
                        break
                    f.write(chunk)

            return dest_path
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                log.warning(f"Attachment download timeout for {name}, retrying (attempt {attempt + 1}/{max_retries})")
                continue
            log.warning(f"Attachment download timeout for {name}, exhausted retries")
            return None
        except Exception as e:
            log.warning(f"Attachment download error for {name}: {e}")
            return None


def _extract_text(file_path: Path) -> str:
    """Extract text from a PDF or DOCX file."""
    suffix = file_path.suffix.lower()
    try:
        if suffix == ".pdf":
            import fitz
            text_parts = []
            with fitz.open(str(file_path)) as doc:
                for page in doc:
                    text_parts.append(page.get_text())
            return "\n".join(text_parts)[:TEXT_LIMIT]
        elif suffix in (".docx", ".doc"):
            import docx
            doc = docx.Document(str(file_path))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            return text[:TEXT_LIMIT]
    except Exception as e:
        log.warning(f"Text extraction failed for {file_path.name}: {e}")
    return ""


def enrich_with_attachments(opps: List[Dict], api_keys: List[str]) -> None:
    """Download and extract text from top-ranked attachments for each opp.
    Modifies opp dicts in-place, adding `attachment_text` and `_attachment_paths`."""
    sam_opps = [o for o in opps if o.get("portal") == "SAM.gov" and o.get("resource_links")]
    if not sam_opps:
        log.info("ATTACHMENTS: no SAM.gov opps with resource_links to process")
        return

    if not api_keys:
        log.warning("ATTACHMENTS: no API key available, skipping attachment downloads")
        return
    api_key_idx = 0
    api_key = api_keys[api_key_idx]
    if len(api_keys) > 1:
        log.info(f"ATTACHMENTS: {len(api_keys)} API keys available for downloads")

    total_downloads = 0
    t0 = time.monotonic()

    for opp in sam_opps:
        if total_downloads >= MAX_TOTAL_DOWNLOADS:
            log.warning(f"ATTACHMENTS: hit global download budget ({MAX_TOTAL_DOWNLOADS}), stopping")
            break

        notice_id = opp.get("id", "unknown")
        resource_links = opp.get("resource_links", [])
        ranked = _rank_attachments(resource_links)

        if not ranked:
            log.debug(f"ATTACHMENTS [{notice_id}]: no extractable attachments found "
                      f"({len(resource_links)} total links)")
            continue

        to_download = ranked[:MAX_PER_OPP]
        remaining_budget = MAX_TOTAL_DOWNLOADS - total_downloads
        to_download = to_download[:remaining_budget]

        dest_dir = DATA_DIR / notice_id
        paths = []
        texts = []

        for att in to_download:
            log.info(f"ATTACHMENTS [{notice_id}]: downloading '{att['name']}' ({att['reason']})")
            time.sleep(0.1)
            path = _download_file(att["link"], dest_dir, att["name"], api_key)
            total_downloads += 1
            if path:
                paths.append(path)
                text = _extract_text(path)
                if text:
                    texts.append(text)
                    log.info(f"ATTACHMENTS [{notice_id}]: extracted {len(text)} chars from '{att['name']}'")

        if texts:
            opp["attachment_text"] = "\n\n---\n\n".join(texts)
        opp["_attachment_paths"] = [str(p) for p in paths]

    elapsed = time.monotonic() - t0
    enriched = sum(1 for o in sam_opps if o.get("attachment_text"))
    log.info(f"ATTACHMENTS: {enriched}/{len(sam_opps)} opps enriched, "
             f"{total_downloads} files downloaded ({elapsed:.1f}s)")


def cleanup_rejected(opps: List[Dict]) -> None:
    """Delete downloaded attachment files for rejected opps."""
    for opp in opps:
        notice_id = opp.get("id", "")
        opp_dir = DATA_DIR / notice_id
        if opp_dir.exists():
            try:
                shutil.rmtree(opp_dir)
                log.debug(f"ATTACHMENTS: cleaned up files for rejected opp {notice_id}")
            except Exception as e:
                log.warning(f"ATTACHMENTS: cleanup failed for {notice_id}: {e}")
        opp.pop("_attachment_paths", None)
