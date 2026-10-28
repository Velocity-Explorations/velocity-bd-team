"""Each draft ends with a slop check (PRO-510), using David's AI slop detection skill.

    report = run_scan(draft_path, solicitation_path)   # the skill's scanner, run as a subprocess
    gate = summarize(report)                            # the band, open placeholders by kind, ready or not
    text = render_report(gate, draft_path)              # slop_report.md beside the draft

The scanner lives outside this repo, in the skill's folder (or wherever AI_SLOP_SCAN points);
nothing of it is copied here. A draft is ready when no placeholder is open and the band is clean
or light. The bands stay provisional until the scanner is calibrated on 20 or more past
Velocity proposals.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from config import get

SCANNER_ENV = "AI_SLOP_SCAN"
DEFAULT_SCANNER = Path.home() / ".claude" / "skills" / "ai-slop-detection" / "scripts" / "slop_scan.py"
SCAN_TIMEOUT_S = 120
READY_BANDS = ("clean", "light")
NO_BAND = "unscored"   # the scanner's band under 150 words: findings are listed without one (PW21)
OPEN_FAMILY = "prop_open_item"
PLACEHOLDER_KINDS = [("PERSON WRITES", re.compile(r"^\[PERSON\s+WRITES", re.I)),
                     ("NEEDS INPUT", re.compile(r"^\[NEEDS?\s+INPUT", re.I)),
                     ("NEEDS EVIDENCE", re.compile(r"^\[NEEDS?\s+EVIDENCE", re.I))]
HOT_PARAGRAPHS = 5


class ScanError(RuntimeError):
    """The scanner is missing, failed or answered with something other than its JSON report."""


@dataclass(frozen=True)
class Gate:
    band: str
    calibrated: bool
    placeholders: dict[str, int]                                   # open placeholders by kind, in a fixed order
    families: list[str] = field(default_factory=list)              # what fired, surface habits left out
    hot: list[tuple[int, int, list[str]]] = field(default_factory=list)   # first and last line, families

    @property
    def ready(self) -> bool:
        return not any(self.placeholders.values()) and (self.band in READY_BANDS or self.band == NO_BAND)


def scanner_path() -> Path:
    configured = (get(SCANNER_ENV) or "").strip()
    return Path(configured) if configured else DEFAULT_SCANNER


def solicitation_text(inputs: Any) -> str:
    """The solicitation's own words: the listing and every attachment that has text."""
    parts = [inputs.listing_text or inputs.description or ""]
    parts += [f"[{a['name']}]\n{a['text']}" for a in inputs.attachments if (a.get("text") or "").strip()]
    return "\n\n".join(part for part in parts if part.strip())


def scan_file(draft: Path, solicitation: Path | None, scanner: Path | None = None) -> dict[str, Any]:
    """Run the skill's scanner on one draft with the proposal profile; its JSON report for that file."""
    scanner = scanner or scanner_path()
    if not scanner.exists():
        raise ScanError(f"slop scanner not found; install the ai-slop-detection skill or set {SCANNER_ENV}")
    command = [sys.executable, str(scanner), str(draft), "--profile", "proposal", "--json"]
    if solicitation is not None:
        command += ["--solicitation", str(solicitation)]
    try:
        done = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", timeout=SCAN_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        raise ScanError(f"slop scanner took longer than {SCAN_TIMEOUT_S} seconds") from exc
    if done.returncode != 0:
        raise ScanError(f"slop scanner failed: {(done.stderr or done.stdout).strip()[:300]}")
    try:
        return json.loads(done.stdout)[0]
    except (ValueError, IndexError, KeyError) as exc:
        raise ScanError("slop scanner did not return its JSON report") from exc


def run_scan(draft: Path, solicitation: Path | None, scanner: Path | None = None) -> dict[str, Any]:
    """The scan the pipeline and the check command run; tests stand in for it (tests/conftest.py)."""
    return scan_file(draft, solicitation, scanner)


def _kind(match: str) -> str:
    return next((name for name, pattern in PLACEHOLDER_KINDS if pattern.match(match)), "other")


def summarize(report: Mapping[str, Any]) -> Gate:
    placeholders = {name: 0 for name, _ in PLACEHOLDER_KINDS} | {"other": 0}
    for finding in report.get("findings") or []:
        if finding.get("family") == OPEN_FAMILY:
            placeholders[_kind(str(finding.get("match") or ""))] += 1
    families = [str(f.get("label") or name) for name, f in (report.get("families") or {}).items()
                if f.get("fired") and f.get("tier") != "surface" and name != OPEN_FAMILY]
    hot = []
    for paragraph in (report.get("hot_paragraphs") or [])[:HOT_PARAGRAPHS]:
        lines = paragraph.get("lines") or [0, 0]
        hot.append((int(lines[0]), int(lines[-1]), [str(f) for f in paragraph.get("families") or []]))
    return Gate(band=str(report.get("band") or "no band"), calibrated=bool((report.get("thresholds") or {}).get("calibrated")),
                placeholders=placeholders, families=families, hot=hot)


def verdict(gate: Gate) -> str:
    """"Ready: band light", or "Not ready: 1 PERSON WRITES, 37 NEEDS INPUT; band clean (provisional)". Under 150 words,
    "no band", and only the placeholders decide."""
    band = "no band" if gate.band == NO_BAND else f"band {gate.band}" + ("" if gate.calibrated else " (provisional)")
    if gate.ready:
        return f"Ready: {band}"
    open_items = ", ".join(f"{n} {kind}" for kind, n in gate.placeholders.items() if n)
    return f"Not ready: {open_items}; {band}" if open_items else f"Not ready: {band}"


def _lines(first: int, last: int) -> str:
    return f"Line {first}" if first == last else f"Lines {first} to {last}"


def render_report(gate: Gate, draft: Path) -> str:
    """slop_report.md: the verdict, then what to fix first."""
    out = ["# Slop check", "", verdict(gate), "",
           "The band comes from the AI slop detection skill's proposal checks. It stays provisional until the scanner "
           "is calibrated on 20 or more past Velocity proposals.", "", "## Open placeholders", ""]
    out += [f"- {n} {kind}" for kind, n in gate.placeholders.items() if n] or ["None."]
    out += ["", "## Paragraphs to revise first", ""]
    out += [f"- {_lines(first, last)}: {', '.join(families)}" for first, last, families in gate.hot] or ["None."]
    out += ["", "## What fired", ""]
    out += [f"- {label}" for label in gate.families] or ["Nothing beyond surface habits."]
    out += ["", f"After editing the draft, rerun: `python -m drafting.cli check --draft {draft}`", ""]
    return "\n".join(out)
