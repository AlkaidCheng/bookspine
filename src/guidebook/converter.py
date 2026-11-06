"""From Markdown to HTML: pulldown-cmark, with the book's additions around it.

pulldown-cmark follows CommonMark. One walk over a page's lines takes out what it cannot
read, such as boxes and footnotes, and the rest is added to what it returns, in the HTML
that :mod:`guidebook.passes` expects.
"""

import html
import re
import unicodedata
from dataclasses import dataclass, field

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexer import Lexer
from pygments.lexers import TextLexer, get_lexer_by_name
from pygments.util import ClassNotFound

from guidebook import _markdown
from guidebook.config import MARKDOWN_OPTIONS
from guidebook.keys import KEY_ALIASES, KEY_LABELS

# Spaces that the text of a box or a footnote is indented by.
BLOCK_INDENT = 4

# The tooltip of a link from a footnote back to the text.
FOOTNOTE_BACKLINK_TITLE = "Back to text"

# What the walk takes out stands in the page as a marker while pulldown-cmark runs.
# Private-use characters cannot come from a book by accident.
_BLOCK_MARKER = "\ue000{}\ue001"
_INLINE_MARKER = "\ue006{}\ue007"
_ATTRIBUTE_MARKER = "\ue002{}\ue003"
_CODE_OPTIONS_MARKER = "\ue004{}\ue005"

# Lines the walk looks for.
_BOX_PATTERN = re.compile(
    r"^(?P<indent> *)(?P<marker>!!!|\?\?\?\+?) +(?P<kinds>[\w-]+(?: +[\w-]+)*)"
    r'(?: +"(?P<title>[^"]*)")? *$'
)
_FENCE_PATTERN = re.compile(r"^(?P<indent> *)(?P<fence>`{3,}|~{3,})[ \t]*(?P<info>.*)$")
_CODE_OPTION_PATTERN = re.compile(r'(\w+)="([^"]*)"')
_FOOTNOTE_PATTERN = re.compile(r"^\[\^(?P<label>[^\]\s]+)\]:[ \t]*(?P<text>.*)$")
_ABBREVIATION_PATTERN = re.compile(r"^\*\[(?P<word>[^\]]+)\]:[ \t]*(?P<title>.*)$")
_ATTRIBUTE_LINE_PATTERN = re.compile(r"^ *\{:\s*(?P<attributes>[^}]*?)\s*\}\s*$")
_ATTRIBUTE_PATTERN = re.compile(
    r"\.(?P<class>[\w-]+)|#(?P<id>[\w-]+)"
    r"|(?P<key>[\w-]+)=(?:\"(?P<quoted>[^\"]*)\"|(?P<bare>\S+))"
)
_MATH_START_PATTERN = re.compile(r"^(?P<indent> *)(?:\\begin\{(?P<name>[\w*]+)\}|\\\[)")
_INLINE_MATH_PATTERN = re.compile(r"(?P<code>(`+).+?\2)|\\\((?P<math>.+?)\\\)")

# What pulldown-cmark returns.
_PARAGRAPH_WRAPPER_PATTERN = re.compile(r"^<p>|</p>$")
_DISPLAY_SPAN_PATTERN = re.compile(
    r'(?:<p>)?<span class="math math-display">(.*?)</span>(?:</p>)?', re.S
)
_INLINE_SPAN_PATTERN = re.compile(r'<span class="math math-inline">(.*?)</span>', re.S)
_CODE_BLOCK_PATTERN = re.compile(
    r'<pre><code(?: class="language-([^"\ue004]*)(?:\ue004(\d+)\ue005)?")?>'
    r"(.*?)</code></pre>",
    re.S,
)
_INLINE_CODE_PATTERN = re.compile(r"<code>(?:#!|:::)([\w#+.-]+) (.+?)</code>")
_ATTRIBUTE_TARGET_PATTERN = re.compile(
    r"<(p|li)>((?:(?!</\1>).)*?) \ue002(\d+)\ue003</\1>", re.S
)
_LEFTOVER_ATTRIBUTE_PATTERN = re.compile(r" ?\ue002\d+\ue003")
_HEADING_PATTERN = re.compile(r"<h([1-6])((?: [^>]*)?)>(.*?)</h\1>", re.S)
_HEADING_ID_PATTERN = re.compile(r'<h[1-6][^>]* id="([^"]+)"')
_TAG_PATTERN = re.compile(r"<[^>]+>")

# What the marks in running text leave alone: tags, code and math.
_PROTECTED_PATTERN = re.compile(
    r"(<pre.*?</pre>|<code.*?</code>"
    r'|<(?:span|div) class="arithmatex">.*?</(?:span|div)>|<[^>]+>)',
    re.S,
)
_FOOTNOTE_REFERENCE = r"\[\^(?P<footnote>[^\]\s]+)\]"
_KEYS = r"\+\+(?P<keys>[\w-]+(?:\+[\w-]+)*?)\+\+"

# Python-Markdown's rule for turning a heading into an anchor, which books link to,
# under the BSD license in LICENSES/Python-Markdown.txt.
# https://github.com/Python-Markdown/markdown/blob/3.11.3/markdown/extensions/toc.py#L33
_NON_WORD_PATTERN = re.compile(r"[^\w\s-]")
_SEPARATOR_PATTERN = re.compile(r"[-\s]+")
_NUMBERED_ANCHOR_PATTERN = re.compile(r"^(.*)_([0-9]+)$")


@dataclass
class _Extras:
    """What the walk over a page's lines takes out, for the page to get back."""

    blocks: dict[str, str] = field(default_factory=dict)
    attributes: list[str] = field(default_factory=list)
    code_options: list[dict[str, str]] = field(default_factory=list)
    abbreviations: dict[str, str] = field(default_factory=dict)
    footnotes: dict[str, str] = field(default_factory=dict)
    footnote_references: dict[str, int] = field(default_factory=dict)

    def mark(self, block: str, marker_format: str = _BLOCK_MARKER) -> str:
        """Return a marker for the HTML `block`."""
        marker = marker_format.format(len(self.blocks))
        self.blocks[marker] = block
        return marker

    def restore(self, body: str) -> str:
        """Return `body` with its markers replaced by what they stand for."""
        # A box was marked after the blocks inside it, so the last holds earlier ones.
        for marker, block in reversed(self.blocks.items()):
            if marker[0] == _BLOCK_MARKER[0]:
                body = body.replace(f"<p>{marker}</p>", block)
            body = body.replace(marker, block)
        return body


def convert_markdown(text: str) -> str:
    """Return the HTML of the Markdown `text`."""
    extras = _Extras()
    # The walk measures indentation in spaces.
    blocks = _convert_blocks(text.expandtabs(BLOCK_INDENT), extras)
    body = _set_attributes(extras.restore(blocks), extras)
    body = _mark_text(body, extras)
    return _add_heading_anchors(body + _footnotes_html(extras)).strip()


def _parse(text: str) -> str:
    html_text = _markdown.to_html(text, MARKDOWN_OPTIONS)
    return _set_inline_code(_set_math(html_text))


def _convert_blocks(text: str, extras: _Extras) -> str:
    return _set_code_blocks(_parse(_lift(text, extras)), extras)


def _lift(text: str, extras: _Extras) -> str:
    """Take what pulldown-cmark cannot read out of `text`, and return what is left."""
    lines = text.split("\n")
    kept: list[str] = []
    fence = ""
    in_display_math = False
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        opening = _FENCE_PATTERN.match(line)
        if fence:
            if opening and _closes_fence(opening, fence):
                fence = ""
            kept.append(line)
        elif opening:
            fence = opening["fence"]
            kept.append(_lift_code_options(opening, extras))
        elif line.count("$$") % 2:
            in_display_math = not in_display_math
            kept.append(line)
        elif in_display_math:
            kept.append(line)
        elif box := _BOX_PATTERN.match(line):
            index = _lift_box(box, lines, index, kept, extras)
        elif footnote := _FOOTNOTE_PATTERN.match(line):
            index = _lift_footnote(footnote, lines, index, extras)
        elif abbreviation := _ABBREVIATION_PATTERN.match(line):
            extras.abbreviations[abbreviation["word"]] = abbreviation["title"].strip()
        elif _follows_blank(kept) and (math := _MATH_START_PATTERN.match(line)):
            index = _lift_display_math(math, lines, index, kept, extras)
        elif (attributes := _ATTRIBUTE_LINE_PATTERN.match(line)) and _ends_text(kept):
            # The space keeps a closing quote before the marker a closing quote.
            kept[-1] += " " + _ATTRIBUTE_MARKER.format(len(extras.attributes))
            extras.attributes.append(attributes["attributes"])
        else:
            kept.append(_lift_inline_math(line, extras))
    return "\n".join(kept)


def _closes_fence(line: re.Match[str], fence: str) -> bool:
    candidate = line["fence"]
    return (
        candidate[0] == fence[0] and len(candidate) >= len(fence) and not line["info"]
    )


def _follows_blank(kept: list[str]) -> bool:
    return not kept or not kept[-1].strip()


def _ends_text(kept: list[str]) -> bool:
    return not _follows_blank(kept) and not kept[-1].lstrip().startswith("#")


def _indented_lines(lines: list[str], index: int, indent: int) -> int:
    """Return the index after the blank or indented lines from `index`."""
    while index < len(lines):
        line = lines[index]
        if line.strip() and len(line) - len(line.lstrip(" ")) < indent:
            break
        index += 1
    return index


def _lift_box(
    box: re.Match[str], lines: list[str], index: int, kept: list[str], extras: _Extras
) -> int:
    indent = len(box["indent"])
    end = _indented_lines(lines, index, indent + BLOCK_INDENT)
    body = "\n".join(line[indent + BLOCK_INDENT :] for line in lines[index:end])
    converted = _convert_blocks(body.rstrip(), extras).strip()
    kept += ["", box["indent"] + extras.mark(_box_html(box, converted)), ""]
    return end


def _box_html(box: re.Match[str], body: str) -> str:
    kinds = box["kinds"]
    title = box["title"]
    if title is None:
        title = kinds.split()[0].capitalize()
    title_html = _PARAGRAPH_WRAPPER_PATTERN.sub("", _parse(title).strip())
    if box["marker"] == "!!!":
        head = f'<p class="admonition-title">{title_html}</p>\n' if title else ""
        return f'<div class="admonition {kinds}">\n{head}{body}\n</div>'
    is_open = ' open="open"' if box["marker"].endswith("+") else ""
    return (
        f'<details class="{kinds}"{is_open}>\n<summary>{title_html}</summary>\n'
        f"{body}\n</details>"
    )


def _lift_footnote(
    footnote: re.Match[str], lines: list[str], index: int, extras: _Extras
) -> int:
    body = [footnote["text"]]
    # The lines straight after a definition belong to it, indented or not.
    while index < len(lines) and lines[index].strip():
        if _FOOTNOTE_PATTERN.match(lines[index]):
            break
        body.append(lines[index].removeprefix(" " * BLOCK_INDENT))
        index += 1
    end = _indented_lines(lines, index, BLOCK_INDENT)
    body += [line[BLOCK_INDENT:] for line in lines[index:end]]
    text = "\n".join(body).rstrip()
    extras.footnotes[footnote["label"]] = _convert_blocks(text, extras).strip()
    return end


def _lift_display_math(
    math: re.Match[str], lines: list[str], index: int, kept: list[str], extras: _Extras
) -> int:
    closing = rf"\end{{{math['name']}}}" if math["name"] else r"\]"
    end = index - 1
    while end < len(lines) and not lines[end].rstrip().endswith(closing):
        end += 1
    if end == len(lines):
        kept.append(_lift_inline_math(lines[index - 1], extras))
        return index
    source = "\n".join(lines[index - 1 : end + 1]).strip()
    if math["name"]:
        source = rf"\[{source}\]"
    block = f'<div class="arithmatex">{html.escape(source, quote=False)}</div>'
    kept.append(math["indent"] + extras.mark(block))
    return end + 1


def _lift_inline_math(line: str, extras: _Extras) -> str:
    def replace(match: re.Match[str]) -> str:
        if match["code"]:
            return match.group(0)
        source = html.escape(match["math"], quote=False)
        span = rf'<span class="arithmatex">\({source}\)</span>'
        return extras.mark(span, _INLINE_MARKER)

    return _INLINE_MATH_PATTERN.sub(replace, line)


def _lift_code_options(opening: re.Match[str], extras: _Extras) -> str:
    info = opening["info"]
    options = dict(_CODE_OPTION_PATTERN.findall(info))
    if not options:
        return opening.group(0)
    # A first word that is an option names no language, so it reads as plain text.
    language = info.split(maxsplit=1)[0]
    marker = _CODE_OPTIONS_MARKER.format(len(extras.code_options))
    extras.code_options.append(options)
    return f"{opening['indent']}{opening['fence']}{language}{marker}"


def _set_math(body: str) -> str:
    """Put math in the delimiters MathJax and the equation numbering read."""
    body = _DISPLAY_SPAN_PATTERN.sub(r'<div class="arithmatex">\\[\1\\]</div>', body)
    return _INLINE_SPAN_PATTERN.sub(r'<span class="arithmatex">\\(\1\\)</span>', body)


def _lexer_for(language: str | None) -> Lexer:
    lexer: Lexer = TextLexer(stripnl=False)
    if language:
        try:
            lexer = get_lexer_by_name(language, stripnl=False)
        except ClassNotFound:
            pass
    return lexer


def _set_inline_code(body: str) -> str:
    """Give the colours of its language to code such as ```#!python x = 1```."""

    def replace(match: re.Match[str]) -> str:
        lexer = _lexer_for(match.group(1))
        source = html.unescape(match.group(2))
        code = highlight(source, lexer, HtmlFormatter(nowrap=True))
        return f'<code class="highlight">{str(code).rstrip()}</code>'

    return _INLINE_CODE_PATTERN.sub(replace, body)


def _marked_lines(text: str) -> list[int]:
    """Return the line numbers in `text`, a list of numbers and ranges like ``1 3-4``."""
    numbers: list[int] = []
    for part in text.split():
        first, _, last = part.partition("-")
        if first.isdigit() and (not last or last.isdigit()):
            numbers += range(int(first), int(last or first) + 1)
    return numbers


def _numbered_code_html(
    source: str, lexer: Lexer, marked: list[int], title: str, first: int
) -> str:
    code = highlight(source, lexer, HtmlFormatter(nowrap=True, hl_lines=marked))
    numbers = "\n".join(
        f'<span class="normal">{number}</span>'
        for number in range(first, first + len(source.splitlines()))
    )
    head = ""
    if title:
        name = html.escape(title)
        head = (
            '<tr><th colspan="2" class="filename">'
            f'<span class="filename">{name}</span></th></tr>'
        )
    return (
        f'<div class="highlight"><table class="highlighttable">{head}<tr>'
        '<td class="linenos"><div class="linenodiv"><pre><span></span>'
        f'{numbers}</pre></div></td><td class="code"><div><pre><span></span><code>{code}'
        "</code></pre></div></td></tr></table></div>"
    )


def _code_html(source: str, language: str | None, options: dict[str, str]) -> str:
    lexer = _lexer_for(language)
    title = options.get("title", "")
    marked = _marked_lines(options.get("hl_lines", ""))
    if "linenums" in options:
        first_word = (options["linenums"].split() or ["1"])[0]
        first = int(first_word) if first_word.isdigit() else 1
        return _numbered_code_html(source, lexer, marked, title, first)
    formatter = HtmlFormatter(
        cssclass="highlight", wrapcode=True, filename=title, hl_lines=marked
    )
    return str(highlight(source, lexer, formatter)).rstrip("\n")


def _set_code_blocks(body: str, extras: _Extras) -> str:
    """Give each code block its colours and options."""

    def replace(match: re.Match[str]) -> str:
        language, options_index, code = match.groups()
        options = extras.code_options[int(options_index)] if options_index else {}
        return _code_html(html.unescape(code), language, options)

    return _CODE_BLOCK_PATTERN.sub(replace, body)


def _attributes_html(text: str) -> str:
    attributes: dict[str, str] = {}
    for match in _ATTRIBUTE_PATTERN.finditer(text):
        if match["class"]:
            classes = attributes.get("class")
            attributes["class"] = (
                f"{classes} {match['class']}" if classes else match["class"]
            )
        elif match["id"]:
            attributes["id"] = match["id"]
        else:
            attributes[match["key"]] = match["quoted"] or match["bare"] or ""
    return "".join(f' {k}="{html.escape(v)}"' for k, v in attributes.items())


def _set_attributes(body: str, extras: _Extras) -> str:
    """Move each attribute line's attributes onto its paragraph or list item."""

    def replace(match: re.Match[str]) -> str:
        tag, content, index = match.groups()
        attributes = _attributes_html(extras.attributes[int(index)])
        return f"<{tag}{attributes}>{content}</{tag}>"

    body = _ATTRIBUTE_TARGET_PATTERN.sub(replace, body)
    return _LEFTOVER_ATTRIBUTE_PATTERN.sub("", body)


def _keys_html(names: str) -> str | None:
    """Return the HTML of ``ctrl+a``, or None if a name is not a key."""
    keys = [KEY_ALIASES.get(name, name) for name in names.split("+")]
    if not all(key in KEY_LABELS for key in keys):
        return None
    labels = (f'<kbd class="key-{key}">{KEY_LABELS[key]}</kbd>' for key in keys)
    return f'<span class="keys">{"<span>+</span>".join(labels)}</span>'


def _footnote_reference_html(label: str, extras: _Extras) -> str:
    count = extras.footnote_references.get(label, 0) + 1
    extras.footnote_references[label] = count
    number = list(extras.footnotes).index(label) + 1
    anchor = html.escape(label)
    prefix = "fnref" if count == 1 else f"fnref{count}"
    return (
        f'<sup id="{prefix}:{anchor}"><a class="footnote-ref" href="#fn:{anchor}">'
        f"{number}</a></sup>"
    )


def _mark_text(body: str, extras: _Extras) -> str:
    """Add footnote references, keys and abbreviations to running text."""
    alternatives = [_FOOTNOTE_REFERENCE, _KEYS]
    if extras.abbreviations:
        words = sorted(extras.abbreviations, key=len, reverse=True)
        alternatives.append(rf"\b(?P<word>{'|'.join(map(re.escape, words))})\b")
    pattern = re.compile("|".join(alternatives))

    def replace(match: re.Match[str]) -> str:
        if match["footnote"]:
            if match["footnote"] not in extras.footnotes:
                return match.group(0)
            return _footnote_reference_html(match["footnote"], extras)
        if match["keys"]:
            return _keys_html(match["keys"]) or match.group(0)
        word = match.group(0)
        title = html.escape(extras.abbreviations[word])
        return f'<abbr title="{title}">{word}</abbr>'

    parts = _PROTECTED_PATTERN.split(body)
    parts[::2] = [pattern.sub(replace, part) for part in parts[::2]]
    return "".join(parts)


def _footnotes_html(extras: _Extras) -> str:
    """Return the list of the page's footnotes, with links back to the text."""
    items = []
    for label, text in extras.footnotes.items():
        body = _mark_text(_set_attributes(extras.restore(text), extras), extras)
        anchor = html.escape(label)
        count = extras.footnote_references.get(label, 1)
        backlinks = "&#160;" + "".join(
            f'<a class="footnote-backref" href="#fnref{"" if n == 1 else n}:{anchor}" '
            f'title="{FOOTNOTE_BACKLINK_TITLE}">&#8617;</a>'
            for n in range(1, count + 1)
        )
        if body.endswith("</p>"):
            body = f"{body[: -len('</p>')]}{backlinks}</p>"
        else:
            body = f"{body}\n<p>{backlinks}</p>"
        items.append(f'<li id="fn:{anchor}">\n{body}\n</li>')
    if not items:
        return ""
    listed = "\n".join(items)
    return f'\n<div class="footnote">\n<hr />\n<ol>\n{listed}\n</ol>\n</div>'


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
