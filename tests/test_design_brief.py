"""docs/design is the dashboard redesign brief that Claude Design reads from GitHub: its parts must be
there, every link between them must resolve, and the text we wrote follows the no-dash rule."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DESIGN = REPO / "docs" / "design"
SNAPSHOT = DESIGN / "dashboard-snapshot"
THEME = DESIGN / "velocity-theme"
TEXT = {".md", ".html", ".css", ".json"}
MD_LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")
HTML_LINK = re.compile(r"""(?:href|src)=["']([^"']+)["']""")
CSS_URL = re.compile(r"""url\(\s*["']?([^"')]+)""")
GITHUB = re.compile(r"https://github\.com/Velocity-Explorations/velocity-bd-team/(?:blob|tree)/main/([^\s)\"'`>]+)")
DASHES = re.compile("[" + chr(0x2013) + chr(0x2014) + "]")   # en dash, em dash


def _local(target: str) -> bool:
    return not re.match(r"([a-z]+:|#)", target)


def _resolves(base: Path, target: str) -> bool:
    return (base / target.split("#")[0].split("?")[0]).exists()


def test_the_brief_has_its_parts() -> None:
    for part in ("README.md", "dashboard-design-spec.md", "dashboard-build-prompts.md",
                 "dashboard-snapshot/README.md", "dashboard-snapshot/queue.html", "dashboard-snapshot/screens",
                 "velocity-theme/README.md", "velocity-theme/tokens.css", "velocity-theme/components/bundle.css"):
        assert (DESIGN / part).exists(), part


@pytest.mark.parametrize("doc", sorted(DESIGN.rglob("*.md")), ids=lambda p: p.relative_to(DESIGN).as_posix())
def test_markdown_links_resolve(doc: Path) -> None:
    text = re.sub(r"```.*?```", "", doc.read_text(encoding="utf-8"), flags=re.S)   # code blocks hold sample markup
    for target in MD_LINK.findall(text):
        if _local(target):
            assert _resolves(doc.parent, target), f"{doc.relative_to(DESIGN).as_posix()}: {target}"


@pytest.mark.parametrize("page", sorted(DESIGN.rglob("*.html")), ids=lambda p: p.relative_to(DESIGN).as_posix())
def test_html_links_resolve(page: Path) -> None:
    text = page.read_text(encoding="utf-8")
    for target in HTML_LINK.findall(text) + CSS_URL.findall(text):
        if _local(target):
            assert _resolves(page.parent, target), f"{page.relative_to(DESIGN).as_posix()}: {target}"


def test_theme_fonts_resolve() -> None:
    css = THEME / "tokens.css"
    fonts = [t for t in CSS_URL.findall(css.read_text(encoding="utf-8")) if _local(t)]
    assert fonts
    for target in fonts:
        assert _resolves(css.parent, target), target


def test_github_links_point_at_files_on_main() -> None:
    """Prompt 0 sends Claude Design to GitHub, so those links must name real paths in this repo."""
    found = 0
    for doc in DESIGN.rglob("*.md"):
        for path in GITHUB.findall(doc.read_text(encoding="utf-8")):
            found += 1
            assert (REPO / path.rstrip("/.,;:")).exists(), f"{doc.name}: {path}"
    assert found


def test_no_en_or_em_dash_in_what_we_wrote() -> None:
    """The guides, spec, prompts and theme follow the writing rule; the snapshot pages keep portal data as captured."""
    written = [p for p in DESIGN.rglob("*") if p.suffix in TEXT and not (p.parent == SNAPSHOT and p.suffix == ".html")]
    assert written
    for path in written:
        assert not DASHES.search(path.read_text(encoding="utf-8")), path.relative_to(DESIGN).as_posix()
