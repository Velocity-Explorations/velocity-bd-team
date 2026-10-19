from __future__ import annotations

from pathlib import Path

import pytest

import config


def test_parse_env_file_handles_comments_quotes_and_export(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n\nA=1\nB = 'two words'\nexport C=\"three\"\nD=has=equals\nnoequals\n",
        encoding="utf-8",
    )
    assert config.parse_env_file(env) == {"A": "1", "B": "two words", "C": "three", "D": "has=equals"}


def test_parse_env_file_missing_returns_empty(tmp_path: Path) -> None:
    assert config.parse_env_file(tmp_path / "nope") == {}


def test_require_names_missing_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr(config, "_cache", None)
    monkeypatch.delenv("VULCAN_SOF_USERNAME", raising=False)
    with pytest.raises(config.ConfigError) as exc:
        config.require("VULCAN_SOF_USERNAME")
    assert "VULCAN_SOF_USERNAME" in str(exc.value)
    assert ".env" in str(exc.value)


def test_environment_wins_over_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("VULCAN_OTP_MAILBOX=file@example.invalid\nVULCAN_SOF_PASSWORD=''\n", encoding="utf-8")
    monkeypatch.setattr(config, "ENV_FILE", env)
    monkeypatch.setattr(config, "_cache", None)
    monkeypatch.setenv("VULCAN_OTP_MAILBOX", "env@example.invalid")
    monkeypatch.delenv("VULCAN_SOF_PASSWORD", raising=False)
    assert config.require("VULCAN_OTP_MAILBOX") == "env@example.invalid"
    assert config.get("VULCAN_SOF_PASSWORD", "dflt") == "dflt"   # empty value counts as unset
    with pytest.raises(config.ConfigError):
        config.require("VULCAN_SOF_PASSWORD")


def test_known_keys_match_env_example() -> None:
    example = config.parse_env_file(config.REPO_ROOT / ".env.example")
    assert set(example) == set(config.KNOWN_KEYS)


def test_pipeline_github_token_is_a_known_key() -> None:
    assert "BD_GITHUB_TOKEN" in config.KNOWN_KEYS
