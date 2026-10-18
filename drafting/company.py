"""The company facts the prompts and templates fill in, from drafting/company.yaml."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

PROFILE_PATH = Path(__file__).resolve().parent / "company.yaml"


@lru_cache(maxsize=1)
def profile() -> dict[str, str]:
    data = yaml.safe_load(PROFILE_PATH.read_text(encoding="utf-8")) or {}
    return {str(key): "" if value is None else str(value) for key, value in data.items()}
