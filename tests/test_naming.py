"""The collection of past proposals is the Proposal Library everywhere. The old name survives
only in reference/, which is read-only prior art."""
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "node_modules", ".next", "data", "reference", "__pycache__", ".pytest_cache"}
OLD_NAME = re.compile("cor" + "pus", re.IGNORECASE)


def test_the_old_name_is_gone() -> None:
    hits = []
    for folder, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            path = Path(folder) / name
            if path.suffix in {".png", ".jpg", ".ico", ".db", ".pyc", ".woff", ".woff2"}:
                continue
            if OLD_NAME.search(name) or OLD_NAME.search(path.read_text(encoding="utf-8", errors="ignore")):
                hits.append(str(path.relative_to(ROOT)))
    assert hits == [], hits
