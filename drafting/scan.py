"""The AI slop check on every new draft (PW12, PW20 to PW23, phase 8a).

    found = check(pursuit_id, step_id, work_dir / "draft_v1.md", solicitation)

First the fixes the worker makes on its own: the house rule's dashes, and tracking parameters left in
links. Then the private scanner (drafting/slop_gate.py, from AI_SLOP_SCAN) with the proposal profile and
the solicitation's own words exempt. The scan is kept in `slop_scans` with the verdict the page and Slack
show, beside the draft as slop_scan.json and slop_report.md; the page never runs the scanner. Without the
scanner nothing is kept, and the verdict says the check did not run. Everything here reports writing
patterns and their fixes only (PW23).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from drafting import slop_gate
from drafting.steps import count_dashes, fix_dashes
from ledger import queries as lq

URL = re.compile(r"https?://[^\s)\]>\"']+")
TRACKING = re.compile(r"^(utm_[a-z_]+|fbclid|gclid|dclid|msclkid|mc_cid|mc_eid|igshid)$", re.I)


def strip_tracking(text: str) -> tuple[str, int]:
    """Links without their tracking parameters, and how many were removed."""
    removed = 0

    def clean(match: re.Match[str]) -> str:
        nonlocal removed
        url = match.group(0)
        trailing = ""
        while url and url[-1] in ".,;:":
            url, trailing = url[:-1], url[-1] + trailing
        parts = urlsplit(url)
        if not parts.query:
            return match.group(0)
        pairs = parse_qsl(parts.query, keep_blank_values=True)
        kept = [(key, value) for key, value in pairs if not TRACKING.match(key)]
        if len(kept) == len(pairs):
            return match.group(0)
        removed += len(pairs) - len(kept)
        return urlunsplit(parts._replace(query=urlencode(kept))) + trailing

    return URL.sub(clean, text), removed


def fix_text(text: str) -> tuple[str, int]:
    """The fixes the worker makes before a scan: dashes replaced, tracking parameters removed; how many."""
    dashes = count_dashes(text)
    fixed, removed = strip_tracking(fix_dashes(text))
    return fixed, dashes + removed


def check(pursuit_id: int, step_id: int | None, draft: Path, solicitation: str) -> dict[str, Any]:
    """Fix a new draft where the worker can, scan it, and keep the scan. Returns the verdict, whether the draft
    is Ready (PW21), the band, the fixes made and the scan's id (None when the scanner did not run)."""
    text = draft.read_text(encoding="utf-8")
    fixed, count = fix_text(text)
    if count:
        draft.write_text(fixed, encoding="utf-8")
    source = None
    if solicitation.strip():
        source = draft.parent / "source" / "solicitation.txt"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(solicitation, encoding="utf-8")
    try:
        report = slop_gate.run_scan(draft, source)
    except slop_gate.ScanError as exc:
        return {"verdict": f"Not checked: {exc}", "ready": False, "band": None, "placeholders": {}, "fixed": count, "scan_id": None}
    gate = slop_gate.summarize(report)
    verdict = slop_gate.verdict(gate)
    scan_id = lq.save_slop_scan(pursuit_id, step_id, draft.name, report, verdict=verdict, ready=gate.ready, fixed_count=count,
                                text=fixed)
    (draft.parent / "slop_scan.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (draft.parent / "slop_report.md").write_text(slop_gate.render_report(gate, draft), encoding="utf-8")
    return {"verdict": verdict, "ready": gate.ready, "band": gate.band, "placeholders": dict(gate.placeholders), "fixed": count,
            "scan_id": scan_id}
