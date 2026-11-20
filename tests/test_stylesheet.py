"""Tests for the rules of book.css that depend on which declaration wins."""

import re
from importlib import resources

BOOK_CSS = resources.files("bookspine").joinpath("static/book.css").read_text("utf-8")

_COMMENT_PATTERN = re.compile(r"/\*.*?\*/", re.S)
# Only rules that hold no block, so a rule inside @media is found on its own.
_RULE_PATTERN = re.compile(r"([^{}]+)\{([^{}]*)\}")
_ID_PATTERN = re.compile(r"#[\w-]+")
_CLASS_PATTERN = re.compile(r"\.[\w-]+|\[[^\]]*\]|(?<!:):[\w-]+")
_TYPE_PATTERN = re.compile(r"(?:^|[\s>+~])[a-z][\w-]*|::[\w-]+")

Rule = tuple[list[str], dict[str, str]]


def specificity(selector: str) -> tuple[int, int, int]:
    """Return the specificity of `selector`, which holds no functional pseudo-class.

    https://www.w3.org/TR/selectors-4/#specificity-rules
    """
    return (
        len(_ID_PATTERN.findall(selector)),
        len(_CLASS_PATTERN.findall(selector)),
        len(_TYPE_PATTERN.findall(selector)),
    )


def css_rules() -> list[Rule]:
    """Return the selector list and declarations of each rule in book.css."""
    css = _COMMENT_PATTERN.sub("", BOOK_CSS)
    rules = []
    for selectors, block in _RULE_PATTERN.findall(css):
        declarations = dict(
            (name.strip(), value.strip())
            for name, _, value in (item.partition(":") for item in block.split(";"))
            if value
        )
        rules.append(([s.strip() for s in selectors.split(",")], declarations))
    return rules


def figure_selectors(selectors: list[str], *, in_lightbox: bool) -> list[str]:
    """Return those of `selectors` that can match a figure on the page or enlarged."""
    return [
        selector
        for selector in selectors
        if selector.split()[-1] in {"img", "svg", "svg.inline-svg"}
        and selector.startswith(".lightbox-content") == in_lightbox
    ]


def lightbox_width_rules() -> list[Rule]:
    """Return the rules that set the width of an enlarged figure."""
    return [
        (figure_selectors(selectors, in_lightbox=True), declarations)
        for selectors, declarations in css_rules()
        if "width" in declarations and figure_selectors(selectors, in_lightbox=True)
    ]


def test_specificity_counts_ids_classes_and_types() -> None:
    assert specificity("figure svg.inline-svg") == (0, 1, 2)
    assert specificity("#a .b:hover > p::before") == (1, 2, 2)


def test_the_lightbox_width_of_an_inline_svg_outweighs_its_width_on_the_page() -> None:
    # The lightbox is as wide as its content, so the page's width of 100% would leave
    # an SVG without width attributes at the 300 px default.
    page_weights = [
        specificity(selector)
        for selectors, declarations in css_rules()
        if "width" in declarations
        for selector in figure_selectors(selectors, in_lightbox=False)
        if selector.endswith("svg.inline-svg")
    ]
    rules = [
        selectors
        for selectors, _ in lightbox_width_rules()
        if any(selector.split()[-1].startswith("svg") for selector in selectors)
    ]
    assert page_weights
    assert rules
    for selectors in rules:
        assert max(map(specificity, selectors)) > max(page_weights), selectors


def test_a_lightbox_width_wider_than_the_screen_is_not_capped() -> None:
    # img, svg { max-width: 100% } would hold the figure at the width of the screen.
    floored = [
        declarations
        for _, declarations in lightbox_width_rules()
        if declarations["width"].startswith("max(")
    ]
    assert floored
    for declarations in floored:
        assert declarations.get("max-width") == "none", declarations
