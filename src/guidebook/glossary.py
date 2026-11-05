"""The glossary: indexes of the book's terms and equations, built from ``\\glossary`` tags.

The tag marks a place and prints nothing, as LaTeX's ``\\index`` does. In a paragraph
``\\glossary{Name}`` makes a term of that place. At the start of a box a bare
``\\glossary`` takes the box's title as the name. Named equations are read in
:mod:`guidebook.equations`, where the same tag names a display equation.
"""

import html
import re
from collections.abc import Callable
from pathlib import Path

from guidebook.config import (
    GLOSSARY_EQUATIONS_NOUN,
    GLOSSARY_EQUATIONS_SUMMARY,
    GLOSSARY_EQUATIONS_TITLE,
    GLOSSARY_EQUATIONS_URL,
    GLOSSARY_SUMMARY,
    GLOSSARY_TERMS_NOUN,
    GLOSSARY_TERMS_SUMMARY,
    GLOSSARY_TERMS_TITLE,
    GLOSSARY_TERMS_URL,
    GLOSSARY_TITLE,
    GLOSSARY_URL,
)
from guidebook.errors import BuildError
from guidebook.pages import GlossaryEntry, Page
from guidebook.passes import CODE_SEGMENT_PATTERN

_TAG_PATTERN = re.compile(r"\\glossary(?![A-Za-z])(?:\{([^{}]*)\})?[ \t]*\n?")
_BOX_TAG_PATTERN = re.compile(
    r'<div class="admonition [^"]*"(?: id="(?P<id>[^"]+)")?>\s*'
    r'<p class="admonition-title">(?P<title>(?:(?!</p>).)*)</p>\s*'
    r"<p>\\glossary(?![A-Za-z])(?:\{(?P<name>[^{}]*)\})?\s*",
    re.S,
)
_BOX_LABEL_PATTERN = re.compile(r'<span class="boxlabel">(.*?)</span>', re.S)
_BOX_TITLE_PATTERN = re.compile(r'<span class="boxtitle">(.*?)</span>', re.S)
_HEADING_OPEN_PATTERN = re.compile(r'<h[23] id="([^"]+)">')
_TAG_HTML_PATTERN = re.compile(r"<[^>]+>")


def _plain(text_html: str) -> str:
    return html.unescape(_TAG_HTML_PATTERN.sub("", text_html)).strip()


def _term_id(name: str) -> str:
    return "term-" + "-".join(re.findall(r"\w+", name.casefold()))


def _collect_box_terms(page: Page) -> None:
    def replace(match: re.Match[str]) -> str:
        title = _BOX_TITLE_PATTERN.search(match["title"])
        label = _BOX_LABEL_PATTERN.search(match["title"])
        name = _plain(match["name"] or (title.group(1) if title else ""))
        if not name:
            raise BuildError(
                f"{page.source_path}: \\glossary needs a name in a box with no title"
            )
        anchor = match["id"] or _term_id(name)
        locator = _plain(label.group(1)) if label else page.title
        page.terms.append(GlossaryEntry(name=name, anchor=anchor, locator=locator))
        opening = match.string[match.start() : match.end("title")]
        if not match["id"]:
            opening = opening.replace(">", f' id="{anchor}">', 1)
        return f"{opening}</p>\n<p>"

    page.body_html = _BOX_TAG_PATTERN.sub(replace, page.body_html)
    page.body_html = page.body_html.replace("<p></p>", "")


def _section_locator(page: Page, source: str, position: int) -> str:
    """Return the number of the section holding `position`, else the page's title."""
    headings = list(_HEADING_OPEN_PATTERN.finditer(source, 0, position))
    numbers = {section["id"]: section["number"] for section in page.sections}
    number = numbers.get(headings[-1].group(1)) if headings else ""
    return f"Section {number}" if number else page.title


def _collect_paragraph_terms(page: Page) -> None:
    source = page.body_html
    code_spans = [match.span() for match in CODE_SEGMENT_PATTERN.finditer(source)]
    pieces = []
    last = 0
    for match in _TAG_PATTERN.finditer(source):
        if any(start <= match.start() < end for start, end in code_spans):
            continue
        name = _plain(match.group(1) or "")
        if not name:
            raise BuildError(
                f"{page.source_path}: \\glossary needs a name outside the start of a box"
            )
        anchor = _term_id(name)
        locator = _section_locator(page, source, match.start())
        page.terms.append(GlossaryEntry(name=name, anchor=anchor, locator=locator))
        pieces += [source[last : match.start()], f'<span id="{anchor}"></span>']
        last = match.end()
    page.body_html = "".join(pieces) + source[last:]


def collect_terms(page: Page) -> None:
    """Move the ``\\glossary`` tags of `page` into its list of terms.

    Runs after the headings and boxes are numbered, for the labels it records.

    Raises
    ------
    BuildError
        If a tag has no name and no box title to take one from.
    """
    _collect_box_terms(page)
    _collect_paragraph_terms(page)


def _gathered(
    pages: list[Page], entries_of: Callable[[Page], list[GlossaryEntry]]
) -> list[tuple[Page, GlossaryEntry]]:
    """Return every page's entries by name, refusing a name used twice."""
    pairs = [(page, entry) for page in pages for entry in entries_of(page)]
    pairs.sort(key=lambda pair: pair[1].name.casefold())
    for (first, entry), (second, other) in zip(pairs, pairs[1:], strict=False):
        if entry.name.casefold() == other.name.casefold():
            raise BuildError(
                f"{second.source_path}: glossary entry {other.name} "
                f"is also defined in {first.source_path}"
            )
    return pairs


def _entry_html(glossary: Page, target: Page, entry: GlossaryEntry) -> str:
    href = html.escape(f"{glossary.href(target)}#{entry.anchor}", quote=True)
    source = entry.locator
    if entry.locator != target.title:
        source = f"{entry.locator}, {target.title}"
    return (
        f'<li><a href="{href}">{html.escape(entry.name)}</a> '
        f'<span class="glossary-source">{html.escape(source)}</span></li>'
    )


def _make_page(title: str, summary: str, url: str) -> Page:
    return Page(
        kind="glossary",
        source_path=Path(f"{url.rstrip('/')}.md"),
        url=url,
        meta={"summary": summary},
        body_md="",
        title=title,
    )


def _make_list_page(
    title: str,
    summary: str,
    noun: str,
    url: str,
    pairs: list[tuple[Page, GlossaryEntry]],
) -> Page:
    count = f"{len(pairs)} {noun}{'' if len(pairs) == 1 else 's'}"
    page = _make_page(title, summary.format(count=count), url)
    entries = "\n".join(_entry_html(page, *pair) for pair in pairs)
    page.body_html = f'<ul class="glossary">\n{entries}\n</ul>'
    return page


def make_glossary_pages(pages: list[Page]) -> list[Page]:
    """Return the glossary's opener and a page for each kind of entry `pages` hold.

    The opener lists the other pages in its ``chapters``, as a part lists its own.

    Returns
    -------
    list of Page
        The pages in reading order, none when nothing is tagged.

    Raises
    ------
    BuildError
        If a name is defined twice, or a page already has a glossary page's address.
    """
    terms = _gathered(pages, lambda page: page.terms)
    equations = _gathered(pages, lambda page: page.named_equations)
    lists = []
    if terms:
        lists.append(
            _make_list_page(
                GLOSSARY_TERMS_TITLE,
                GLOSSARY_TERMS_SUMMARY,
                GLOSSARY_TERMS_NOUN,
                GLOSSARY_TERMS_URL,
                terms,
            )
        )
    if equations:
        lists.append(
            _make_list_page(
                GLOSSARY_EQUATIONS_TITLE,
                GLOSSARY_EQUATIONS_SUMMARY,
                GLOSSARY_EQUATIONS_NOUN,
                GLOSSARY_EQUATIONS_URL,
                equations,
            )
        )
    if not lists:
        return []
    opener = _make_page(GLOSSARY_TITLE, GLOSSARY_SUMMARY, GLOSSARY_URL)
    opener.chapters = lists
    taken = {page.url for page in pages}
    for page in (opener, *lists):
        if page.url in taken:
            raise BuildError(
                f"the glossary needs the address {page.url}, which is taken"
            )
    return [opener, *lists]
