from __future__ import annotations

from pathlib import Path

import pytest

from ledger import migrate


@pytest.fixture
def ledger_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Fresh, migrated SQLite ledger per test. Returns the DATABASE_URL in use."""
    url = f"sqlite:///{(tmp_path / 'ledger.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    migrate.apply(url)
    return url
