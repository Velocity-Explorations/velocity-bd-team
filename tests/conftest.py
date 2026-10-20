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


@pytest.fixture(autouse=True)
def no_real_grok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never reach xAI, even with BD_XAI_API_KEY in the real .env: the second judge is
    off unless a test turns it on with a scripted model."""
    import run

    monkeypatch.setattr(run, "grok_enabled", lambda: False)
