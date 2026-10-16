"""Ledger database access.

One function set, two backends. DATABASE_URL picks the backend:

    sqlite:///data/dev.db          relative to the repo root
    sqlite:///C:/path/to/file.db   absolute (Windows)
    sqlite:////path/to/file.db     absolute (POSIX)
    postgresql://user:pass@host/db hosted Postgres via psycopg

Queries are written once with ``?`` placeholders; ``q()`` rewrites them to ``%s`` for
Postgres. Do not put a literal ``?`` inside SQL text for that reason.

Never log or print DATABASE_URL: it carries the password.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SQLITE_URL = "sqlite:///data/dev.db"


def now_iso() -> str:
    """Current time as ISO-8601 UTC text with second precision, e.g. 2026-10-15T14:03:09Z."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def database_url() -> str:
    """DATABASE_URL from the environment or .env. Raises ConfigError naming the key if absent."""
    from config import require

    return require("DATABASE_URL").strip()


def dialect_of(url: str) -> str:
    """'sqlite' or 'postgres'."""
    scheme = url.split("://", 1)[0].lower()
    if scheme.startswith("sqlite"):
        return "sqlite"
    if scheme in ("postgres", "postgresql"):
        return "postgres"
    raise ValueError(f"Unsupported DATABASE_URL scheme: {scheme}")


def sqlite_path(url: str) -> Path | str:
    """Resolve a sqlite:// URL to a filesystem path (or ':memory:')."""
    rest = url.split("://", 1)[1]
    if rest.startswith("/"):
        rest = rest[1:]
    if rest == ":memory:":
        return rest
    path = Path(rest)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def connect(url: str | None = None) -> Any:
    """Open a DB-API connection for DATABASE_URL (or the given URL)."""
    url = url or database_url()
    if dialect_of(url) == "sqlite":
        target = sqlite_path(url)
        if isinstance(target, Path):
            target.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False: the pipeline's fetch worker thread shares the dry-run
        # connection with the main thread; they never use it at the same time.
        return sqlite3.connect(str(target), check_same_thread=False)
    import psycopg

    return psycopg.connect(url)


def is_sqlite(conn: Any) -> bool:
    return isinstance(conn, sqlite3.Connection)


# When set, every tx() hands out this one connection and never commits. dry_run_session()
# owns it and rolls everything back at the end.
_shared: Any = None


@contextmanager
def dry_run_session(url: str | None = None) -> Iterator[Any]:
    """Run a whole pipeline against one connection and roll it back at the end."""
    global _shared
    conn = connect(url)
    _shared = conn
    try:
        yield conn
    finally:
        _shared = None
        try:
            conn.rollback()
        finally:
            conn.close()


@contextmanager
def tx(url: str | None = None) -> Iterator[Any]:
    """Connection scoped to one transaction: commit on success, roll back on error, always close.

    Inside dry_run_session() the shared connection is yielded instead and nothing commits.
    """
    if _shared is not None and url is None:
        yield _shared
        return
    conn = connect(url)
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def q(conn: Any, sql: str, params: Sequence[Any] = ()) -> Any:
    """Execute ``sql`` with ``?`` placeholders on either backend; returns the cursor."""
    if not is_sqlite(conn):
        sql = sql.replace("?", "%s")
    cur = conn.cursor()
    cur.execute(sql, tuple(params))
    return cur


def rows(cur: Any) -> list[dict[str, Any]]:
    """Fetch all rows from a cursor as dicts keyed by column name."""
    if cur.description is None:
        return []
    names = [d[0] for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def one(cur: Any) -> dict[str, Any] | None:
    """Fetch the first row as a dict, or None."""
    found = rows(cur)
    return found[0] if found else None
