"""
Yukon checkpoint helpers.

Scope: minimal checkpoint/resume support for long-running portal fetches,
starting with SAM.gov. Stores small JSON files under data/checkpoints/.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHECKPOINT_DIR = PROJECT_ROOT / "data" / "checkpoints"


def _safe_name(value: str) -> str:
    value = value or "default"
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value)


def checkpoint_path(namespace: str, key: str) -> Path:
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    return CHECKPOINT_DIR / f"{_safe_name(namespace)}__{_safe_name(key)}.json"


def load_checkpoint(namespace: str, key: str) -> Dict[str, Any] | None:
    path = checkpoint_path(namespace, key)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def save_checkpoint(namespace: str, key: str, payload: Dict[str, Any]) -> Path:
    path = checkpoint_path(namespace, key)
    data = dict(payload)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    tmp.replace(path)
    return path


def clear_checkpoint(namespace: str, key: str) -> None:
    path = checkpoint_path(namespace, key)
    if path.exists():
        path.unlink()


def expire_checkpoints(namespace: str, max_age_days: int = 7) -> list[Path]:
    """Delete checkpoint files under namespace whose mtime is older than max_age_days.

    Returns the list of paths removed. Silent on missing dir.
    """
    if not CHECKPOINT_DIR.exists():
        return []
    cutoff = datetime.now(timezone.utc).timestamp() - max_age_days * 86400
    removed: list[Path] = []
    prefix = f"{_safe_name(namespace)}__"
    for p in CHECKPOINT_DIR.glob(f"{prefix}*.json"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
                removed.append(p)
        except OSError:
            continue
    return removed
