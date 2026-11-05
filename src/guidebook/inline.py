"""A faster inline pass over Markdown text, with the same result as the library's own.

Python-Markdown tries every inline pattern on every piece of text, twice over with the
``smarty`` extension, and that search is the largest cost of a build. Most patterns
cannot match most text, because their regular expression needs a character the text
lacks, so :class:`SkippingInlineProcessor` tries a pattern only if that character is
there. A pattern with no entry in :data:`REQUIRED_TEXT` is always tried.
"""

from typing import Any

import markdown
from markdown import util
from markdown.treeprocessors import InlineProcessor

# The tree processors that run inline patterns, by name, with the priorities that
# Python-Markdown gives them.
# https://github.com/Python-Markdown/markdown/blob/3.11.3/markdown/treeprocessors.py#L48
# https://github.com/Python-Markdown/markdown/blob/3.11.3/markdown/extensions/smarty.py#L290
INLINE_PROCESSOR_PRIORITIES = {"inline": 20, "smarty": 6}

# The number of quote patterns the smarty extension registers.
# https://github.com/Python-Markdown/markdown/blob/3.11.3/markdown/extensions/smarty.py#L235
_SMARTY_QUOTE_PATTERNS = 15

# For each pattern, by its registered name, the strings of which its regular expression
# needs at least one. tests/test_inline.py checks each entry against the expression.
# https://github.com/Python-Markdown/markdown/blob/3.11.3/markdown/inlinepatterns.py#L77
# https://github.com/facelessuser/pymdown-extensions/blob/12.3/pymdownx/inlinehilite.py
# https://github.com/facelessuser/pymdown-extensions/blob/12.3/pymdownx/arithmatex.py
# https://github.com/facelessuser/pymdown-extensions/blob/12.3/pymdownx/keys.py
REQUIRED_TEXT: dict[str, tuple[str, ...]] = {
    "backtick": ("`",),
    "arithmatex-inline": ("$", "\\"),
    "keys-custom": ("+",),
    "escape": ("\\",),
    "footnote": ("[^",),
    "reference": ("[",),
    "link": ("[",),
    "image_link": ("![",),
    "image_reference": ("![",),
    "short_reference": ("[",),
    "short_image_ref": ("![",),
    "autolink": ("<",),
    "automail": ("<",),
    "linebreak": ("  \n",),
    "html": ("<",),
    "entity": ("&",),
    "keys": ("++",),
    "delimiter": ("*", "_"),
    "smarty-em-dashes": ("---",),
    "smarty-en-dashes": ("--",),
    "smarty-ellipses": ("...",),
    **{f"smarty-quotes-{n}": ("'", '"') for n in range(_SMARTY_QUOTE_PATTERNS)},
}


class SkippingInlineProcessor(InlineProcessor):
    """An inline processor that leaves out the patterns a text cannot match.

    Parameters
    ----------
    md : markdown.Markdown
        The converter this processor belongs to.
    patterns : markdown.util.Registry
        The patterns to run, in the order of the processor this one replaces.
    """

    def __init__(self, md: markdown.Markdown, patterns: Any) -> None:
        super().__init__(md)
        self.inlinePatterns = patterns
        required = {
            id(patterns[name]): text
            for name, text in REQUIRED_TEXT.items()
            if name in patterns
        }
        self.steps = [(pattern, required.get(id(pattern))) for pattern in patterns]

    # The library's own loop, under the name it calls it by, with the check added. If a
    # release renames the method, the library's loop runs and the result is the same.
    def _InlineProcessor__handleInline(self, data: str, patternIndex: int = 0) -> str:
        if isinstance(data, util.AtomicString):
            return data
        steps = self.steps
        count = len(steps)
        start_index = 0
        while patternIndex < count:
            pattern, required_text = steps[patternIndex]
            if start_index == 0 and required_text is not None:
                for text in required_text:
                    if text in data:
                        break
                else:
                    patternIndex += 1
                    continue
            data, matched, start_index = self._InlineProcessor__applyPattern(  # type: ignore[attr-defined]
                pattern, data, patternIndex, start_index
            )
            if not matched:
                patternIndex += 1
        return data


def skip_impossible_patterns(md: markdown.Markdown) -> None:
    """Replace the inline processors of `md` with ones that skip what cannot match."""
    for name, priority in INLINE_PROCESSOR_PRIORITIES.items():
        if name in md.treeprocessors:
            library_processor: Any = md.treeprocessors[name]
            processor = SkippingInlineProcessor(md, library_processor.inlinePatterns)
            md.treeprocessors.register(processor, name, priority)
