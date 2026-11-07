"""Where a book's files are, and what its ``book.yaml`` says.

Every field of :class:`BookConfig` is a ``book.yaml`` key, so the defaults live here
and nowhere else.
"""

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from bookspine import _markdown
from bookspine.errors import BuildError
from bookspine.safe_paths import require_path_component

# Names inside a project directory.
CONFIG_NAME = "book.yaml"
BOOK_DIR_NAME = "book"
THEME_DIR_NAME = "theme"
SITE_DIR_NAME = "site"
TEMPLATES_DIR_NAME = "templates"
STATIC_DIR_NAME = "static"
ICONS_DIR_NAME = "icons"
OPENER_NAME = "index.md"

# The layouts. A book numbers its parts, chapters and sections. A reference site leaves
# them unnumbered, for readers who look a page up instead of reading in order.
BOOK_LAYOUT = "book"
REFERENCE_LAYOUT = "reference"
LAYOUTS = (BOOK_LAYOUT, REFERENCE_LAYOUT)

# The reference layout's own templates, where it has them, under this directory.
REFERENCE_TEMPLATES_DIR_NAME = "reference"

# What the search box says in each layout.
DEFAULT_SEARCH_SCOPE = "book"
DEFAULT_SEARCH_HINT = "Type to search chapter and section text."
REFERENCE_SEARCH_SCOPE = "site"
REFERENCE_SEARCH_HINT = "Type what you are looking for."

# Code colours, from the styles listed at https://pygments.org/styles/
DEFAULT_PYGMENTS_LIGHT = "friendly"
DEFAULT_PYGMENTS_DARK = "github-dark"

# What pulldown-cmark reads beyond CommonMark, each option documented at
# https://docs.rs/pulldown-cmark/0.13.6/pulldown_cmark/struct.Options.html
MARKDOWN_OPTIONS = (
    _markdown.ENABLE_DEFINITION_LIST
    | _markdown.ENABLE_HEADING_ATTRIBUTES
    | _markdown.ENABLE_MATH
    | _markdown.ENABLE_SMART_PUNCTUATION
    | _markdown.ENABLE_TABLES
)

# Boxed environments that receive a running number within the chapter. Their names
# are this theme's convention: book.css styles each one.
NUMBERED_BOXES = {
    "definition": "Definition",
    "example": "Example",
    "remark": "Remark",
    "recipe": "Recipe",
}

# Boxed environments that carry a kind label but no running number.
LABELLED_BOXES = {
    "warning": "Warning",
    "caution": "Caution",
    "note": "Note",
    "tip": "Tip",
}

# Headings left without a number, compared in lower case.
UNNUMBERED_HEADINGS = {"references", "further reading"}

# The characters of a section's text kept in the search index.
SEARCH_TEXT_LIMIT = 1200

# Between a topic and its page in a search result of the reference layout.
SEARCH_CRUMB_SEPARATOR = " › "

# The generated glossary: an opener, as a part has, and a page for each kind of entry.
GLOSSARY_TITLE = "Glossary"
GLOSSARY_SUMMARY = "Find where this book defines a term or states an equation."
GLOSSARY_URL = "glossary/"
GLOSSARY_TERMS_TITLE = "Terms"
GLOSSARY_TERMS_NOUN = "term"
GLOSSARY_TERMS_SUMMARY = "{count} defined in this book."
GLOSSARY_TERMS_URL = "glossary/terms/"
GLOSSARY_EQUATIONS_TITLE = "Equations"
GLOSSARY_EQUATIONS_NOUN = "equation"
GLOSSARY_EQUATIONS_SUMMARY = "{count} named in this book."
GLOSSARY_EQUATIONS_URL = "glossary/equations/"

# How the title page and footer print the date, in the notation of
# https://docs.python.org/3/library/datetime.html#format-codes
BUILD_DATE_FORMAT = "%B %Y"

# Keys holding text. The others are checked one by one in _config_from_record.
_TEXT_KEYS = (
    "title",
    "author",
    "subtitle",
    "kicker",
    "url",
    "repo",
    "repo_host",
    "edit_url",
    "help_page",
    "layout",
    "search_scope",
    "search_hint",
    "pygments_light",
    "pygments_dark",
)
# The C parser, which is much faster, where PyYAML was built with it.
_FAST_YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

_SWITCH_KEYS = ("enlarge_tables", "export_menus", "glossary", "wrap_code")
_REQUIRED_KEYS = ("title", "author")
_PART_KEYS = {"dir", "title", "chapters"}
_CHAPTER_KEYS = {"dir", "sections"}

# A TeX control word, written as an unquoted key of MathJax's macros object:
# https://github.com/mathjax/MathJax-src/blob/3.2.2/ts/input/tex/configmacros/ConfigMacrosConfiguration.ts
_MACRO_NAME_PATTERN = re.compile(r"[A-Za-z]+")


@dataclass(frozen=True)
class Project:
    """Where a book's files are.

    Parameters
    ----------
    project_dir : Path
        The directory holding ``book.yaml``, ``book/`` and an optional ``theme/``.
    site_dir : Path
        The directory the site is written to.
    """

    project_dir: Path
    site_dir: Path

    @classmethod
    def locate(
        cls,
        project_dir: str | os.PathLike[str],
        site_dir: str | os.PathLike[str] | None = None,
    ) -> "Project":
        """Return the project in `project_dir`, by default writing to its ``site/``."""
        resolved_dir = Path(project_dir).resolve()
        resolved_site_dir = (
            resolved_dir / SITE_DIR_NAME
            if site_dir is None
            else Path(site_dir).resolve()
        )
        return cls(resolved_dir, resolved_site_dir)

    @property
    def config_path(self) -> Path:
        return self.project_dir / CONFIG_NAME

    @property
    def book_dir(self) -> Path:
        return self.project_dir / BOOK_DIR_NAME

    @property
    def theme_dir(self) -> Path:
        return self.project_dir / THEME_DIR_NAME

    @property
    def templates_dir(self) -> Path:
        return self.theme_dir / TEMPLATES_DIR_NAME

    @property
    def static_dir(self) -> Path:
        return self.theme_dir / STATIC_DIR_NAME

    @property
    def icons_dir(self) -> Path:
        return self.theme_dir / ICONS_DIR_NAME


@dataclass(frozen=True)
class ChapterConfig:
    """One chapter of a part.

    Parameters
    ----------
    dir_name : str
        The chapter's directory in the site and, with section pages, in ``book/``.
    source_name : str
        The chapter's Markdown file, relative to its part.
    section_names : tuple of str
        The section pages' Markdown files, relative to `dir_name`.
    """

    dir_name: str
    source_name: str
    section_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class PartConfig:
    """One part of the book.

    Parameters
    ----------
    dir_name : str
        The part's directory, in ``book/`` and in the site.
    chapters : tuple of ChapterConfig
        The part's chapters, in reading order.
    """

    dir_name: str
    chapters: tuple[ChapterConfig, ...] = ()


@dataclass(frozen=True)
class BookConfig:
    """The contents of ``book.yaml``.

    Parameters
    ----------
    title, author : str
        The book's title and author.
    subtitle, kicker : str
        The lines around the title on the home page.
    url : str
        The published address.
    repo : str
        The source repository, linked from the sidebar. Needs `repo_host`.
    repo_host : str
        The name in the sidebar's link text, such as ``GitHub``.
    edit_url : str
        The prefix of a page's edit link, followed by its path under ``book/``.
    help_page : str
        The Markdown file in ``book/`` linked from the foot of the sidebar.
    parts : tuple of PartConfig
        The book's parts, in reading order.
    layout : str
        ``book`` for numbered pages, ``reference`` for unnumbered ones.
    search_scope : str
        What the search box offers to search, as in "Search the book".
    search_hint : str
        The line under the search box.
    enlarge_tables : bool
        Whether a table has a button that opens it enlarged, as a figure does.
    export_menus : bool
        Whether tables, figures, code blocks and equations offer an export menu.
    glossary : bool
        Whether ``\\glossary`` tags make glossary pages.
    wrap_code : bool
        Whether a long line of code wraps instead of scrolling.
    mathjax_macros : Mapping[str, Any]
        TeX macros by name, each a definition or ``[definition, argument count]``.
    pygments_light, pygments_dark : str
        The code colour styles of the two colour schemes.
    """

    title: str
    author: str
    subtitle: str = ""
    kicker: str = ""
    url: str = ""
    repo: str = ""
    repo_host: str = ""
    edit_url: str = ""
    help_page: str = ""
    parts: tuple[PartConfig, ...] = ()
    layout: str = BOOK_LAYOUT
    search_scope: str = DEFAULT_SEARCH_SCOPE
    search_hint: str = DEFAULT_SEARCH_HINT
    enlarge_tables: bool = True
    export_menus: bool = True
    glossary: bool = True
    wrap_code: bool = True
    mathjax_macros: Mapping[str, Any] = field(default_factory=dict)
    pygments_light: str = DEFAULT_PYGMENTS_LIGHT
    pygments_dark: str = DEFAULT_PYGMENTS_DARK

    @property
    def is_reference(self) -> bool:
        return self.layout == REFERENCE_LAYOUT


def parse_yaml(text: str) -> Any:
    """Return the data in the YAML `text`, as :func:`yaml.safe_load` does.

    The C parser accepts some tabs that the Python parser refuses, so it does not see
    text with a tab.

    Raises
    ------
    yaml.YAMLError
        If `text` is invalid, with the Python parser's fuller message.
    """
    if "\t" in text:
        return yaml.safe_load(text)
    try:
        return yaml.load(text, Loader=_FAST_YAML_LOADER)
    except yaml.YAMLError:
        return yaml.safe_load(text)


def load_config(config_path: Path) -> BookConfig:
    """Read and check the ``book.yaml`` at `config_path`.

    Raises
    ------
    BuildError
        If the file is missing, is not valid YAML, or has an unknown or invalid key.
    """
    try:
        config_text = config_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise BuildError(f"no {config_path.name} in {config_path.parent}") from None
    try:
        record = parse_yaml(config_text)
    except yaml.YAMLError as error:
        raise BuildError(f"{CONFIG_NAME}: invalid YAML: {error}") from None
    return _config_from_record(record)


def _config_from_record(record: Any) -> BookConfig:
    if not isinstance(record, Mapping):
        raise BuildError(f"{CONFIG_NAME} must be a mapping of keys to values")
    known_keys = {book_field.name for book_field in fields(BookConfig)}
    _require_known_keys(record, known_keys, CONFIG_NAME)
    for key in _REQUIRED_KEYS:
        if not record.get(key):
            raise BuildError(f"{CONFIG_NAME} needs a {key}")
    for key in _TEXT_KEYS:
        if key in record and not isinstance(record[key], str):
            raise BuildError(f"{CONFIG_NAME}: {key} must be text")
    if record.get("repo") and not record.get("repo_host"):
        raise BuildError(f"{CONFIG_NAME}: repo needs a repo_host, such as GitHub")

    values = {key: record[key] for key in _TEXT_KEYS if key in record}
    if "help_page" in values:
        require_path_component(values["help_page"], what="The help_page")
    layout = values.get("layout", BOOK_LAYOUT)
    if layout not in LAYOUTS:
        raise BuildError(f"{CONFIG_NAME}: layout must be one of {', '.join(LAYOUTS)}")
    if layout == REFERENCE_LAYOUT:
        values.setdefault("search_scope", REFERENCE_SEARCH_SCOPE)
        values.setdefault("search_hint", REFERENCE_SEARCH_HINT)
    values["parts"] = _parts_from_record(record.get("parts"))
    for key in _SWITCH_KEYS:
        if key in record:
            if not isinstance(record[key], bool):
                raise BuildError(f"{CONFIG_NAME}: {key} must be true or false")
            values[key] = record[key]
    if "mathjax_macros" in record:
        values["mathjax_macros"] = _checked_macros(record["mathjax_macros"])
    return BookConfig(**values)


def _require_known_keys(record: Mapping[Any, Any], known: set[str], what: str) -> None:
    unknown = sorted(str(key) for key in record if key not in known)
    if unknown:
        raise BuildError(f"{what}: unknown key: {', '.join(unknown)}")


def _parts_from_record(record: Any) -> tuple[PartConfig, ...]:
    if record is None:
        return ()
    if not isinstance(record, list):
        raise BuildError(f"{CONFIG_NAME}: parts must be a list")
    return tuple(_part_from_record(entry) for entry in record)


def _part_from_record(record: Any) -> PartConfig:
    if not isinstance(record, Mapping) or "dir" not in record:
        raise BuildError(f"{CONFIG_NAME}: every part needs a dir")
    _require_known_keys(record, _PART_KEYS, f"{CONFIG_NAME}: part {record['dir']}")
    chapters = record.get("chapters") or []
    if not isinstance(chapters, list):
        raise BuildError(f"{CONFIG_NAME}: chapters of {record['dir']} must be a list")
    return PartConfig(
        dir_name=_checked_dir_name(record["dir"]),
        chapters=tuple(_chapter_from_entry(entry) for entry in chapters),
    )


def _chapter_from_entry(entry: Any) -> ChapterConfig:
    """Read a chapter: a Markdown file name, or a directory with its section pages."""
    if isinstance(entry, str):
        require_path_component(entry, what="A chapter file name")
        return ChapterConfig(dir_name=PurePosixPath(entry).stem, source_name=entry)
    if not isinstance(entry, Mapping) or "dir" not in entry:
        raise BuildError(f"{CONFIG_NAME}: a chapter is a file name or has a dir")
    _require_known_keys(entry, _CHAPTER_KEYS, f"{CONFIG_NAME}: chapter {entry['dir']}")
    dir_name = _checked_dir_name(entry["dir"])
    section_names = entry.get("sections") or []
    if not isinstance(section_names, list):
        raise BuildError(f"{CONFIG_NAME}: sections of {dir_name} must be a list")
    return ChapterConfig(
        dir_name=dir_name,
        source_name=f"{dir_name}/{OPENER_NAME}",
        section_names=tuple(
            require_path_component(name, what="A section file name")
            for name in section_names
        ),
    )


def _checked_dir_name(name: Any) -> str:
    stripped = name.strip("/") if isinstance(name, str) else name
    return require_path_component(stripped, what="A dir in book.yaml")


def _checked_macros(record: Any) -> Mapping[str, Any]:
    if not isinstance(record, Mapping):
        raise BuildError(f"{CONFIG_NAME}: mathjax_macros must be a mapping")
    for name, definition in record.items():
        if not isinstance(name, str) or not _MACRO_NAME_PATTERN.fullmatch(name):
            raise BuildError(f"{CONFIG_NAME}: {name} is not a TeX macro name")
        if not _is_macro_definition(definition):
            raise BuildError(
                f"{CONFIG_NAME}: macro {name} must be a definition or "
                "[definition, argument count]"
            )
    return record


def _is_macro_definition(definition: Any) -> bool:
    if isinstance(definition, str):
        return True
    if not isinstance(definition, list) or len(definition) != 2:
        return False
    text, argument_count = definition
    return (
        isinstance(text, str)
        and isinstance(argument_count, int)
        and not isinstance(argument_count, bool)
    )
