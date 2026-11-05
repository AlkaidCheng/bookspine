"""Tests that the faster inline pass gives the library's own result."""

import random
import string
from typing import Any

import markdown
import pytest
from markdown.treeprocessors import InlineProcessor
from markdown.util import AtomicString

from guidebook.config import MARKDOWN_EXTENSION_CONFIGS, MARKDOWN_EXTENSIONS
from guidebook.inline import INLINE_PROCESSOR_PRIORITIES, REQUIRED_TEXT
from guidebook.site import make_markdown

# Pieces of Markdown that exercise each pattern, alone and against one another.
FRAGMENTS = [
    "word", "two words", " ", "  \n", "\n", "\n\n", ".", "...", "....", "-", "--", "---",
    "----", "\'", '"', "''", '"\'', "it's", "the '90s", "*", "**", "***", "_", "__", "`",
    "``", "\\", "\\\\", "\\*", "\\`", "\\(", "\\)", "\\[", "\\]", "$", "$$", "$x$", "\\$",
    "[", "]", "(", ")", "!", "![", "[a](b)", "![a](b)", "[a][b]", "[a]", "[^1]", "<", ">",
    "<b>", "</b>", "<!-- c -->", "<a@b.c>", "<https://a.b/c>", "&", "&amp;", "&#39;",
    "&nbsp;", "+", "++", "++ctrl+a++", "\\\\+", "++a++", "#", "- ", "1. ", "> ", "    ",
    ": ", "|", "{: #x }", "`code`", "``a`b``", "`#!python x`", "*a*", "**a**", "_a_",
    "__a__", "*a _b* c_", "\t", "\u2014", "\u2013", "\u00e9",
]  # fmt: skip

PATTERN_REGISTRIES = {"inline", "smarty"}


def library_markdown() -> markdown.Markdown:
    return markdown.Markdown(
        extensions=MARKDOWN_EXTENSIONS, extension_configs=MARKDOWN_EXTENSION_CONFIGS
    )


def registered_patterns() -> dict[str, Any]:
    md = library_markdown()
    patterns = {}
    for processor in PATTERN_REGISTRIES:
        registry = md.treeprocessors[processor].inlinePatterns
        for name in [item.name for item in registry._priority]:
            patterns[name] = registry[name]
    return patterns


def test_the_library_still_has_the_methods_this_relies_on() -> None:
    assert hasattr(InlineProcessor, "_InlineProcessor__handleInline")
    assert hasattr(InlineProcessor, "_InlineProcessor__applyPattern")


def test_every_pattern_has_an_entry() -> None:
    assert set(registered_patterns()) == set(REQUIRED_TEXT)


def test_processors_keep_their_places() -> None:
    fast, library = make_markdown(), library_markdown()
    fast.treeprocessors._sort()
    library.treeprocessors._sort()
    places = [(item.name, item.priority) for item in library.treeprocessors._priority]
    assert [
        (item.name, item.priority) for item in fast.treeprocessors._priority
    ] == places
    assert set(INLINE_PROCESSOR_PRIORITIES.items()) <= set(places)


def test_atomic_text_is_left_alone() -> None:
    processor = make_markdown().treeprocessors["inline"]
    processor.stashed_nodes = {}
    processor.ancestors = []
    text = AtomicString("*a* and `b`")
    assert processor._InlineProcessor__handleInline(text) == text


@pytest.mark.parametrize("name", sorted(REQUIRED_TEXT))
def test_a_pattern_cannot_match_without_its_required_text(name: str) -> None:
    expression = registered_patterns()[name].getCompiledRegExp()
    required = REQUIRED_TEXT[name]
    rng = random.Random(name)
    alphabet = string.printable + "".join(FRAGMENTS)
    for _ in range(3000):
        text = "".join(rng.choices(FRAGMENTS + list(alphabet), k=rng.randint(1, 30)))
        while any(piece in text for piece in required):
            for piece in required:
                text = text.replace(piece, "")
        assert expression.search(text) is None, text


@pytest.mark.parametrize("seed", range(40))
def test_random_markdown_converts_as_the_library_does(seed: int) -> None:
    fast, library = make_markdown(), library_markdown()
    rng = random.Random(seed)
    for _ in range(25):
        source = "".join(rng.choices(FRAGMENTS, k=rng.randint(1, 40)))
        expected = library.convert(source)
        library.reset()
        assert fast.convert(source) == expected, repr(source)
        fast.reset()
