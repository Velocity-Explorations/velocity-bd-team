"""Settings for every component, read from the environment and the repo's .env file.

.env is parsed line by line: blank lines and lines starting with # are skipped, the first
'=' splits key from value, surrounding single or double quotes are removed. A value
already present in the process environment wins over the file.

    from config import require, get
    user = require("VULCAN_SOF_USERNAME")   # ConfigError naming the key if absent
    mailbox = get("VULCAN_OTP_MAILBOX", "")

Never print, log or echo a value. Log the key name only. ``python -m config`` lists which
known keys are set without showing any value.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
ENV_FILE = REPO_ROOT / ".env"

# Every key any component reads. Keep in step with .env.example.
KNOWN_KEYS = [
    "DATABASE_URL",
    "AI_SLOP_SCAN",
    "LIBRARY_DRIVE_FOLDER_ID",
    "GOOGLE_SERVICE_ACCOUNT_FILE",
    "VULCAN_SOF_USERNAME",
    "VULCAN_SOF_PASSWORD",
    "VULCAN_OTP_MAILBOX",
    "VELOCITY_GMAIL_APP_USERNAME",
    "VELOCITY_GMAIL_APP_PASSWORD",
    "ANTHROPIC_API_KEY",
    "BD_SLACK_BOT_TOKEN",
    "SLACK_CHANNEL_ID",
    "BD_GITHUB_TOKEN",
    "BD_XAI_API_KEY",
    "WRITER_MODEL",
    "BD_SAM_API_KEY",
    "DASHBOARD_URL",
    "DASHBOARD_USERS",
    "WORKSPACE_SLACK",
    "OLLAMA_URL",
]


class ConfigError(Exception):
    """A required setting is missing or malformed. The message names the key, never a value."""


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file. Returns {} when the file does not exist."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            values[key] = value
    return values


_cache: dict[str, str] | None = None


def load(path: Path | None = None, reload: bool = False) -> dict[str, str]:
    """File values with the process environment layered on top. Cached after first call."""
    global _cache
    if _cache is None or reload or path is not None:
        merged = parse_env_file(path or ENV_FILE)
        merged.update({k: v for k, v in os.environ.items() if k in merged or k in KNOWN_KEYS})
        if path is None:
            _cache = merged
        return merged
    return _cache


def get(key: str, default: str | None = None) -> str | None:
    value = os.environ.get(key)
    if value is None:
        value = load().get(key)
    if value is None or value == "":
        return default
    return value


def require(key: str) -> str:
    value = get(key)
    if value is None:
        raise ConfigError(
            f"Missing setting {key}. Add a line '{key}=...' to {ENV_FILE.name} (see .env.example)."
        )
    return value


def main(argv: list[str] | None = None) -> int:
    """Print which known keys are set. Values are never shown."""
    print(f"{ENV_FILE.name}: {'found' if ENV_FILE.exists() else 'not found'} at {ENV_FILE.parent}")
    missing = 0
    for key in KNOWN_KEYS:
        present = get(key) is not None
        missing += 0 if present else 1
        print(f"  {key:22s} {'set' if present else 'MISSING'}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
