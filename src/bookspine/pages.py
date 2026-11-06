"""The book's pages: reading the Markdown files ``book.yaml`` lists, in reading order."""

import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from bookspine.config import CONFIG_NAME, OPENER_NAME, BookConfig, parse_yaml
from bookspine.errors import BuildError

_FRONT_MATTER_PATTERN = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)

_ROMAN_NUMERALS = (
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
)


@dataclass
class GlossaryEntry:
    """One reference in the glossary.

    Parameters
    ----------
    name : str
        The name of the term or equation, as plain text.
    anchor : str
        The id the reference links to, on the page it comes from.
    locator : str
        Where it stands there, such as ``Definition 1.2``.
    """

    name: str
    anchor: str
    locator: str


# Pages are compared by identity: the templates ask whether a page is the current one,
# and the fields link pages to one another.
@dataclass(eq=False)
class Page:
    """One output page: home, a part opener, a chapter, a section or a generated page.

    Parameters
    ----------
    kind : str
        ``"home"``, ``"part"``, ``"chapter"``, ``"section"``, ``"glossary"`` or
        ``"help"``.
    source_path : Path
        The Markdown source, relative to ``book/``.
    url : str
        The site-relative URL, ending in ``/``; empty for the home page.
    meta : dict
        The front matter.
    body_md : str
        The Markdown after the front matter.
    title : str
        The title from the front matter.
    number : str
        ``"1"`` for a chapter, ``"I"`` for a part, ``"1.3"`` for a section page.
    part, chapter : Page or None
        The part and chapter the page belongs to.
    chapters, section_pages : list of Page
        A part's chapters and a chapter's section pages.
    sections : list of dict
        The headings within this page.
    counters : dict
        Running counts of figures, tables, boxes and equations, shared across a
        chapter's pages.
    equation_offset : int
        Equations numbered on the chapter's earlier pages.
    terms, named_equations : list of GlossaryEntry
        The glossary entries the page defines.
    body_html : str
        The page's HTML, built up by the passes.
    prev, next : Page or None
        The neighbouring pages in reading order.
    """

    kind: str
    source_path: Path
    url: str
    meta: dict[str, Any]
    body_md: str
    title: str = ""
    number: str = ""
    part: "Page | None" = None
    chapter: "Page | None" = None
    chapters: "list[Page]" = field(default_factory=list)
    section_pages: "list[Page]" = field(default_factory=list)
    sections: list[dict[str, Any]] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)
    equation_offset: int = 0
    terms: list[GlossaryEntry] = field(default_factory=list)
    named_equations: list[GlossaryEntry] = field(default_factory=list)
    body_html: str = ""
    prev: "Page | None" = None
    next: "Page | None" = None

    @property
    def status(self) -> str:
        return str(self.meta.get("status", "")).strip()

    @property
    def summary(self) -> str:
        return str(self.meta.get("summary", "")).strip()

    @property
    def chapter_number(self) -> str:
        """The number of the chapter this page is in, empty outside chapters."""
        if self.kind == "section":
            assert self.chapter is not None
            return self.chapter.number
        return self.number if self.kind == "chapter" else ""

    @property
    def has_numbered_headings(self) -> bool:
        """Whether H2/H3 are numbered; an opener with section pages leaves them plain."""
        return self.kind == "section" or (
            self.kind == "chapter" and not self.section_pages
        )

    @property
    def output_name(self) -> str:
        """The page's file, as a POSIX path relative to the site directory."""
        return f"{self.url}index.html"

    @property
    def depth(self) -> int:
        return self.url.count("/")

    @property
    def root(self) -> str:
        return "../" * self.depth if self.depth else "./"

    def href(self, target: "Page") -> str:
        return self.root + target.url


def roman_numeral(number: int) -> str:
    """Return the Roman numeral for a positive `number`."""
    numeral = ""
    for value, symbol in _ROMAN_NUMERALS:
        count, number = divmod(number, value)
        numeral += symbol * count
    return numeral


def split_front_matter(text: str, source_path: Path) -> tuple[dict[str, Any], str]:
    """Return the front matter of `text` and the Markdown after it.

    Raises
    ------
    BuildError
        If the front matter is missing, is not valid YAML or is not a mapping.
    """
    match = _FRONT_MATTER_PATTERN.match(text)
    if not match:
        raise BuildError(f"{source_path}: missing YAML front matter")
    try:
        meta = parse_yaml(match.group(1)) or {}
    except yaml.YAMLError as error:
        raise BuildError(f"{source_path}: invalid front matter: {error}") from None
    if not isinstance(meta, dict):
        raise BuildError(f"{source_path}: front matter must be a mapping")
    return meta, text[match.end() :]


def read_page(book_dir: Path, kind: str, source_path: Path, url: str) -> Page:
    """Read the page at `source_path`, relative to `book_dir`.

    Raises
    ------
    BuildError
        If the file is missing or its front matter is invalid or has no title.
    """
    path = book_dir / source_path
    if not path.is_file():
        raise BuildError(f"book.yaml refers to a missing file: {source_path}")
    meta, body_md = split_front_matter(path.read_text(encoding="utf-8"), source_path)
    title = str(meta.get("title", "")).strip()
    if not title:
        raise BuildError(f"{source_path}: front matter needs a title")
    return Page(
        kind=kind,
        source_path=source_path,
        url=url,
        meta=meta,
        body_md=body_md,
        title=title,
    )


def read_help_page(name: str, book_dir: Path, pages: list[Page]) -> Page:
    """Read the help page `name`, which takes its address from the file's name.

    Raises
    ------
    BuildError
        If the file is one of `pages` or its address is taken by one of them.
    """
    help_page = read_page(book_dir, "help", Path(name), f"{PurePosixPath(name).stem}/")
    for page in pages:
        if help_page.source_path == page.source_path or help_page.url == page.url:
            raise BuildError(
                f"{CONFIG_NAME}: help_page {name} clashes with {page.source_path}"
            )
    return help_page


def load_pages(config: BookConfig, book_dir: Path) -> list[Page]:
    """Read every page `config` lists and return them in reading order.

    A help page stands outside that order: it comes last, with no neighbours.

    Raises
    ------
    BuildError
        If a listed file is missing or a page is invalid.
    """
    pages = [read_page(book_dir, "home", Path(OPENER_NAME), "")]
    chapter_number = 0
    for part_number, part_config in enumerate(config.parts, start=1):
        part_dir = Path(part_config.dir_name)
        part = read_page(
            book_dir, "part", part_dir / OPENER_NAME, f"{part_config.dir_name}/"
        )
        part.number = roman_numeral(part_number)
        pages.append(part)
        for chapter_config in part_config.chapters:
            chapter_number += 1
            chapter_url = f"{part.url}{chapter_config.dir_name}/"
            chapter = read_page(
                book_dir, "chapter", part_dir / chapter_config.source_name, chapter_url
            )
            chapter.number = str(chapter_number)
            chapter.part = part
            part.chapters.append(chapter)
            pages.append(chapter)
            for section_number, name in enumerate(
                chapter_config.section_names, start=1
            ):
                section = read_page(
                    book_dir,
                    "section",
                    part_dir / chapter_config.dir_name / name,
                    f"{chapter_url}{PurePosixPath(name).stem}/",
                )
                section.number = f"{chapter.number}.{section_number}"
                section.part = part
                section.chapter = chapter
                section.counters = chapter.counters
                chapter.section_pages.append(section)
                pages.append(section)
    for before, after in zip(pages, pages[1:], strict=False):
        before.next = after
        after.prev = before
    if config.help_page:
        pages.append(read_help_page(config.help_page, book_dir, pages))
    return pages
