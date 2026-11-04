"""The passes over a page's HTML: numbers, citations, links and the search index."""

import html
import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

import markdown

from guidebook.config import (
    LABELLED_BOXES,
    NUMBERED_BOXES,
    SEARCH_TEXT_LIMIT,
    UNNUMBERED_HEADINGS,
)
from guidebook.errors import BuildError
from guidebook.pages import Page

_CODE_SEGMENT_PATTERN = re.compile(r"(<pre.*?</pre>|<code.*?</code>)", re.S)
_HEADING_PATTERN = re.compile(r'<h([23]) id="([^"]+)">(.*?)</h\1>', re.S)
_FIGURE_PATTERN = re.compile(r"<p>(<img [^>]*>)</p>")
_TABLE_CAPTION_PATTERN = re.compile(
    r"(<table>.*?</table>)\s*(?:<p>Table:\s*(.*?)</p>)?", re.S
)
_IMG_ALT_PATTERN = re.compile(r'alt="([^"]*)"')
_IMG_SRC_PATTERN = re.compile(r'src="([^"]+)"')
_XML_DECLARATION_PATTERN = re.compile(r"<\?xml[^>]*\?>\s*")
_BOX_PATTERN = re.compile(
    r'<div class="admonition ([\w-]+)( [\w -]+)?">\s*'
    r'<p class="admonition-title">(.*?)</p>',
    re.S,
)
_CITE_PATTERN = re.compile(r"\[@([^\]]+)\]")
_LINK_PATTERN = re.compile(
    r'(href|src)="([^"#]*?\.(?:md|svg|png|jpe?g|gif|pdf|webp))(#[^"]*)?"'
)
_TAG_PATTERN = re.compile(r"<[^>]+>")


def outside_code(text: str, transform: Callable[[str], str]) -> str:
    """Apply `transform` to the parts of `text` that are not code."""
    segments = _CODE_SEGMENT_PATTERN.split(text)
    return "".join(
        segment if index % 2 else transform(segment)
        for index, segment in enumerate(segments)
    )


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
        plain = re.sub(r"<[^>]+>", "", text).strip()
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

    def replace(match: re.Match[str]) -> str:
        kind, extra, title = match.group(1), match.group(2) or "", match.group(3)
        name = NUMBERED_BOXES.get(kind)
        if name is None:
            plain = LABELLED_BOXES.get(kind)
            if plain is None:
                return match.group(0)
            head = f'<span class="boxlabel">{plain}</span>'
            if title and title.lower() != plain.lower():
                head += f' <span class="boxtitle">{title}</span>'
            return (
                f'<div class="admonition {kind}{extra}">\n'
                f'<p class="admonition-title">{head}</p>'
            )
        counters[kind] = counters.get(kind, 0) + 1
        box_id = f"{kind}-{label}{counters[kind]}".replace(".", "-")
        head = f'<span class="boxlabel">{name} {label}{counters[kind]}</span>'
        if title and title != kind.capitalize():
            head += f' <span class="boxtitle">{title}</span>'
        head += anchor_link(box_id)
        return (
            f'<div class="admonition {kind}{extra}" id="{box_id}">\n'
            f'<p class="admonition-title">{head}</p>'
        )

    page.body_html = _BOX_PATTERN.sub(replace, page.body_html)


def resolve_citations(page: Page, md: markdown.Markdown) -> list[str]:
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
            text = md.convert(str(references[key]))
            md.reset()
            text = re.sub(r"^<p>|</p>$", "", text.strip())
            items.append(f'<li id="ref-{key}">{text}</li>')
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
) -> None:
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

    Raises
    ------
    BuildError
        If a link leaves the book, or its target is not in ``book.yaml`` or on disk.
    """

    def replace(match: re.Match[str]) -> str:
        attr, target, fragment = match.group(1), match.group(2), match.group(3) or ""
        if "://" in target or target.startswith("/"):
            return match.group(0)
        resolved = _resolved_link(page, target)
        if target.endswith(".md"):
            dest = pages_by_source.get(resolved)
            if dest is None:
                raise BuildError(
                    f"{page.source_path}: link to a page that is not in book.yaml: "
                    f"{target}"
                )
            return f'{attr}="{page.href(dest)}{fragment}"'
        if not (book_dir / resolved).is_file():
            raise BuildError(f"{page.source_path}: missing asset: {target}")
        assets.add(resolved)
        return f'{attr}="{page.root}{resolved.as_posix()}{fragment}"'

    page.body_html = _LINK_PATTERN.sub(replace, page.body_html)


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


def search_entries(page: Page) -> list[dict[str, str]]:
    """Return one entry per H2 section, with plain text for the client-side index."""
    chunks = re.split(r'(?=<h2 id=")', page.body_html)
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
        prefix = {"chapter": f"{page.number}. ", "section": f"{page.number} "}
        entries.append(
            {
                "url": page.url + anchor,
                "page": prefix.get(page.kind, "") + page.title,
                "section": section,
                "text": text[:SEARCH_TEXT_LIMIT],
            }
        )
    return entries
