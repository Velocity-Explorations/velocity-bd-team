"""The dashboard wears the BD Team theme from Claude Design's handoff (PRO-569): the handoff's app and
card tokens, dark only, self-hosted fonts, and Lucide pinned to one version. Reads files only."""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DASHBOARD = REPO / "dashboard"
THEME = DASHBOARD / "app" / "theme.css"
HANDOFF = REPO / "docs" / "design" / "handoff" / "velocity-theme"
PROPERTY = re.compile(r"(--[\w-]+)\s*:\s*([^;]+);")


def _properties(css: Path) -> dict[str, str]:
    text = re.sub(r"/\*.*?\*/", "", css.read_text(encoding="utf-8"), flags=re.S)
    return {name: " ".join(value.split()) for name, value in PROPERTY.findall(text)}


def test_the_dashboard_tokens_equal_the_handoff() -> None:
    ours = _properties(THEME)
    theirs = _properties(HANDOFF / "tokens-app.css") | _properties(HANDOFF / "card.css")
    assert theirs
    assert {name: value for name, value in theirs.items() if ours.get(name) != value} == {}


def test_the_dashboard_is_dark_only() -> None:
    css = [p for p in (DASHBOARD / "app").rglob("*.css")]
    assert css
    for path in css:
        assert "prefers-color-scheme" not in path.read_text(encoding="utf-8"), path.name
    assert re.search(r"color-scheme:\s*dark;", THEME.read_text(encoding="utf-8"))


def test_the_fonts_are_self_hosted() -> None:
    text = THEME.read_text(encoding="utf-8")
    faces = re.findall(r"@font-face\s*\{(.*?)\}", text, flags=re.S)
    found = set()
    for face in faces:
        family = re.search(r"font-family:\s*'([^']+)'", face).group(1)
        weight = re.search(r"font-weight:\s*(\d+)", face).group(1)
        url = re.search(r"url\('([^']+)'\)", face).group(1)
        assert url.startswith("/fonts/"), url
        assert (DASHBOARD / "public" / url.lstrip("/")).is_file(), url
        found.add((family, weight))
    wanted = {("Inter Tight", w) for w in ("400", "600", "700")} | {("Chakra Petch", w) for w in ("400", "500", "600", "700")}
    assert found == wanted
    assert "fonts.googleapis" not in text and "http" not in text


def test_lucide_is_pinned_to_one_version() -> None:
    version = json.loads((DASHBOARD / "package.json").read_text(encoding="utf-8"))["dependencies"]["lucide-react"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), version
