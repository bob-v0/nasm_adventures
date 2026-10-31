import re

import pytest

from ring import briefs
from ring.level import all_levels

LEVELS = all_levels()


@pytest.mark.parametrize("number", sorted(LEVELS, reverse=True))
def test_briefs_and_hints_render_for_both_interfaces(number):
    lv = LEVELS[number]
    for text in [lv.brief, *lv.hints]:
        web, cli = briefs.render(text, "web"), briefs.render(text, "cli")
        assert "{{" not in web and "{{" not in cli, "unknown placeholder"
        # In the browser there is no `ring` command to type (except the explicit
        # plain-terminal aside in level 174).
        assert not re.search(r"`ring (?!debug --binary|debug` in the \*\*Terminal)[a-z]", web), \
            "CLI command shown in the browser"


@pytest.mark.parametrize("number", sorted(LEVELS, reverse=True))
def test_starters_do_not_assume_a_terminal(number):
    """Starters open in the browser editor too; they mustn't tell you to run `ring ...`."""
    assert not re.search(r"\bring [a-z]", LEVELS[number].starter.read_text())


@pytest.mark.parametrize("number", sorted(LEVELS, reverse=True))
def test_figures_exist_and_are_safe(number):
    """`![caption](name.svg)` lines name files in the level's figures/ folder; SVGs are
    shown as images, and must not script or fetch anything."""
    lv = LEVELS[number]
    for text in [lv.brief, *lv.hints]:
        for _, name in briefs.FIGURE.findall(text):
            f = lv.path / "figures" / name
            assert f.is_file(), f"missing figure {f}"
            if name.endswith(".svg"):
                svg = f.read_text()
                assert "<svg" in svg and "<script" not in svg.lower()
                assert not re.search(r"(href|src)\s*=\s*[\"'](?!#)", svg), "external reference in an SVG"
