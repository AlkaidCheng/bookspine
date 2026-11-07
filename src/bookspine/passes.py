"""The passes over a page's HTML: numbers, citations, links and the search index."""

import html
import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from bookspine.config import (
    EQUATION_ANCHOR_PREFIX,
    LABELLED_BOXES,
    NUMBERED_BOXES,
    SEARCH_CRUMB_SEPARATOR,
    SEARCH_TEXT_LIMIT,
    UNNUMBERED_HEADINGS,
)
from bookspine.converter import convert_markdown
from bookspine.errors import BuildError
from bookspine.pages import Page

# The pages whose head shows a lede in the reference layout.
LEDE_KINDS = {"part", "chapter", "section"}

CODE_SEGMENT_PATTERN = re.compile(r"(<pre.*?</pre>|<code.*?</code>)", re.S)
_HEADING_PATTERN = re.compile(r'<h([23]) id="([^"]+)">(.*?)</h\1>', re.S)
_FIGURE_PATTERN = re.compile(r"<p>(<img [^>]*>)</p>")
_TABLE_CAPTION_PATTERN = re.compile(
    r"(<table>.*?</table>)\s*(?:<p>Table:\s*(.*?)</p>)?", re.S
)
_IMG_ALT_PATTERN = re.compile(r'alt="([^"]*)"')
_IMG_SRC_PATTERN = re.compile(r'src="([^"]+)"')
_XML_DECLARATION_PATTERN = re.compile(r"<\?xml[^>]*\?>\s*")
# One pattern, so that open and collapsible boxes share a count in reading order.
_BOX_PATTERN = re.compile(
    r'<(?:div class="admonition |details class=")([\w-]+)( [\w -]+)?"( open="open")?>\s*'
    r'<(?:p class="admonition-title"|summary)>(.*?)</(?:p|summary)>',
    re.S,
)
_CITE_PATTERN = re.compile(r"\[@([^\]]+)\]")
_LINK_PATTERN = re.compile(r'(href|src)="([^"]*)"')
_LINK_SCHEME_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*:")
_ID_PATTERN = re.compile(r'\sid="([^"]+)"')
_SAME_PAGE_LINK_PATTERN = re.compile(r'href="#([^"]+)"')
_TAG_PATTERN = re.compile(r"<[^>]+>")
_TAB_LABEL_PATTERN = re.compile(r'<label for="__tabbed_.*?</label>', re.S)
_EXTERNAL_LINK_PATTERN = re.compile(
    r'<a href="(https?://[^"]+)" class="external" rel="noopener">([^<\s]+)</a>'
)
_CODE_BLOCK_PATTERN = re.compile(
    r'(<div class="highlight">(?:<span class="filename">[^<]*</span>)?'
    r"<pre><span></span><code>)(.*?)(</code></pre>)",
    re.S,
)
_CODE_LINE_PATTERN = re.compile(r".*\n|.+")
_PRE_PATTERN = re.compile(r"(<pre.*?</pre>)", re.S)
_PLAIN_CODE_PATTERN = re.compile(r"<code>([^<]*)</code>")
_LEDE_PATTERN = re.compile(r"\A\s*<p>(.*?)</p>", re.S)
_PARAGRAPH_WRAPPER_PATTERN = re.compile(r"^<p>|</p>$")
_URL_SCHEME_PATTERN = re.compile(r"https?://")
# After a colon, a double slash, an equals sign or an ampersand, and before a single
# slash or other punctuation, as The Chicago Manual of Style has it in 7.46, "Dividing
# URLs and email addresses". A slash or mark that ends the address stays with it.
_URL_BREAK_PATTERN = re.compile(
    r"(?<=:)(?!//)|(?<=//)|(?<=[=&])|(?<![:/])(?=/.)|(?=(?:[^\w/:=&]|_).)"
)


def outside_code(text: str, transform: Callable[[str], str]) -> str:
    """Apply `transform` to the parts of `text` that are not code."""
    segments = CODE_SEGMENT_PATTERN.split(text)
    return "".join(
        segment if index % 2 else transform(segment)
        for index, segment in enumerate(segments)
    )


def inline_html(markdown: str) -> str:
    """Return the HTML of the one-paragraph `markdown`, without its paragraph tags."""
    return _PARAGRAPH_WRAPPER_PATTERN.sub("", convert_markdown(markdown).strip())


def anchor_link(anchor: str) -> str:
    """Return a permalink that copies the shareable URL of the element when clicked."""
    return (
        f' <a class="anchor" href="#{anchor}" title="Copy link to this place"'
        f' aria-label="Copy link to this place">§</a>'
    )


def number_headings(page: Page) -> None:
    """Prefix H2/H3 with section numbers and collect the page's section list."""
    counters = [0, 0]
    sections: list[dict[str, Any]] = []

    def replace(match: re.Match[str]) -> str:
        level, anchor, text = int(match.group(1)), match.group(2), match.group(3)
        plain = html.unescape(re.sub(r"<[^>]+>", "", text)).strip()
        unnumbered = "unnumbered" in text or plain.lower() in UNNUMBERED_HEADINGS
        if level == 2:
            counters[1] = 0
            if not unnumbered:
                counters[0] += 1
        elif not unnumbered:
            counters[1] += 1
        if unnumbered or not page.has_numbered_headings:
            label = ""
        elif level == 2:
            label = f"{page.number}.{counters[0]}"
        else:
            label = f"{page.number}.{counters[0]}.{counters[1]}"
        sections.append({"level": level, "id": anchor, "title": plain, "number": label})
        prefix = f'<span class="secnum">{label}</span> ' if label else ""
        return f'<h{level} id="{anchor}">{prefix}{text}{anchor_link(anchor)}</h{level}>'

    page.body_html = _HEADING_PATTERN.sub(replace, page.body_html)
    page.sections = sections


def inline_svg(page: Page, img: str, caption: str, book_dir: Path) -> str | None:
    """Embed a local SVG figure so it can use the page's colour tokens.

    Raises
    ------
    BuildError
        If the figure is missing.
    """
    src = _IMG_SRC_PATTERN.search(img)
    if not src or not src.group(1).endswith(".svg") or "://" in src.group(1):
        return None
    path = book_dir / page.source_path.parent / src.group(1)
    if not path.is_file():
        raise BuildError(f"{page.source_path}: missing figure: {src.group(1)}")
    svg = _XML_DECLARATION_PATTERN.sub("", path.read_text(encoding="utf-8")).strip()
    title = html.escape(caption, quote=True)
    return svg.replace(
        "<svg", f'<svg class="inline-svg" role="img" aria-label="{title}"', 1
    )


def number_figures_and_tables(page: Page, book_dir: Path) -> None:
    """Number figures, and the tables that carry a caption, in the chapter's count."""
    label = f"{page.chapter_number}." if page.chapter_number else ""
    counters = page.counters

    def figure(match: re.Match[str]) -> str:
        fig = counters["figure"] = counters.get("figure", 0) + 1
        img = match.group(1)
        alt = _IMG_ALT_PATTERN.search(img)
        caption = alt.group(1) if alt else ""
        body = inline_svg(page, img, caption, book_dir) or img
        return (
            f'<figure id="fig-{fig}">{body}<figcaption>'
            f'<span class="caplabel">Figure {label}{fig}</span> {caption}'
            f'{anchor_link(f"fig-{fig}")}</figcaption></figure>'
        )

    def table(match: re.Match[str]) -> str:
        body, caption = match.group(1), match.group(2)
        if not caption:
            # Only captioned tables are numbered, so the numbers run without gaps.
            return (
                f'<figure class="table"><div class="table-wrap">{body}</div></figure>'
            )
        tab = counters["table"] = counters.get("table", 0) + 1
        figcaption = (
            f'<figcaption><span class="caplabel">Table {label}{tab}</span> {caption}'
            f'{anchor_link(f"tab-{tab}")}</figcaption>'
        )
        return (
            f'<figure class="table" id="tab-{tab}">{figcaption}'
            f'<div class="table-wrap">{body}</div></figure>'
        )

    page.body_html = _FIGURE_PATTERN.sub(figure, page.body_html)
    page.body_html = _TABLE_CAPTION_PATTERN.sub(table, page.body_html)


def number_boxes(page: Page) -> None:
    """Label boxed environments and number those in :data:`NUMBERED_BOXES`."""
    counters = page.counters
    label = f"{page.chapter_number}." if page.chapter_number else ""

    def head_of(kind: str, title: str) -> tuple[str, str]:
        """Return a box's heading and its id, which only a numbered box has."""
        name = NUMBERED_BOXES.get(kind)
        if name is None:
            plain = LABELLED_BOXES.get(kind)
            if plain is None:
                return title, ""
            head = f'<span class="boxlabel">{plain}</span>'
            if title and title.lower() != plain.lower():
                head += f' <span class="boxtitle">{title}</span>'
            return head, ""
        counters[kind] = counters.get(kind, 0) + 1
        box_id = f"{kind}-{label}{counters[kind]}".replace(".", "-")
        head = f'<span class="boxlabel">{name} {label}{counters[kind]}</span>'
        if title and title != kind.capitalize():
            head += f' <span class="boxtitle">{title}</span>'
        return head + anchor_link(box_id), box_id

    def replace(match: re.Match[str]) -> str:
        kind, extra, is_open, title = match.groups(default="")
        head, box_id = head_of(kind, title)
        attributes = f'class="admonition {kind}{extra}"{is_open}'
        if box_id:
            attributes += f' id="{box_id}"'
        if match.group(0).startswith("<details"):
            return f"<details {attributes}>\n<summary>{head}</summary>"
        return f'<div {attributes}>\n<p class="admonition-title">{head}</p>'

    page.body_html = _BOX_PATTERN.sub(replace, page.body_html)


def resolve_citations(page: Page) -> list[str]:
    """Turn ``[@key]`` into numbered citations and append the reference list.

    Returns
    -------
    list of str
        A warning for each reference never cited.

    Raises
    ------
    BuildError
        If ``references`` is not a mapping or a citation has no entry in it.
    """
    references = page.meta.get("references") or {}
    if not isinstance(references, dict):
        raise BuildError(
            f"{page.source_path}: 'references' must be a mapping of key to text"
        )
    order: list[str] = []
    warnings: list[str] = []

    def number(key: str) -> int:
        if key not in references:
            raise BuildError(
                f"{page.source_path}: citation [@{key}] has no entry in 'references'"
            )
        if key not in order:
            order.append(key)
        return order.index(key) + 1

    def replace(match: re.Match[str]) -> str:
        keys = [k.strip().lstrip("@") for k in match.group(1).split(";") if k.strip()]
        links = [f'<a class="cite" href="#ref-{k}">{number(k)}</a>' for k in keys]
        return f'<span class="cites">[{", ".join(links)}]</span>'

    page.body_html = outside_code(
        page.body_html, lambda segment: _CITE_PATTERN.sub(replace, segment)
    )
    unused = [key for key in references if key not in order]
    if unused:
        warnings.append(
            f"{page.source_path}: references never cited: {', '.join(unused)}"
        )
    if order:
        items = []
        for key in order:
            items.append(f'<li id="ref-{key}">{inline_html(str(references[key]))}</li>')
        page.body_html += (
            '\n<section class="references"><h2 id="references" class="unnumbered">'
            "References</h2>"
            f'<ol class="references">{"".join(items)}</ol></section>'
        )
    return warnings


def rewrite_links(
    page: Page,
    pages_by_source: dict[Path, Page],
    assets: set[Path],
    book_dir: Path,
) -> list[tuple[Page, Page, str]]:
    """Rewrite ``.md`` links into site URLs and check that every target exists.

    Parameters
    ----------
    page : Page
        The page to rewrite.
    pages_by_source : dict
        Every page, by its source path.
    assets : set of Path
        Receives the local files the page links to, relative to `book_dir`.
    book_dir : Path
        The book's sources.

    Returns
    -------
    list of tuple
        The page, the page it links to and the anchor, for each link to an anchor of
        another page, which :func:`check_anchors` checks once every page is finished.

    Raises
    ------
    BuildError
        If a link starts at the site's root or leaves the book, or its target is not in
        ``book.yaml`` or on disk.
    """
    anchor_links: list[tuple[Page, Page, str]] = []

    def replace(match: re.Match[str]) -> str:
        attr, link = match.group(1), match.group(2)
        if not link or link.startswith(("#", "//")) or _LINK_SCHEME_PATTERN.match(link):
            return match.group(0)
        if link.startswith("/"):
            raise BuildError(
                f"{page.source_path}: absolute link, use a relative one: {link}"
            )
        target, _, anchor = link.partition("#")
        fragment = f"#{anchor}" if anchor else ""
        resolved = _resolved_link(page, target)
        if target.endswith(".md"):
            dest = pages_by_source.get(resolved)
            if dest is None:
                raise BuildError(
                    f"{page.source_path}: link to a page that is not in book.yaml: "
                    f"{target}"
                )
            if anchor:
                anchor_links.append((page, dest, anchor))
            return f'{attr}="{page.href(dest)}{fragment}"'
        if not (book_dir / resolved).is_file():
            raise BuildError(f"{page.source_path}: missing asset: {target}")
        assets.add(resolved)
        return f'{attr}="{page.root}{resolved.as_posix()}{fragment}"'

    page.body_html = _LINK_PATTERN.sub(replace, page.body_html)
    return anchor_links


def check_anchors(
    page_html: dict[Page, str], anchor_links: list[tuple[Page, Page, str]]
) -> None:
    """Check that the anchors links point at exist on the finished pages.

    Parameters
    ----------
    page_html : dict
        Each page's finished HTML. The templates add ids of their own.
    anchor_links : list of tuple
        What :func:`rewrite_links` returned, to which each page's links to itself are
        added here.

    Raises
    ------
    BuildError
        If a link names an anchor its page does not have.
    """
    anchors = {page: set(_ID_PATTERN.findall(text)) for page, text in page_html.items()}
    same_page_links = [
        (page, page, anchor)
        for page, text in page_html.items()
        for anchor in _SAME_PAGE_LINK_PATTERN.findall(text)
    ]
    for page, dest, anchor in anchor_links + same_page_links:
        if anchor.startswith(EQUATION_ANCHOR_PREFIX):
            continue
        if anchor not in anchors[dest]:
            raise BuildError(
                f"{page.source_path}: no anchor #{anchor} in {dest.source_path}"
            )


def _resolved_link(page: Page, target: str) -> Path:
    """Return `target` relative to ``book/``, collapsing its ``..`` components."""
    parts: list[str] = []
    for part in (PurePosixPath(page.source_path.parent.as_posix()) / target).parts:
        if part == "..":
            if not parts:
                raise BuildError(f"{page.source_path}: link escapes the book: {target}")
            parts.pop()
        elif part != ".":
            parts.append(part)
    return Path(*parts)


def mark_external_links(page: Page) -> None:
    """Add the class and ``rel`` of an external link to every absolute link."""
    page.body_html = re.sub(
        r'<a href="(https?://[^"]+)"',
        r'<a href="\1" class="external" rel="noopener"',
        page.body_html,
    )


def url_with_breaks(url_text: str) -> str:
    """Return the escaped `url_text` with a ``<wbr>`` wherever it may break."""
    parts = _URL_BREAK_PATTERN.split(html.unescape(url_text))
    return "<wbr>".join(html.escape(part, quote=False) for part in parts)


def break_bare_urls(page: Page) -> None:
    """Let the links that show their own address wrap between its elements.

    An address has few places to break by itself, so a long one would widen the page.
    A ``<wbr>`` adds none of its own text to a selection or to the link. The class
    keeps hyphenation out of the address, where an added hyphen would read as part of it.
    """

    def plain_address(url: str) -> str:
        return _URL_SCHEME_PATTERN.sub("", url, count=1).rstrip("/")

    def replace(match: re.Match[str]) -> str:
        address, text = match.group(1), match.group(2)
        if plain_address(address) != plain_address(text):
            return match.group(0)
        return (
            f'<a href="{address}" class="external bare-url" rel="noopener">'
            f"{url_with_breaks(text)}</a>"
        )

    page.body_html = _EXTERNAL_LINK_PATTERN.sub(replace, page.body_html)


def split_code_lines(page: Page) -> None:
    """Put each line of a code block in the ``.line`` span that wraps it.

    The span records the line's indentation, which a continuation goes past, so a
    wrapped line reads apart from the next one. Each newline stays in its span, which
    leaves the block's text and a selection of it as they were. A block with line
    numbers is left alone: a wrapped line would lose its place beside its number.
    """

    def line_span(line: str) -> str:
        text = _TAG_PATTERN.sub("", line)
        indent = len(text) - len(text.lstrip(" "))
        style = f' style="--indent:{indent}"' if indent else ""
        return f'<span class="line"{style}>{line}</span>'

    def replace(match: re.Match[str]) -> str:
        # Pygments closes the span of a marked line after its newline.
        code = match.group(2).replace("\n</span>", "</span>\n")
        lines = "".join(map(line_span, _CODE_LINE_PATTERN.findall(code)))
        return f"{match.group(1)}{lines}{match.group(3)}"

    page.body_html = _CODE_BLOCK_PATTERN.sub(replace, page.body_html)


def keep_code_tokens(text: str) -> str:
    """Let the inline code in `text` wrap only at its spaces.

    Each word goes in a ``.tok`` span, which ``book.css`` keeps on one line, so that a
    token like ``:<line>`` stays whole. Code with colours and code blocks are left alone.
    """

    def tokens(match: re.Match[str]) -> str:
        words = match.group(1).split(" ")
        spans = (f'<span class="tok">{word}</span>' if word else word for word in words)
        return f"<code>{' '.join(spans)}</code>"

    segments = _PRE_PATTERN.split(text)
    segments[::2] = [
        _PLAIN_CODE_PATTERN.sub(tokens, segment) for segment in segments[::2]
    ]
    return "".join(segments)


def prepare_reference_page(page: Page) -> None:
    """Give `page` what the reference layout shows beyond its body.

    The first paragraph moves from the body to ``lede_html``. This runs after the search
    index is made, which keeps that paragraph's text.
    """
    if page.kind in LEDE_KINDS and (lede := _LEDE_PATTERN.match(page.body_html)):
        page.lede_html = keep_code_tokens(lede.group(1))
        page.body_html = page.body_html[lede.end() :]
    page.body_html = keep_code_tokens(page.body_html)
    page.summary_html = keep_code_tokens(inline_html(page.summary))


def _search_crumb(page: Page) -> str:
    """Return what a search result calls `page`: by number, or else by its part."""
    if page.number:
        prefix = {"chapter": f"{page.number}. ", "section": f"{page.number} "}
        return prefix.get(page.kind, "") + page.title
    if page.part:
        return f"{page.part.title}{SEARCH_CRUMB_SEPARATOR}{page.title}"
    return page.title


def search_entries(page: Page) -> list[dict[str, str]]:
    """Return one entry per H2 section, with plain text for the client-side index."""
    # A tab's label names a view of the text and would match every search for it.
    chunks = re.split(r'(?=<h2 id=")', _TAB_LABEL_PATTERN.sub("", page.body_html))
    entries = []
    for chunk in chunks:
        heading = re.match(r'<h2 id="([^"]+)">(.*?)</h2>', chunk, re.S)
        text = html.unescape(_TAG_PATTERN.sub(" ", chunk)).replace("§", "")
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        if heading:
            plain_heading = _TAG_PATTERN.sub("", heading.group(2))
            section = html.unescape(plain_heading).replace("§", "").strip()
            anchor = "#" + heading.group(1)
            text = text[len(section) :].strip() if text.startswith(section) else text
        else:
            section, anchor = "", ""
        entries.append(
            {
                "url": page.url + anchor,
                "page": _search_crumb(page),
                "section": section,
                "text": text[:SEARCH_TEXT_LIMIT],
            }
        )
    return entries
