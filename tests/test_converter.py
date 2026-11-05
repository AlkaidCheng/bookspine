"""Tests for turning Markdown into the HTML the later passes read."""

import pytest

from guidebook.converter import convert_markdown


def test_a_box_holds_its_title_and_text() -> None:
    assert convert_markdown('!!! note "Careful"\n    Mind the gap.\n') == (
        '<div class="admonition note">\n<p class="admonition-title">Careful</p>\n'
        "<p>Mind the gap.</p>\n</div>"
    )


def test_a_box_without_a_title_takes_its_kind() -> None:
    assert '<p class="admonition-title">Tip</p>' in convert_markdown("!!! tip\n    A\n")


def test_an_empty_title_leaves_the_title_out() -> None:
    assert "admonition-title" not in convert_markdown('!!! note ""\n    A\n')


def test_a_box_keeps_its_extra_classes() -> None:
    assert '<div class="admonition note wide">' in convert_markdown(
        "!!! note wide\n    A\n"
    )


def test_a_box_title_reads_markdown_and_math() -> None:
    html = convert_markdown('!!! example "A *matched* $Z$ sample"\n    A\n')
    assert '<em>matched</em> <span class="arithmatex">\\(Z\\)</span>' in html


def test_a_box_ends_at_the_first_line_outside_it() -> None:
    html = convert_markdown("!!! note\n    One\n\n    Two\n\nThree\n")
    assert html.endswith("<p>Two</p>\n</div>\n<p>Three</p>")


def test_boxes_nest() -> None:
    html = convert_markdown("!!! note\n    A\n\n    !!! tip\n        B\n\nC\n")
    assert html.index("admonition note") < html.index("admonition tip")
    assert html.index("<p>B</p>") < html.index("<p>C</p>")
    assert "\ue000" not in html


def test_two_boxes_keep_their_order() -> None:
    html = convert_markdown("!!! note\n    A\n\n!!! tip\n    B\n")
    assert html.index("<p>A</p>") < html.index("<p>B</p>")


def test_a_box_can_sit_in_a_list() -> None:
    html = convert_markdown("- Item\n\n    !!! note\n        A\n")
    assert '<li>\n<p>Item</p>\n<div class="admonition note">' in html


def test_a_box_holds_code_and_lists() -> None:
    html = convert_markdown("!!! note\n    - a\n\n    ```python\n    x = 1\n    ```\n")
    assert "<li>a</li>" in html
    assert '<div class="highlight">' in html


def test_box_syntax_in_code_stays_as_code() -> None:
    html = convert_markdown("```\n!!! note\n    A\n```\n")
    assert "admonition" not in html
    assert "!!! note" in html


@pytest.mark.parametrize("marker, attribute", [("???", ""), ("???+", ' open="open"')])
def test_a_collapsible_box(marker: str, attribute: str) -> None:
    assert convert_markdown(f'{marker} note "More"\n    A\n') == (
        f'<details class="note"{attribute}>\n<summary>More</summary>\n<p>A</p>\n'
        "</details>"
    )


def test_code_takes_the_colours_of_its_language() -> None:
    html = convert_markdown("```python\nx = 1\n```\n")
    assert html.startswith('<div class="highlight"><pre><span></span><code>')
    assert '<span class="mi">1</span>' in html


@pytest.mark.parametrize("fence", ["```", "```not-a-language"])
def test_code_without_a_known_language_stays_plain(fence: str) -> None:
    html = convert_markdown(f"{fence}\na < b\n```\n")
    assert "<code>a &lt; b\n</code>" in html


def test_blank_lines_at_the_edges_of_code_stay() -> None:
    assert "<code>\na\n\n</code>" in convert_markdown("```\n\na\n\n```\n")


def test_inline_math_takes_mathjax_delimiters() -> None:
    assert convert_markdown("Energy $E = mc^2$.") == (
        '<p>Energy <span class="arithmatex">\\(E = mc^2\\)</span>.</p>'
    )


def test_display_math_is_a_block_of_its_own() -> None:
    assert convert_markdown("$$\nx \\label{eq:a}\n$$\n") == (
        '<div class="arithmatex">\\[\nx \\label{eq:a}\n\\]</div>'
    )


def test_a_dollar_in_prose_is_not_math() -> None:
    assert "arithmatex" not in convert_markdown("It costs $5 or $ 6.")


def test_math_keeps_its_backslashes() -> None:
    source = "\\frac{a}{b} \\\\ c"
    assert source in convert_markdown(f"$$\n{source}\n$$\n")


@pytest.mark.parametrize(
    "heading, anchor",
    [
        ("## A heading", "a-heading"),
        ("## It's *here*", "its-here"),
        ("## Caf\u00e9 au lait", "cafe-au-lait"),
        ("## `code` and more", "code-and-more"),
        ("## \u03b1", "_1"),
    ],
)
def test_a_heading_takes_its_anchor_from_its_text(heading: str, anchor: str) -> None:
    assert convert_markdown(heading).startswith(f'<h2 id="{anchor}">')


def test_repeated_headings_stay_unique() -> None:
    html = convert_markdown("## A\n\n## A\n\n## A\n")
    assert [f'id="{a}"' in html for a in ("a", "a_1", "a_2")] == [True, True, True]


def test_a_written_anchor_is_kept_and_counts_as_taken() -> None:
    html = convert_markdown("## One {: #two }\n\n## Two\n")
    assert '<h2 id="two">One</h2>' in html
    assert '<h2 id="two_1">Two</h2>' in html


def test_a_heading_takes_a_class() -> None:
    assert 'class="unnumbered"' in convert_markdown("## One {: .unnumbered }\n")


def test_headings_in_boxes_take_anchors_too() -> None:
    assert '<h3 id="inside">' in convert_markdown("!!! note\n    ### Inside\n")


def test_punctuation_is_set() -> None:
    assert convert_markdown('It\'s "quoted" -- and...') == (
        "<p>It\u2019s \u201cquoted\u201d \u2013 and\u2026</p>"
    )


def test_tables_and_definition_lists_are_read() -> None:
    assert "<table>" in convert_markdown("| a |\n|---|\n| b |\n")
    assert "<dd>" in convert_markdown("Term\n:   Meaning\n")


def test_lists_follow_commonmark() -> None:
    assert "<ul>\n<li>b</li>" in convert_markdown("- a\n  - b\n")
    assert convert_markdown("text\n- a\n").startswith("<p>text</p>\n<ul>")


def test_html_passes_through() -> None:
    assert '<div class="x">a</div>' in convert_markdown('<div class="x">a</div>\n')
