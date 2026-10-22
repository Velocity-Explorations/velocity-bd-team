"""
Yukon — Deduplication store
SQLite-backed seen-opps tracker. Prevents alerting on the same opportunity twice.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class DedupStore:
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / "data" / "seen_opps.db"

        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS seen_opps (
                    id        TEXT NOT NULL,
                    portal    TEXT NOT NULL,
                    title     TEXT,
                    url       TEXT,
                    first_seen TEXT NOT NULL,
                    profile   TEXT NOT NULL,
                    PRIMARY KEY (id, profile)
                )
            """)

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def is_seen(self, opp_id: str, profile: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM seen_opps WHERE id = ? AND profile = ?",
                (opp_id, profile)
            ).fetchone()
            return row is not None

    def mark_seen(self, opp_id: str, portal: str, title: str, url: str, profile: str):
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO seen_opps (id, portal, title, url, first_seen, profile)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (opp_id, portal, title, url, now, profile)
            )

    def count(self, profile: Optional[str] = None) -> int:
        with self._conn() as conn:
            if profile:
                return conn.execute(
                    "SELECT COUNT(*) FROM seen_opps WHERE profile = ?", (profile,)
                ).fetchone()[0]
            return conn.execute("SELECT COUNT(*) FROM seen_opps").fetchone()[0]
