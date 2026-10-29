from __future__ import annotations

import re
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


@pytest.fixture(autouse=True)
def fake_slop_scanner(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never run the slop scanner, which lives outside this repo. The stand-in reports every
    [PERSON WRITES ...] and [NEEDS ...] in the draft as an open placeholder, with a clean band."""
    from drafting import slop_gate

    def scan(draft: Path, solicitation: Path | None = None, scanner: Path | None = None) -> dict:
        text = Path(draft).read_text(encoding="utf-8")
        found = re.findall(r"\[(?:PERSON WRITES|NEEDS [A-Z]+)[^\]\n]*\]", text)
        return {"band": "clean", "confidence": "full", "words": len(text.split()), "thresholds": {"calibrated": False},
                "families": {}, "hot_paragraphs": [],
                "findings": [{"family": "prop_open_item", "tier": "proposal", "line": 1, "match": m} for m in found]}

    monkeypatch.setattr(slop_gate, "run_scan", scan)


@pytest.fixture(autouse=True)
def writer_on_its_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests draft with the default model whatever WRITER_MODEL the real .env names, and the Writer never
    reaches xAI: a test of the Grok path puts a fake stream in its place."""
    from drafting import llm

    monkeypatch.setenv("WRITER_MODEL", "")

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("tests never reach xAI")

    monkeypatch.setattr(llm, "_open", refuse)


@pytest.fixture(autouse=True)
def no_real_drive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never reach Google Drive, whatever .env says; a test that needs Drive puts a fake in its place."""
    from drafting import drive

    monkeypatch.setattr(drive, "client", lambda: None)
    monkeypatch.setattr(drive, "sheets_client", lambda: None)
