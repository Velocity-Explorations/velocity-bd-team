"""
Yukon — RFP Agent attachment downloader and text extractor.

Portal-aware module that downloads solicitation documents for a single opportunity,
extracts text, and uploads originals to Google Drive. SAM.gov supported first;
generic web scraping as fallback for other portals.
"""

import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests

log = logging.getLogger(__name__)

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB
DOWNLOAD_TIMEOUT = 60
MAX_ATTACHMENTS = 5
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "rfp-agent"
DRIVE_ACCOUNT = "david@velocityexplorations.com"

TIER1_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bsow\b", r"\bpws\b", r"\brfp\b", r"\brfq\b", r"\brfi\b",
        r"statement\s+of\s+work", r"performance\s+work\s+statement",
        r"\bscope\b", r"\bdescription\b", r"solicitation",
        r"\bsynopsis\b", r"requirement", r"section\s+c\b", r"section\s+j\b",
        r"\btechnical\b",
    ]
]

TIER2_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bsf[\s-]", r"standard\s+form", r"\bamendment\b", r"\bmodification\b",
        r"wage\s+determination", r"\bfar\b", r"\bdfar", r"\bclause\b",
        r"\bcertification\b", r"\brepresentation\b",
        r"\bresume\b", r"\bquestionnaire\b", r"\bdd[\s-]form", r"\bdd-\d",
    ]
]


def _score_attachment(name: str) -> int:
    for pat in TIER2_PATTERNS:
        if pat.search(name):
            return 0
    for pat in TIER1_PATTERNS:
        if pat.search(name):
            return 2
    return 1


def _safe_filename(name: str) -> str:
    safe = re.sub(r'[^\w\-.]', '_', name or "attachment")[:120]
    return safe or "attachment"


def _is_extractable(name: str) -> bool:
    lower = (name or "").lower()
    return any(lower.endswith(ext) for ext in (".pdf", ".docx", ".doc", ".pptx", ".xlsx"))


def extract_text(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    try:
        if suffix == ".pdf":
            import fitz
            parts = []
            with fitz.open(str(file_path)) as doc:
                for page in doc:
                    parts.append(page.get_text())
            return "\n".join(parts)
        elif suffix in (".docx", ".doc"):
            from docx import Document
            doc = Document(str(file_path))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        elif suffix == ".pptx":
            from pptx import Presentation
            prs = Presentation(str(file_path))
            parts = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        for para in shape.text_frame.paragraphs:
                            t = para.text.strip()
                            if t:
                                parts.append(t)
            return "\n".join(parts)
        elif suffix == ".xlsx":
            from openpyxl import load_workbook
            wb = load_workbook(str(file_path), read_only=True, data_only=True)
            parts = []
            for ws in wb.worksheets:
                for row in ws.iter_rows(values_only=True):
                    vals = [str(c) for c in row if c is not None]
                    if vals:
                        parts.append(" | ".join(vals))
            wb.close()
            return "\n".join(parts)
    except Exception as e:
        log.warning(f"Text extraction failed for {file_path.name}: {e}")
    return ""


def _download_file(url: str, dest_dir: Path, name: str, headers: dict = None) -> Optional[Path]:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / _safe_filename(name)

    try:
        resp = requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT, headers=headers or {})
        if resp.status_code != 200:
            log.warning(f"Download failed ({resp.status_code}): {name}")
            return None

        content_length = int(resp.headers.get("Content-Length", 0))
        if content_length > MAX_FILE_BYTES:
            log.info(f"File too large ({content_length / 1024 / 1024:.1f}MB), skipping: {name}")
            return None

        downloaded = 0
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                downloaded += len(chunk)
                if downloaded > MAX_FILE_BYTES:
                    log.info(f"File exceeded 10MB during download, truncating: {name}")
                    break
                f.write(chunk)

        return dest_path
    except Exception as e:
        log.warning(f"Download error for {name}: {e}")
        return None


def _upload_to_drive(local_path: Path, drive_folder_id: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["/opt/homebrew/bin/gog", "drive", "upload", str(local_path),
             "--parent", drive_folder_id, "-a", DRIVE_ACCOUNT, "-j"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            link = data.get("file", {}).get("webViewLink", "")
            log.info(f"Uploaded to Drive: {local_path.name}")
            return link
        else:
            log.warning(f"Drive upload failed: {result.stderr[:200]}")
    except Exception as e:
        log.warning(f"Drive upload error: {e}")
    return None


def _load_sam_api_key() -> str:
    key = os.environ.get("SAM_GOV_API_KEY", "")
    if key:
        return key
    env_path = Path(__file__).resolve().parent.parent / "configs" / "velocity" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("SAM_GOV_API_KEY") and "=" in line:
                return line.split("=", 1)[1].strip()
    return ""


def _load_rfp_agent_key() -> str:
    """Load the dedicated RFP agent API key (not used by nightly scanner)."""
    key = os.environ.get("SAM_GOV_RFP_AGENT_KEY", "")
    if key:
        return key
    env_path = Path(__file__).resolve().parent.parent / "configs" / "velocity" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("SAM_GOV_RFP_AGENT_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


SCANNER_ATTACHMENTS_DIR = Path(__file__).resolve().parent.parent / "data" / "attachments"


def load_cached_attachments(notice_id: str, drive_folder_id: str = None) -> List[Dict]:
    """Load attachments already cached by the nightly scanner."""
    cache_dir = SCANNER_ATTACHMENTS_DIR / notice_id
    if not cache_dir.exists():
        return []

    results = []
    for f in sorted(cache_dir.iterdir()):
        if not f.is_file() or f.stat().st_size == 0:
            continue
        if not _is_extractable(f.name) and f.suffix.lower() not in (".pdf", ".docx", ".doc", ".pptx", ".xlsx"):
            # Check if file is a PDF without proper extension (e.g. "download")
            try:
                with open(f, "rb") as fh:
                    header = fh.read(5)
                if header != b"%PDF-":
                    continue
            except Exception:
                continue

        text = extract_text(f)
        if not text and not f.suffix:
            try:
                import fitz
                with fitz.open(str(f)) as doc:
                    text = "\n".join(page.get_text() for page in doc)
            except Exception:
                pass

        drive_link = None
        if drive_folder_id:
            drive_link = _upload_to_drive(f, drive_folder_id)

        results.append({
            "name": f.name,
            "local_path": str(f),
            "text": text,
            "drive_link": drive_link,
            "score": _score_attachment(f.name),
            "source": "cache",
        })
        if text:
            log.info(f"Cached attachment: {f.name} ({len(text)} chars)")

    return results


def _download_with_filename(url: str, api_key: str, dest_dir: Path) -> Optional[tuple]:
    """Download a file, resolving the real filename from Content-Disposition.
    Returns (path, resolved_name) or None."""
    import urllib.parse
    sep = "&" if "?" in url else "?"
    full_url = f"{url}{sep}api_key={api_key}"
    try:
        resp = requests.get(full_url, stream=True, timeout=DOWNLOAD_TIMEOUT)
        if resp.status_code != 200:
            log.warning(f"Download failed ({resp.status_code}): {url[-60:]}")
            return None

        cd = resp.headers.get("Content-Disposition", "")
        if "filename=" in cd:
            name = cd.split("filename=", 1)[1].strip().strip('"')
            name = urllib.parse.unquote_plus(name)
        else:
            name = url.rsplit("/", 1)[-1] or "attachment"

        safe = _safe_filename(name)
        dest_path = dest_dir / safe

        content_length = int(resp.headers.get("Content-Length", 0))
        if content_length > MAX_FILE_BYTES:
            log.info(f"File too large ({content_length / 1024 / 1024:.1f}MB), skipping: {name}")
            return None

        downloaded = 0
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                downloaded += len(chunk)
                if downloaded > MAX_FILE_BYTES:
                    log.info(f"File exceeded limit during download, truncating: {name}")
                    break
                f.write(chunk)

        return dest_path, name
    except Exception as e:
        log.warning(f"Download error: {e}")
        return None


def download_all_sam_attachments(opp_url: str, dest_dir: Path = None,
                                 api_key: str = None) -> List[Dict]:
    """Download ALL attachments for a SAM.gov opp (no cap). Uses dedicated key by default."""
    key = api_key or _load_rfp_agent_key() or _load_sam_api_key()
    if not key:
        log.error("No SAM.gov API key available for full attachment download")
        return []

    notice_id = _extract_sam_notice_id(opp_url)
    if not notice_id:
        log.warning(f"Could not extract SAM.gov notice ID from URL: {opp_url}")
        return []

    if dest_dir is None:
        dest_dir = SCANNER_ATTACHMENTS_DIR / notice_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    listing = _fetch_sam_listing(notice_id, key)
    if not listing:
        log.warning(f"Could not fetch SAM.gov listing for {notice_id}")
        return []

    resource_links = listing.get("resourceLinks") or []
    if not resource_links:
        log.info(f"No resource links found for {notice_id}")
        return []

    links = []
    for r in resource_links:
        if isinstance(r, dict):
            links.append(r.get("link", "") or r.get("url", ""))
        elif isinstance(r, str):
            links.append(r)

    existing_files = {f.name for f in dest_dir.iterdir() if f.is_file() and f.stat().st_size > 0}

    results = []
    for link in links:
        if not link:
            continue

        # Check cache: we need to download to know the filename, but first
        # try a quick GET to resolve the name without saving
        dl_result = _download_with_filename(link, key, dest_dir)
        if not dl_result:
            continue
        path, name = dl_result
        safe_name = _safe_filename(name)

        if safe_name in existing_files and path.stat().st_size > 0:
            log.info(f"Already had cached copy: {safe_name}")

        existing_files.add(safe_name)

        text = extract_text(path) if _is_extractable(name) else ""
        results.append({
            "name": name, "local_path": str(path),
            "text": text, "score": _score_attachment(name),
            "source": "downloaded",
        })
        if text:
            log.info(f"Extracted {len(text)} chars from {name}")
        else:
            log.info(f"Saved: {name} ({path.stat().st_size} bytes)")

        time.sleep(0.3)

    return results


# ─── SAM.GOV ──────────────────────────────────────────────────────────────────

def _fetch_sam_listing(notice_id: str, api_key: str) -> Optional[Dict]:
    url = f"https://api.sam.gov/opportunities/v2/search"
    params = {
        "api_key": api_key,
        "noticeid": notice_id,
        "limit": 1,
    }
    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code != 200:
            log.warning(f"SAM.gov listing fetch failed: HTTP {resp.status_code}")
            return None
        data = resp.json()
        opps = data.get("opportunitiesData", [])
        if opps:
            return opps[0]
    except Exception as e:
        log.warning(f"SAM.gov listing fetch error: {e}")
    return None


def _extract_sam_notice_id(url: str) -> Optional[str]:
    m = re.search(r"sam\.gov/opp/([a-f0-9]+)/", url)
    return m.group(1) if m else None


def download_sam_attachments(opp_url: str, dest_dir: Path, drive_folder_id: str = None) -> List[Dict]:
    """Download attachments for a SAM.gov opportunity.

    Returns list of dicts: {name, local_path, text, drive_link}
    """
    api_key = _load_sam_api_key()
    if not api_key:
        log.error("No SAM.gov API key available")
        return []

    notice_id = _extract_sam_notice_id(opp_url)
    if not notice_id:
        log.warning(f"Could not extract SAM.gov notice ID from URL: {opp_url}")
        return []

    listing = _fetch_sam_listing(notice_id, api_key)
    if not listing:
        log.warning(f"Could not fetch SAM.gov listing for {notice_id}")
        return []

    resource_links = listing.get("resourceLinks") or []
    if not resource_links:
        log.info(f"No resource links found for {notice_id}")
        return []

    normalized = []
    for r in resource_links:
        if isinstance(r, dict):
            normalized.append(r)
        elif isinstance(r, str):
            normalized.append({"name": r.rsplit("/", 1)[-1], "link": r})

    scored = []
    for res in normalized:
        name = res.get("name", "") or ""
        link = res.get("link", "") or ""
        if not link:
            continue
        if not _is_extractable(name) and not _is_extractable(link):
            continue
        score = _score_attachment(name)
        scored.append((score, name, link))

    scored.sort(key=lambda x: -x[0])
    to_download = scored[:MAX_ATTACHMENTS]

    results = []
    for score, name, link in to_download:
        sep = "&" if "?" in link else "?"
        full_url = f"{link}{sep}api_key={api_key}"

        log.info(f"Downloading: {name} (score={score})")
        time.sleep(0.2)
        path = _download_file(full_url, dest_dir, name)
        if not path:
            continue

        text = extract_text(path)
        drive_link = None
        if drive_folder_id:
            drive_link = _upload_to_drive(path, drive_folder_id)

        results.append({
            "name": name,
            "local_path": str(path),
            "text": text,
            "drive_link": drive_link,
            "score": score,
        })
        if text:
            log.info(f"Extracted {len(text)} chars from {name}")

    return results


# ─── GENERIC WEB SCRAPER (future portals) ─────────────────────────────────────

def download_generic_attachments(opp_url: str, dest_dir: Path, drive_folder_id: str = None) -> List[Dict]:
    """Scrape a listing page for downloadable document links.
    Fallback for non-SAM.gov portals.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        log.warning("BeautifulSoup not available for generic scraping")
        return []

    try:
        resp = requests.get(opp_url, timeout=30)
        if resp.status_code != 200:
            log.warning(f"Page fetch failed ({resp.status_code}): {opp_url}")
            return []
    except Exception as e:
        log.warning(f"Page fetch error: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    doc_extensions = (".pdf", ".docx", ".doc", ".pptx", ".xlsx", ".xls")
    links = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if any(href.lower().endswith(ext) for ext in doc_extensions):
            name = a_tag.get_text(strip=True) or href.rsplit("/", 1)[-1]
            if not href.startswith("http"):
                from urllib.parse import urljoin
                href = urljoin(opp_url, href)
            score = _score_attachment(name)
            links.append((score, name, href))

    links.sort(key=lambda x: -x[0])
    to_download = links[:MAX_ATTACHMENTS]

    results = []
    for score, name, href in to_download:
        log.info(f"Downloading: {name} (score={score})")
        path = _download_file(href, dest_dir, name)
        if not path:
            continue

        text = extract_text(path)
        drive_link = None
        if drive_folder_id:
            drive_link = _upload_to_drive(path, drive_folder_id)

        results.append({
            "name": name,
            "local_path": str(path),
            "text": text,
            "drive_link": drive_link,
            "score": score,
        })

    return results


# ─── DISPATCHER ────────────────────────────────────────────────────────────────

def download_attachments(portal: str, opp_url: str, dest_dir: Path,
                         drive_folder_id: str = None) -> List[Dict]:
    """Download attachments for an opportunity, dispatching by portal type."""
    dest_dir.mkdir(parents=True, exist_ok=True)

    if portal and "sam" in portal.lower():
        return download_sam_attachments(opp_url, dest_dir, drive_folder_id)

    return download_generic_attachments(opp_url, dest_dir, drive_folder_id)


def scrape_listing_page(opp_url: str) -> str:
    """Fetch and extract text from a listing page."""
    portal = ""
    if "sam.gov" in opp_url:
        portal = "SAM.gov"
        notice_id = _extract_sam_notice_id(opp_url)
        if notice_id:
            api_key = _load_sam_api_key()
            if api_key:
                listing = _fetch_sam_listing(notice_id, api_key)
                if listing:
                    parts = []
                    parts.append(f"Title: {listing.get('title', '')}")
                    parts.append(f"Agency: {listing.get('fullParentPathName', '')}")
                    parts.append(f"Type: {listing.get('type', '')}")
                    parts.append(f"Posted: {listing.get('postedDate', '')}")
                    parts.append(f"Due: {listing.get('responseDeadLine', '')}")
                    parts.append(f"NAICS: {listing.get('naicsCode', '')}")
                    parts.append(f"Set-Aside: {listing.get('typeOfSetAsideDescription', '')}")
                    desc = listing.get("description", "")
                    if desc and desc.startswith("https://api.sam.gov/"):
                        try:
                            r = requests.get(desc, params={"api_key": api_key}, timeout=30)
                            if r.status_code == 200:
                                raw_html = r.json().get("description", "")
                                desc = re.sub(r"<[^>]+>", " ", raw_html).strip()
                        except Exception:
                            pass
                    parts.append(f"\nDescription:\n{desc}")
                    return "\n".join(parts)

    try:
        resp = requests.get(opp_url, timeout=30)
        if resp.status_code == 200:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                return soup.get_text(separator="\n", strip=True)[:20000]
            except ImportError:
                return resp.text[:20000]
    except Exception as e:
        log.warning(f"Listing page scrape error: {e}")

    return ""
