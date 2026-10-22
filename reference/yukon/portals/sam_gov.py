"""
Yukon — SAM.gov portal adapter
Fetches all active opportunities from the SAM.gov Opportunities API v2.

Queries by (ptype × NAICS) combinations with rdlfrom=today to find all opps
with response deadlines still open. SAM.gov ncode only accepts single NAICS
codes, so each NAICS is queried separately and results are deduped.
"""

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import re

import requests
import urllib3.util.connection
urllib3.util.connection.HAS_IPV6 = False

from scanner.checkpoint import clear_checkpoint, expire_checkpoints, load_checkpoint, save_checkpoint

log = logging.getLogger(__name__)

SAM_API_BASE = "https://api.sam.gov/opportunities/v2/search"
PAGE_SIZE = 1000
MAX_PAGES_PER_TYPE = int(os.environ.get("YUKON_SAM_MAX_PAGES", "2"))
DAILY_QUOTA = 1000
QUOTA_RESERVE = 50
_requests_used = 0
REQUEST_TIMEOUT = int(os.environ.get("YUKON_SAM_REQUEST_TIMEOUT", "120"))

_exhausted_keys: set = set()
_exhausted_lock = threading.Lock()

_resume_loaded: bool = False
_resume_skipped_ptypes: List[str] = []
_resume_cleared: bool = False

PTYPES = [
    ("s", "SBIR/STTR"),
    ("r", "Sources Sought"),
    ("o", "Solicitation"),
    ("p", "Pre-solicitation"),
    ("k", "Combined Synopsis"),
]

CHECKPOINT_NAMESPACE = "sam_gov"


def _load_api_keys(primary: str = None) -> List[str]:
    keys = []
    k1 = primary or os.environ.get("SAM_GOV_API_KEY", "")
    if k1:
        keys.append(k1)
    env_path = os.path.join(os.path.dirname(__file__), "..", "..", "configs", "velocity", ".env")
    env_path = os.path.normpath(env_path)
    if os.path.exists(env_path):
        for line in open(env_path).read().splitlines():
            line = line.strip()
            if line.startswith("SAM_GOV_API_KEY") and "=" in line:
                val = line.split("=", 1)[1].strip()
                if val and val not in keys:
                    keys.append(val)
    seen = set()
    result = []
    for k in keys:
        if k not in seen:
            seen.add(k)
            result.append(k)
    return result


def _active_ptypes() -> List[Tuple[str, str]]:
    ptype_filter = os.environ.get("YUKON_SAM_PTYPES", "").strip().lower()
    if ptype_filter:
        allowed = {c.strip() for c in ptype_filter.split(",")}
        active = [(c, l) for c, l in PTYPES if c in allowed]
        if not active:
            log.warning(f"SAM.gov: YUKON_SAM_PTYPES={ptype_filter!r} matched none, using all ptypes")
            return list(PTYPES)
        log.info(f"SAM.gov debug: filtering to ptypes {[l for _, l in active]}")
        return active
    return list(PTYPES)


def _checkpoint_key(rdl_from: str, naics_str: str) -> str:
    ptypes = "-".join(code for code, _ in _active_ptypes())
    return f"active_{rdl_from}_{naics_str}_{ptypes}_pages{MAX_PAGES_PER_TYPE}"


def _load_resume_state(enabled: bool, rdl_from: str, naics_str: str) -> Tuple[Optional[dict], str]:
    key = _checkpoint_key(rdl_from, naics_str)
    if not enabled:
        return None, key
    state = load_checkpoint(CHECKPOINT_NAMESPACE, key)
    if state:
        finished = state.get("completed_ptypes", [])
        offsets = state.get("ptype_offsets", {})
        log.info(
            "SAM.gov resume: loaded checkpoint %s, completed=%s, offsets=%s",
            key,
            finished,
            offsets,
        )
    else:
        log.info("SAM.gov resume: no checkpoint found for %s, starting fresh", key)
    return state, key


def fetch(
    profile_naics: List[str],
    api_key: str = None,
    resume: bool = False,
    reset_checkpoint: bool = False,
) -> List[Dict]:
    global _resume_loaded, _resume_skipped_ptypes, _resume_cleared
    _resume_loaded = False
    _resume_skipped_ptypes = []
    _resume_cleared = False

    api_keys = _load_api_keys(api_key)
    if not api_keys:
        log.error("No SAM.gov API keys configured, skipping SAM.gov")
        return []
    if len(api_keys) > 1:
        log.info(f"SAM.gov: {len(api_keys)} API keys available (will rotate on quota hit)")

    now = datetime.now(timezone.utc)
    rdl_from = now.strftime("%m/%d/%Y")
    posted_from = (now - timedelta(days=364)).strftime("%m/%d/%Y")
    posted_to = now.strftime("%m/%d/%Y")
    naics_codes = list(profile_naics) if profile_naics else []
    naics_param = ",".join(naics_codes)
    active_ptypes = _active_ptypes()
    sequential = os.environ.get("YUKON_SAM_SEQUENTIAL", "").strip() == "1"
    mode = "sequential" if sequential else "parallel"

    if resume:
        expired = expire_checkpoints(CHECKPOINT_NAMESPACE, max_age_days=7)
        if expired:
            log.info(f"SAM.gov resume: expired {len(expired)} stale checkpoint(s) older than 7 days")

    checkpoint_state, checkpoint_key = _load_resume_state(resume, rdl_from, naics_param)
    if checkpoint_state is not None:
        _resume_loaded = True
    if reset_checkpoint:
        clear_checkpoint(CHECKPOINT_NAMESPACE, checkpoint_key)
        checkpoint_state = None
        log.info("SAM.gov resume: cleared checkpoint %s", checkpoint_key)

    # Build work units: (ptype, naics) combos — SAM.gov ncode only accepts single codes
    if naics_codes:
        work_units = [
            (ptype_code, ptype_label, naics)
            for ptype_code, ptype_label in active_ptypes
            for naics in naics_codes
        ]
    else:
        work_units = [
            (ptype_code, ptype_label, "")
            for ptype_code, ptype_label in active_ptypes
        ]

    estimated_needed = len(work_units) * MAX_PAGES_PER_TYPE
    if _requests_used + estimated_needed > DAILY_QUOTA - QUOTA_RESERVE:
        log.warning(
            f"SAM.gov quota guard: {_requests_used} requests used today, "
            f"estimated {estimated_needed} needed but only {DAILY_QUOTA - QUOTA_RESERVE - _requests_used} safe to use. "
            f"Skipping SAM.gov scan to preserve quota for tonight's nightly run."
        )
        return []

    naics_display = f" | NAICS: {naics_param}" if naics_param else ""
    log.info(
        f"SAM.gov: active opps (deadline >= {rdl_from}){naics_display} | "
        f"{len(active_ptypes)} types × {len(naics_codes) or 1} NAICS = {len(work_units)} queries ({mode})"
    )

    seen_ids = set()
    all_opps: List[Dict] = []
    checkpoint_lock = threading.Lock()
    completed_units = set((checkpoint_state or {}).get("completed_ptypes", []))
    unit_offsets = dict((checkpoint_state or {}).get("ptype_offsets", {}))
    partial_results = dict((checkpoint_state or {}).get("partial_results", {}))

    for cached_items in partial_results.values():
        for opp in cached_items:
            opp_id = opp.get("id")
            if opp_id and opp_id not in seen_ids:
                seen_ids.add(opp_id)
                all_opps.append(opp)

    def _persist_checkpoint() -> None:
        if not resume:
            return
        payload = {
            "posted_from": posted_from,
            "posted_to": posted_to,
            "rdl_from": rdl_from,
            "naics_param": naics_param,
            "completed_ptypes": sorted(completed_units),
            "ptype_offsets": unit_offsets,
            "partial_results": partial_results,
        }
        save_checkpoint(CHECKPOINT_NAMESPACE, checkpoint_key, payload)

    def _unit_key(ptype_code: str, naics: str) -> str:
        return f"{ptype_code}:{naics}" if naics else ptype_code

    def _collect(label: str, key: str, opps: List[Dict], completed: bool, next_offset: int = 0):
        added = 0
        for opp in opps:
            if opp.get("id") and opp["id"] not in seen_ids:
                seen_ids.add(opp["id"])
                all_opps.append(opp)
                added += 1
        if resume:
            with checkpoint_lock:
                partial_results[key] = opps
                if completed:
                    completed_units.add(key)
                    unit_offsets.pop(key, None)
                else:
                    unit_offsets[key] = next_offset
                _persist_checkpoint()
        status = "complete" if completed else f"partial, next offset={next_offset}"
        log.info(f"SAM.gov [{label}]: {added} unique records added ({status})")

    remaining = [
        (pc, pl, n) for pc, pl, n in work_units
        if _unit_key(pc, n) not in completed_units
    ]
    if resume and completed_units:
        _resume_skipped_ptypes = sorted(completed_units)
        log.info(f"SAM.gov resume: skipping completed units {_resume_skipped_ptypes}")
    if not remaining:
        log.info("SAM.gov resume: all work units already complete, returning checkpointed results")
        return all_opps

    if sequential:
        for ptype_code, ptype_label, naics in remaining:
            ukey = _unit_key(ptype_code, naics)
            label = f"{ptype_label}/{naics}" if naics else ptype_label
            try:
                start_offset = int(unit_offsets.get(ukey, 0)) if resume else 0
                if start_offset:
                    log.info(f"SAM.gov resume [{label}]: resuming at offset={start_offset}")
                opps, completed, next_offset = _fetch_ptype(
                    api_keys=api_keys,
                    ptype=ptype_code,
                    ptype_label=label,
                    posted_from=posted_from,
                    posted_to=posted_to,
                    rdl_from=rdl_from,
                    naics_param=naics,
                    start_offset=start_offset,
                )
                _collect(label, ukey, opps, completed, next_offset)
            except Exception as e:
                log.error(f"SAM.gov [{label}] error: {e}")
                if resume:
                    _persist_checkpoint()
    else:
        with ThreadPoolExecutor(max_workers=min(len(remaining), 4)) as executor:
            futures = {}
            for ptype_code, ptype_label, naics in remaining:
                ukey = _unit_key(ptype_code, naics)
                label = f"{ptype_label}/{naics}" if naics else ptype_label
                futures[executor.submit(
                    _fetch_ptype,
                    api_keys=api_keys,
                    ptype=ptype_code,
                    ptype_label=label,
                    posted_from=posted_from,
                    posted_to=posted_to,
                    rdl_from=rdl_from,
                    naics_param=naics,
                    start_offset=int(unit_offsets.get(ukey, 0)) if resume else 0,
                )] = (ukey, label)
            for future in as_completed(futures):
                ukey, label = futures[future]
                try:
                    opps, completed, next_offset = future.result()
                    _collect(label, ukey, opps, completed, next_offset)
                except Exception as e:
                    log.error(f"SAM.gov [{label}] thread error: {e}")
                    if resume:
                        _persist_checkpoint()

    if resume and len(completed_units) == len(work_units):
        clear_checkpoint(CHECKPOINT_NAMESPACE, checkpoint_key)
        _resume_cleared = True
        log.info(f"SAM.gov resume: checkpoint cleared after successful completion ({checkpoint_key})")

    log.info(f"SAM.gov: {len(all_opps)} total unique opportunities fetched")
    log.info(f"SAM.gov: {_requests_used} total API requests used this session")

    _fetch_descriptions(all_opps, api_keys)

    return all_opps


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&#\d+;", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _fetch_single_desc(opp: Dict, api_keys: List[str]) -> None:
    desc_url = opp.get("description", "")
    if not desc_url.startswith("https://api.sam.gov/"):
        return
    for api_key in api_keys:
        try:
            resp = requests.get(desc_url, params={"api_key": api_key}, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                raw_html = data.get("description", "")
                if raw_html:
                    opp["description"] = _strip_html(raw_html)[:4000]
                    return
            elif resp.status_code == 429:
                log.debug(f"SAM.gov desc fetch: 429 on key ...{api_key[-4:]}, trying next key")
                continue
            else:
                log.debug(f"SAM.gov desc fetch: HTTP {resp.status_code} for {opp.get('title', '')[:40]}")
        except Exception as e:
            log.warning(f"SAM.gov desc fetch failed for '{opp.get('title', '')[:40]}': {e}")
    log.warning(f"SAM.gov: could not fetch description for '{opp.get('title', '')[:40]}' (all keys exhausted)")


def _fetch_descriptions(opps: List[Dict], api_keys: List[str]) -> None:
    to_fetch = [o for o in opps if o.get("description", "").startswith("https://api.sam.gov/")]
    if not to_fetch:
        return
    if not api_keys:
        log.warning("SAM.gov: no API keys available for description fetching")
        return
    log.info(f"SAM.gov: fetching descriptions for {len(to_fetch)} opportunities...")
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(_fetch_single_desc, opp, api_keys) for opp in to_fetch]
        for f in as_completed(futures):
            f.result()
    fetched = sum(1 for o in to_fetch if not o.get("description", "").startswith("https://"))
    elapsed = time.monotonic() - t0
    log.info(f"SAM.gov: fetched {fetched}/{len(to_fetch)} descriptions ({elapsed:.1f}s)")


def _next_live_key(api_keys: List[str], start: int, ptype_label: str) -> int:
    idx = start
    while idx < len(api_keys):
        with _exhausted_lock:
            if api_keys[idx] not in _exhausted_keys:
                return idx
        log.info(f"SAM.gov [{ptype_label}]: skipping key #{idx + 1} (previously exhausted this run)")
        idx += 1
    return idx


def _mark_exhausted(api_key: str) -> None:
    with _exhausted_lock:
        _exhausted_keys.add(api_key)


def _fetch_ptype(
    api_keys: List[str],
    ptype: str,
    ptype_label: str,
    posted_from: str,
    posted_to: str,
    rdl_from: str,
    naics_param: str,
    start_offset: int = 0,
) -> Tuple[List[Dict], bool, int]:
    results = []
    offset = start_offset
    key_index = _next_live_key(api_keys, 0, ptype_label)
    completed = False
    pages_attempted = 0

    def current_key():
        return api_keys[key_index] if key_index < len(api_keys) else None

    max_pages = MAX_PAGES_PER_TYPE
    while pages_attempted < max_pages:
        if current_key() is None:
            log.error(f"SAM.gov [{ptype_label}]: all API keys exhausted, stopping")
            break

        params = {
            "api_key": current_key(),
            "limit": PAGE_SIZE,
            "offset": offset,
            "postedFrom": posted_from,
            "postedTo": posted_to,
            "rdlfrom": rdl_from,
            "ptype": ptype,
            "sortBy": "-modifiedDate",
        }
        if naics_param:
            params["ncode"] = naics_param

        try:
            log.info(f"SAM.gov [{ptype_label}]: page {(offset // PAGE_SIZE) + 1} (offset={offset})")
            global _requests_used
            _requests_used += 1
            t0 = time.monotonic()
            resp = requests.get(SAM_API_BASE, params=params, timeout=REQUEST_TIMEOUT)
            elapsed = time.monotonic() - t0
            log.info(
                f"SAM.gov [{ptype_label}] request: key={key_index+1}/{len(api_keys)} "
                f"status={resp.status_code} elapsed={elapsed:.1f}s (req #{_requests_used})"
            )
            if resp.status_code == 429:
                retry_header = resp.headers.get("Retry-After", "86400")
                log.warning(f"SAM.gov [{ptype_label}]: key #{key_index + 1} quota exhausted (Retry-After: {retry_header})")
                _mark_exhausted(api_keys[key_index])
                key_index = _next_live_key(api_keys, key_index + 1, ptype_label)
                if current_key() is not None:
                    log.info(f"SAM.gov [{ptype_label}]: rotating to key #{key_index + 1} of {len(api_keys)}")
                    params["api_key"] = current_key()
                    _requests_used += 1
                    t0 = time.monotonic()
                    resp = requests.get(SAM_API_BASE, params=params, timeout=REQUEST_TIMEOUT)
                    elapsed = time.monotonic() - t0
                    log.info(
                        f"SAM.gov [{ptype_label}] retry: key={key_index+1}/{len(api_keys)} "
                        f"status={resp.status_code} elapsed={elapsed:.1f}s"
                    )
                    if resp.status_code == 429:
                        log.error(f"SAM.gov [{ptype_label}]: key #{key_index + 1} also quota-exhausted, stopping")
                        _mark_exhausted(api_keys[key_index])
                        raise requests.RequestException("All API keys quota-exhausted")
                else:
                    log.error(f"SAM.gov [{ptype_label}]: no more API keys to rotate to, stopping")
                    raise requests.RequestException(f"All {len(api_keys)} API keys quota-exhausted")
            resp.raise_for_status()
            data = resp.json()
        except requests.Timeout:
            log.warning(f"SAM.gov [{ptype_label}]: page {(offset // PAGE_SIZE) + 1} timed out, stopping")
            break
        except requests.RequestException as e:
            log.error(f"SAM.gov [{ptype_label}] API error: {e}")
            break
        except Exception as e:
            log.error(f"SAM.gov [{ptype_label}] unexpected error: {e}")
            break

        opps_raw = data.get("opportunitiesData", [])
        total = data.get("totalRecords", 0)
        log.info(f"SAM.gov [{ptype_label}]: {len(opps_raw)} records (page {(offset // PAGE_SIZE) + 1}, {total} total)")

        for raw in opps_raw:
            results.append(_normalize(raw))

        pages_attempted += 1
        offset += PAGE_SIZE
        if offset >= total or len(opps_raw) < PAGE_SIZE:
            log.info(f"SAM.gov [{ptype_label}]: pagination complete")
            completed = True
            break
        if pages_attempted >= max_pages:
            log.info(f"SAM.gov [{ptype_label}]: page budget ({max_pages}) reached, treating as complete for this run")
            completed = True
            break

    log.info(f"SAM.gov [{ptype_label}]: {len(results)} records fetched total")
    return results, completed, offset


def _normalize(raw: Dict) -> Dict:
    notice_id = raw.get("noticeId", "")
    title = raw.get("title", "No Title")
    description = raw.get("description") or raw.get("synopsis") or ""

    naics_code = ""
    naics_raw = raw.get("naicsCode", [])
    if isinstance(naics_raw, list) and naics_raw:
        first = naics_raw[0]
        naics_code = str(first.get("naicsCode", "")) if isinstance(first, dict) else str(first)
    elif isinstance(naics_raw, str):
        naics_code = naics_raw

    set_aside = raw.get("typeOfSetAsideDescription") or raw.get("typeOfSetAside") or ""
    posted_date = raw.get("postedDate", "")
    due_date = raw.get("responseDeadLine") or raw.get("archiveDate") or ""

    if posted_date and "T" in str(posted_date):
        posted_date = posted_date.split("T")[0]
    if due_date and "T" in str(due_date):
        due_date = due_date.split("T")[0]

    type_map = {
        "o": "Solicitation",
        "p": "Pre-solicitation",
        "k": "Combined Synopsis",
        "r": "Sources Sought",
        "s": "SBIR/STTR",
        "g": "Sale of Surplus",
        "i": "Intent to Bundle",
        "a": "Award Notice",
        "u": "Justification",
        "m": "Modification",
    }
    ptype = str(raw.get("type") or raw.get("opportunityType") or "").lower()
    opp_type = type_map.get(ptype, ptype.capitalize() or "Opportunity")

    department = raw.get("fullParentPathName", "")
    if not department:
        org_hier = raw.get("organizationHierarchy", [])
        if isinstance(org_hier, list) and org_hier:
            department = org_hier[0].get("name", "")

    return {
        "id": notice_id,
        "title": title,
        "url": f"https://sam.gov/opp/{notice_id}/view" if notice_id else "https://sam.gov",
        "portal": "SAM.gov",
        "naics_code": naics_code,
        "set_aside": set_aside,
        "posted_date": posted_date,
        "due_date": due_date,
        "description": description,
        "type": opp_type,
        "department": department,
        "resource_links": [
            r if isinstance(r, dict) else {"name": r.rsplit("/", 1)[-1], "link": r}
            for r in (raw.get("resourceLinks") or [])
        ],
    }
