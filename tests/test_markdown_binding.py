"""The compiled module that hands pages to pulldown-cmark."""

from importlib.metadata import version

import pytest

import bookspine
from bookspine import _markdown


def test_commonmark_needs_no_extension() -> None:
    assert _markdown.to_html("# Title", 0) == "<h1>Title</h1>\n"


@pytest.mark.parametrize(
    ("extension", "source", "expected"),
    [
        (_markdown.ENABLE_DEFINITION_LIST, "term\n: text\n", "<dl>"),
        (_markdown.ENABLE_HEADING_ATTRIBUTES, "# Title {#name}\n", 'id="name"'),
        (_markdown.ENABLE_MATH, "$x$\n", 'class="math'),
        (_markdown.ENABLE_SMART_PUNCTUATION, '"quoted"\n', "“quoted”"),
        (_markdown.ENABLE_TABLES, "| a |\n|---|\n| b |\n", "<table>"),
    ],
)
def test_each_extension_reads_its_own_syntax(
    extension: int, source: str, expected: str
) -> None:
    assert expected in _markdown.to_html(source, extension)
    assert expected not in _markdown.to_html(source, 0)


def test_text_outside_ascii_keeps_its_characters() -> None:
    assert _markdown.to_html("α → β ", 0) == "<p>α → β </p>\n"


def test_an_unknown_option_bit_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown option bits"):
        _markdown.to_html("text", 1 << 31)


def test_the_package_reports_the_version_it_was_installed_as() -> None:
    assert bookspine.__version__ == version("bookspine")
