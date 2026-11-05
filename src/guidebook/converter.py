"""From Markdown to HTML: pyromark, with the book's additions around it.

pyromark follows CommonMark. Boxes are read before it runs, and code colours, math and
heading anchors are added to what it returns, in the HTML that :mod:`guidebook.passes`
expects.
"""

import html
import re
import unicodedata

import pyromark
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexer import Lexer
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.util import ClassNotFound

from guidebook.config import MARKDOWN_OPTIONS

# Spaces that a box's text is indented by, as in Python-Markdown's admonitions.
BOX_INDENT = 4

# A box's text stands in the page as a marker while pyromark runs. Private-use
# characters cannot come from a book by accident.
_BOX_MARKER = "\ue000box{}\ue001"

_BOX_PATTERN = re.compile(
    r"^(?P<indent> *)(?P<marker>!!!|\?\?\?\+?) +(?P<kinds>[\w-]+(?: +[\w-]+)*)"
    r'(?: +"(?P<title>[^"]*)")? *$'
)
_FENCE_PATTERN = re.compile(r"^ *(?:```|~~~)")
_PARAGRAPH_WRAPPER_PATTERN = re.compile(r"^<p>|</p>$")
_DISPLAY_MATH_PATTERN = re.compile(
    r'(?:<p>)?<span class="math math-display">(.*?)</span>(?:</p>)?', re.S
)
_INLINE_MATH_PATTERN = re.compile(r'<span class="math math-inline">(.*?)</span>', re.S)
_CODE_PATTERN = re.compile(
    r'<pre><code(?: class="language-([^"]+)")?>(.*?)</code></pre>', re.S
)
_HEADING_PATTERN = re.compile(r"<h([1-6])((?: [^>]*)?)>(.*?)</h\1>", re.S)
_HEADING_ID_PATTERN = re.compile(r'<h[1-6][^>]* id="([^"]+)"')
_TAG_PATTERN = re.compile(r"<[^>]+>")

# Python-Markdown's rule for turning a heading into an anchor, which books link to.
# https://github.com/Python-Markdown/markdown/blob/3.11.3/markdown/extensions/toc.py#L33
_NON_WORD_PATTERN = re.compile(r"[^\w\s-]")
_SEPARATOR_PATTERN = re.compile(r"[-\s]+")
_NUMBERED_ANCHOR_PATTERN = re.compile(r"^(.*)_([0-9]+)$")

_CODE_FORMATTER = HtmlFormatter(cssclass="highlight", wrapcode=True)


def convert_markdown(text: str) -> str:
    """Return the HTML of the Markdown `text`."""
    boxes: dict[str, str] = {}
    body = _convert_blocks(text, boxes)
    # A box was written after the boxes inside it, so the last holds the earlier ones.
    for marker, box in reversed(boxes.items()):
        body = body.replace(f"<p>{marker}</p>", box).replace(marker, box)
    return _add_heading_anchors(body).strip()


def _parse(text: str) -> str:
    return _set_math(pyromark.html(text, options=MARKDOWN_OPTIONS))


def _convert_blocks(text: str, boxes: dict[str, str]) -> str:
    return _set_code(_parse(_lift_boxes(text, boxes)))


def _lift_boxes(text: str, boxes: dict[str, str]) -> str:
    """Convert each box in `text` and leave a marker for it in `boxes`."""
    lines = text.split("\n")
    kept: list[str] = []
    in_fence = False
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if _FENCE_PATTERN.match(line):
            in_fence = not in_fence
        match = None if in_fence else _BOX_PATTERN.match(line)
        if match is None:
            kept.append(line)
            continue
        indent = len(match["indent"])
        start = index
        while index < len(lines) and _belongs_to_box(lines[index], indent):
            index += 1
        body = "\n".join(line[indent + BOX_INDENT :] for line in lines[start:index])
        box = _box_html(match, _convert_blocks(body.rstrip(), boxes).strip())
        marker = _BOX_MARKER.format(len(boxes))
        boxes[marker] = box
        kept += ["", match["indent"] + marker, ""]
    return "\n".join(kept)


def _belongs_to_box(line: str, indent: int) -> bool:
    return not line.strip() or len(line) - len(line.lstrip(" ")) >= indent + BOX_INDENT


def _box_html(match: re.Match[str], body: str) -> str:
    kinds = match["kinds"]
    title = match["title"]
    if title is None:
        title = kinds.split()[0].capitalize()
    title_html = _PARAGRAPH_WRAPPER_PATTERN.sub("", _parse(title).strip())
    if match["marker"] == "!!!":
        head = f'<p class="admonition-title">{title_html}</p>\n' if title else ""
        return f'<div class="admonition {kinds}">\n{head}{body}\n</div>'
    is_open = ' open="open"' if match["marker"].endswith("+") else ""
    return (
        f'<details class="{kinds}"{is_open}>\n<summary>{title_html}</summary>\n'
        f"{body}\n</details>"
    )


def _set_math(body: str) -> str:
    """Put math in the delimiters MathJax and the equation numbering read."""
    body = _DISPLAY_MATH_PATTERN.sub(r'<div class="arithmatex">\\[\1\\]</div>', body)
    return _INLINE_MATH_PATTERN.sub(r'<span class="arithmatex">\\(\1\\)</span>', body)


def _lexer_for(language: str | None) -> Lexer:
    lexer: Lexer = TextLexer(stripnl=False)
    if language:
        try:
            lexer = get_lexer_by_name(language, stripnl=False)
        except ClassNotFound:
            pass
    return lexer


def _set_code(body: str) -> str:
    """Give each code block its colours."""

    def replace(match: re.Match[str]) -> str:
        source = html.unescape(match.group(2))
        code = highlight(source, _lexer_for(match.group(1)), _CODE_FORMATTER)
        return str(code).rstrip("\n")

    return _CODE_PATTERN.sub(replace, body)


def _slugify(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return _SEPARATOR_PATTERN.sub("-", _NON_WORD_PATTERN.sub("", plain).strip().lower())


def _unique(anchor: str, used: set[str]) -> str:
    while anchor in used or not anchor:
        match = _NUMBERED_ANCHOR_PATTERN.match(anchor)
        if match:
            anchor = f"{match.group(1)}_{int(match.group(2)) + 1}"
        else:
            anchor = f"{anchor}_1"
    used.add(anchor)
    return anchor


def _add_heading_anchors(body: str) -> str:
    """Give each heading without an id one made from its text."""
    used = set(_HEADING_ID_PATTERN.findall(body))

    def replace(match: re.Match[str]) -> str:
        level, attributes, content = match.groups()
        if ' id="' in attributes:
            return match.group(0)
        plain = html.unescape(_TAG_PATTERN.sub("", content))
        anchor = _unique(_slugify(plain), used)
        return f'<h{level} id="{anchor}"{attributes}>{content}</h{level}>'

    return _HEADING_PATTERN.sub(replace, body)
