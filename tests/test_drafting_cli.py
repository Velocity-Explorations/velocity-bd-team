"""The Writer's command line: `python -m drafting.cli dev` (Writer Plan W0)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from drafting import cli, llm
from tests.test_drafting_pipeline import ALL_FILES, canned

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample_inputs.json"


@pytest.fixture
def fake_model(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def generate(prompt: str, system: str = "", model: str | None = None, phase_label: str = "",
                 **kwargs: Any) -> str:
        calls.append({"label": phase_label, "model": model})
        return canned(phase_label)

    monkeypatch.setattr(llm, "generate", generate)
    return calls


def test_the_fixture_is_a_complete_input() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for key in ("title", "portal", "opp_type", "agency", "due_date", "listing_text", "attachments",
                "company_context"):
        assert data.get(key), key


def test_dev_runs_every_phase_and_prints_the_timing(tmp_path: Path, fake_model: list[dict[str, Any]],
                                                   capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "sample"
    assert cli.main(["dev", "--inputs", str(FIXTURE), "--out", str(out), "--model", "claude-haiku-5-5"]) == 0
    for name in ALL_FILES:
        assert (out / name).exists(), name
    printed = capsys.readouterr().out
    assert "Review ×4" in printed and "Final draft:" in printed and "draft_final.md" in printed
    assert {c["model"] for c in fake_model} == {"claude-haiku-5-5"}
    assert json.loads((out / "source" / "inputs.json").read_text(encoding="utf-8"))["title"]


def test_dev_from_a_phase_reruns_only_what_was_asked(tmp_path: Path, fake_model: list[dict[str, Any]]) -> None:
    out = tmp_path / "sample"
    assert cli.main(["dev", "--inputs", str(FIXTURE), "--out", str(out)]) == 0
    fake_model.clear()
    assert cli.main(["dev", "--inputs", str(FIXTURE), "--out", str(out), "--from-phase", "6.5",
                     "--to-phase", "6.5"]) == 0
    assert [c["label"].split(":")[0] for c in fake_model] == [f"review pass {n}/4" for n in range(1, 5)]


def test_an_unknown_phase_is_a_clean_error(tmp_path: Path, fake_model: list[dict[str, Any]],
                                           capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["dev", "--inputs", str(FIXTURE), "--out", str(tmp_path), "--from-phase", "9"]) == 2
    assert "No phase 9" in capsys.readouterr().out
