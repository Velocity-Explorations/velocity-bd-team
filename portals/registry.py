"""Portal discovery. Every package under portals/ that defines a PORTAL dict is a portal.

    PORTAL = {
        "slug": "vulcan_sof",            # used by run.py --portal and as runs.component
        "name": "Vulcan SOF",            # the calls.portal value
        "fetch": fn(page, run_id, limit=None) -> {"found", "scraped", "new", "failed"},
        "filter": fn(rows) -> (kept, rejected),
        "fetch_timeout": 300,            # seconds; the pipeline force-closes the browser after this
        "needs_browser": True,           # False: fetch is called with page=None
        "keywords": Path,                # optional: this portal's keywords.yaml
        "how_to_submit": "one line",     # optional: how a response is submitted
        "notes": Path,                   # optional: NOTES.md, what the assistant should know
    }

Adding a portal means adding a package; run.py never changes. portals/shared/ holds the
helpers adapters reuse (browser, saved sessions, emailed sign-in codes, keyword filter); it
defines no PORTAL, so discovery skips it.
"""
from __future__ import annotations

import importlib
import logging
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import portals

log = logging.getLogger("registry")

REQUIRED_KEYS = ("slug", "name", "fetch", "filter")


@dataclass(frozen=True)
class Portal:
    slug: str
    name: str
    fetch: Callable[..., dict[str, int]]
    filter: Callable[[list[dict[str, Any]]], tuple[list[Any], list[Any]]]
    fetch_timeout: int = 300
    needs_browser: bool = True
    keywords: Path | None = None
    how_to_submit: str = ""
    notes: Path | None = None


def _from_dict(spec: dict[str, Any], module_name: str) -> Portal:
    missing = [k for k in REQUIRED_KEYS if k not in spec]
    if missing:
        raise ValueError(f"{module_name}.PORTAL is missing {missing}")
    return Portal(
        slug=str(spec["slug"]),
        name=str(spec["name"]),
        fetch=spec["fetch"],
        filter=spec["filter"],
        fetch_timeout=int(spec.get("fetch_timeout", 300)),
        needs_browser=bool(spec.get("needs_browser", True)),
        keywords=Path(spec["keywords"]) if spec.get("keywords") else None,
        how_to_submit=str(spec.get("how_to_submit") or ""),
        notes=Path(spec["notes"]) if spec.get("notes") else None,
    )


def discover() -> list[Portal]:
    """Import every package under portals/ and collect the ones that define PORTAL."""
    found: list[Portal] = []
    for info in pkgutil.iter_modules(portals.__path__):
        if not info.ispkg:
            continue
        module_name = f"portals.{info.name}"
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            log.warning("Skipping %s: import failed (%s: %s)", module_name, type(exc).__name__, str(exc)[:120])
            continue
        spec = getattr(module, "PORTAL", None)
        if isinstance(spec, dict):
            found.append(_from_dict(spec, module_name))
    return sorted(found, key=lambda p: p.slug)


def get(slug: str) -> Portal:
    for portal in discover():
        if portal.slug == slug:
            return portal
    known = ", ".join(p.slug for p in discover()) or "(none)"
    raise KeyError(f"no portal with slug '{slug}'; known: {known}")
