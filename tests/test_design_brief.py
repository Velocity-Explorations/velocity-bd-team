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
SPEC = DESIGN / "dashboard-design-spec.md"
PROMPTS = DESIGN / "dashboard-build-prompts.md"
SPEC_ID = re.compile(r"^\| ([A-Z]\d+) \|", flags=re.M)
ID_RANGE = re.compile(r"\b([A-Z])(\d+) to \1(\d+)\b")
ID_ONE = re.compile(r"\(([A-Z]\d+)\)")


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


def test_prompt_ids_exist_in_the_spec() -> None:
    """Every requirement ID a build prompt names, alone or as a range such as Q1 to Q12, is a row in the spec."""
    prompts = PROMPTS.read_text(encoding="utf-8")
    spec_ids = set(SPEC_ID.findall(SPEC.read_text(encoding="utf-8")))
    named = {f"{letter}{n}" for letter, first, last in ID_RANGE.findall(prompts) for n in range(int(first), int(last) + 1)}
    named |= set(ID_ONE.findall(prompts))
    assert named, "the prompts name no requirement IDs"
    assert sorted(named - spec_ids) == []


def test_prompts_are_numbered_in_order() -> None:
    """Prompt 0 is for Claude Design; prompts 1 to N are phases 1 to N of N."""
    text = PROMPTS.read_text(encoding="utf-8")
    headings = [int(n) for n in re.findall("^## Prompt ([0-9]+):", text, flags=re.M)]
    phases = re.findall("Phase ([0-9]+) of ([0-9]+)", text)
    last = len(headings) - 1
    assert headings == list(range(last + 1))
    assert [int(n) for n, _ in phases] == list(range(1, last + 1))
    assert {int(total) for _, total in phases} == {last}


def test_update_prompt_covers_the_new_structure() -> None:
    """A design made before 26 Oct is updated in Claude Design, not redrawn; the build phases then use it."""
    text = PROMPTS.read_text(encoding="utf-8")
    blocks = re.findall(r"^## Update prompt: Claude Design.*?```text\n(.*?)```", text, flags=re.M | re.S)
    assert len(blocks) == 1
    for ids in ("N1 to N6", "H1 to H7", "P1 to P8", "U1 to U6", "Q9"):
        assert ids in blocks[0]
