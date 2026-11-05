from __future__ import annotations

import re
from pathlib import Path

import pytest

from ledger import migrate


@pytest.fixture(autouse=True)
def pages_wait_for_their_content(monkeypatch: pytest.MonkeyPatch) -> None:
    """A dashboard page streams its loading screen first (dashboard/app/loading.tsx), and React swaps the page in up to
    300 ms after the load event, so opening a page in a browser test also waits until the loading screen has gone."""
    try:
        from playwright.sync_api import Error, Page
    except ImportError:
        return

    def settled(original):   # type: ignore[no-untyped-def]
        def wait(self, *args, **kwargs):   # type: ignore[no-untyped-def]
            result = original(self, *args, **kwargs)
            for _ in range(3):   # a page that redirects in the browser replaces the document once more
                try:
                    self.wait_for_function("!document.querySelector('.loading-page')", timeout=60_000)
                    break
                except Error as exc:
                    if "context was destroyed" not in str(exc) and "navigat" not in str(exc):
                        raise
                    self.wait_for_load_state("load")
            return result
        return wait

    for name in ("goto", "reload", "wait_for_url"):
        monkeypatch.setattr(Page, name, settled(getattr(Page, name)))


@pytest.fixture
def ledger_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Fresh, migrated SQLite ledger per test. Returns the DATABASE_URL in use."""
    url = f"sqlite:///{(tmp_path / 'ledger.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    migrate.apply(url)
    return url


@pytest.fixture(autouse=True)
def no_real_linear(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never reach Linear, even with BD_LINEAR_API_KEY in the real .env: the key reads as unset."""
    monkeypatch.setenv("BD_LINEAR_API_KEY", "")


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
def made_up_company_facts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Every Writer step reads Velocity's facts from 01 Company Reference on Drive; tests read a made-up one
    (tests/company_reference.py) and keep its copy in the test's folder."""
    from drafting import facts
    from tests import company_reference

    monkeypatch.setattr(facts, "read_drive", company_reference.files)
    monkeypatch.setattr(facts, "CACHE", tmp_path / "facts" / "company_reference.json")


@pytest.fixture(autouse=True)
def no_real_drive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never reach Google Drive, whatever .env says; a test that needs Drive puts a fake in its place."""
    from drafting import drive

    monkeypatch.setattr(drive, "client", lambda: None)
    monkeypatch.setattr(drive, "sheets_client", lambda: None)
