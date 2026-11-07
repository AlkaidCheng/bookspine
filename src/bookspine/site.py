"""From a project directory to a site: converting pages, theming them, writing them."""

import datetime as dt
import json
import os
import re
from dataclasses import dataclass, field
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path

import jinja2
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound

from bookspine.config import (
    BUILD_DATE_FORMAT,
    REFERENCE_TEMPLATES_DIR_NAME,
    STATIC_DIR_NAME,
    TEMPLATES_DIR_NAME,
    BookConfig,
    Project,
    load_config,
)
from bookspine.converter import convert_markdown
from bookspine.equations import (
    MATHJAX_URL,
    needs_mathjax,
    number_equations,
    resolve_equation_refs,
)
from bookspine.errors import BuildError
from bookspine.glossary import collect_terms, make_glossary_pages
from bookspine.pages import Page, load_pages
from bookspine.passes import (
    break_bare_urls,
    mark_external_links,
    number_boxes,
    number_figures_and_tables,
    number_headings,
    prepare_reference_page,
    resolve_citations,
    rewrite_links,
    search_entries,
    split_code_lines,
)
from bookspine.safe_paths import (
    replace_site,
    require_path_component,
    require_site_dir,
)

# Names in the package and in the site.
PACKAGE_NAME = "bookspine"
PYGMENTS_CSS_NAME = f"{STATIC_DIR_NAME}/pygments.css"
SEARCH_INDEX_NAME = "search.json"
NOJEKYLL_NAME = ".nojekyll"

# An override reaches the package's own copy of a template under this prefix.
PACKAGE_TEMPLATE_PREFIX = "bookspine"

# What an icon's <svg> tag gains, so that it takes the size and colour book.css gives it.
ICON_ATTRIBUTES = 'class="icon" aria-hidden="true" fill="currentColor"'

# Replaces the build date when set: https://reproducible-builds.org/specs/source-date-epoch/
SOURCE_DATE_EPOCH_VARIABLE = "SOURCE_DATE_EPOCH"

_EPOCH_PATTERN = re.compile(r"[0-9]+")


@dataclass(frozen=True)
class BuildResult:
    """What a build did.

    Parameters
    ----------
    site_dir : Path
        The directory the site was written to.
    page_count, chapter_count : int
        The pages and chapters written.
    warnings : list of str
        Problems that do not stop the build by themselves.
    overrides : list of str
        The files under ``theme/`` in force, as POSIX paths.
    """

    site_dir: Path
    page_count: int
    chapter_count: int
    warnings: list[str] = field(default_factory=list)
    overrides: list[str] = field(default_factory=list)


@dataclass
class ConvertedPages:
    """What converting the pages collected besides their HTML.

    Parameters
    ----------
    assets : set of Path
        The local files the pages link to, relative to ``book/``.
    search_index : list of dict
        The entries of the client-side search index.
    warnings : list of str
        Problems that do not stop the build by themselves.
    """

    assets: set[Path] = field(default_factory=set)
    search_index: list[dict[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def build_book(
    project_dir: str | os.PathLike[str] = ".",
    site_dir: str | os.PathLike[str] | None = None,
) -> BuildResult:
    """Build the book in `project_dir`.

    Parameters
    ----------
    project_dir : str or PathLike, optional
        The directory holding ``book.yaml``, ``book/`` and an optional ``theme/``.
    site_dir : str or PathLike or None, optional
        Where to write the site, by default ``site/`` in `project_dir`.

    Returns
    -------
    BuildResult
        What was written, and the warnings. A warning does not stop the build here;
        the command line treats it as fatal unless told otherwise.

    Raises
    ------
    BuildError
        If the book has a problem, such as a broken link, or `site_dir` cannot be
        used. A failed build leaves the site directory as it was.
    """
    project = Project.locate(project_dir, site_dir)
    require_site_dir(
        project.site_dir, project.project_dir, [project.book_dir, project.theme_dir]
    )
    config = load_config(project.config_path)
    pages = load_pages(config, project.book_dir)
    converted = convert_pages(pages, project.book_dir, config)
    replace_site(project.site_dir, site_files(project, config, pages, converted))
    return BuildResult(
        site_dir=project.site_dir,
        page_count=len(pages),
        chapter_count=sum(1 for page in pages if page.kind == "chapter"),
        warnings=converted.warnings,
        overrides=find_overrides(project),
    )


def convert_pages(
    pages: list[Page], book_dir: Path, config: BookConfig
) -> ConvertedPages:
    """Turn every page's Markdown into numbered, linked HTML.

    Parameters
    ----------
    pages : list of Page
        The pages :func:`~bookspine.pages.load_pages` returned, to which the
        glossary's are appended.
    book_dir : Path
        The book's sources.
    config : BookConfig
        The book's settings.

    Raises
    ------
    BuildError
        If a link, figure, citation or equation reference does not resolve, or a
        glossary tag cannot be read.
    """
    pages_by_source = {page.source_path: page for page in pages}
    equation_labels: dict[str, tuple[Page, str]] = {}
    converted = ConvertedPages()
    for page in pages:
        page.body_html = convert_markdown(page.body_md)
        number_headings(page)
        number_figures_and_tables(page, book_dir)
        number_boxes(page)
        number_equations(page, equation_labels)
        collect_terms(page)
        converted.warnings += resolve_citations(page)
        rewrite_links(page, pages_by_source, converted.assets, book_dir)
        mark_external_links(page)
        converted.search_index += search_entries(page)
        # After the search text, which would otherwise split at every <wbr>.
        break_bare_urls(page)
        if config.wrap_code:
            split_code_lines(page)
        if config.is_reference:
            prepare_reference_page(page)

    last_page = next(page for page in reversed(pages) if page.kind != "help")
    for glossary_page in make_glossary_pages(pages) if config.glossary else []:
        last_page.next = glossary_page
        glossary_page.prev = last_page
        last_page = glossary_page
        pages.append(glossary_page)
        converted.search_index += search_entries(glossary_page)

    # A reference can point forward, so this waits until every page is numbered.
    for page in pages:
        resolve_equation_refs(page, equation_labels)
    return converted


def build_date() -> dt.date:
    """Return the date the book is revised at, from ``SOURCE_DATE_EPOCH`` if set.

    Raises
    ------
    BuildError
        If the variable is set and is not a Unix time.
    """
    epoch_text = os.environ.get(SOURCE_DATE_EPOCH_VARIABLE)
    if epoch_text is None:
        return dt.date.today()
    if not _EPOCH_PATTERN.fullmatch(epoch_text):
        raise BuildError(
            f"{SOURCE_DATE_EPOCH_VARIABLE} is not a Unix time: {epoch_text}"
        )
    try:
        return dt.datetime.fromtimestamp(int(epoch_text), dt.UTC).date()
    except (OverflowError, OSError, ValueError):
        raise BuildError(
            f"{SOURCE_DATE_EPOCH_VARIABLE} is out of range: {epoch_text}"
        ) from None


def make_environment(project: Project) -> jinja2.Environment:
    """Return the template environment, a book's own templates taking precedence."""
    package_loader = jinja2.PackageLoader(PACKAGE_NAME, TEMPLATES_DIR_NAME)
    return jinja2.Environment(
        loader=jinja2.ChoiceLoader(
            [
                jinja2.FileSystemLoader(project.templates_dir),
                package_loader,
                jinja2.PrefixLoader({PACKAGE_TEMPLATE_PREFIX: package_loader}),
            ]
        ),
        autoescape=jinja2.select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=jinja2.StrictUndefined,
    )


def read_icons(project: Project, pages: list[Page]) -> dict[str, str]:
    """Return the SVG of each part's icon, by its name, ready to place in a page.

    Raises
    ------
    BuildError
        If an icon's name is not a plain file name, or ``theme/icons/`` lacks the file.
    """
    icons = {}
    for page in pages:
        if page.kind != "part" or not page.icon:
            continue
        name = require_path_component(page.icon, what=f"{page.source_path}: icon")
        icon_path = project.icons_dir / f"{name}.svg"
        if not icon_path.is_file():
            raise BuildError(f"{page.source_path}: no such icon: {name}")
        svg = icon_path.read_text(encoding="utf-8").strip()
        icons[name] = svg.replace("<svg", f"<svg {ICON_ATTRIBUTES}", 1)
    return icons


def template_names(config: BookConfig, name: str) -> list[str]:
    """Return where to look for the template `name`, in order."""
    if config.is_reference:
        return [f"{REFERENCE_TEMPLATES_DIR_NAME}/{name}", name]
    return [name]


def page_files(
    project: Project, config: BookConfig, pages: list[Page]
) -> dict[str, bytes]:
    """Return the HTML file of every page, by its name in the site.

    Raises
    ------
    BuildError
        If a template fails, which for the package's own means an override's mistake.
    """
    environment = make_environment(project)
    environment.globals.update(
        base_template=template_names(config, "base.html")[0],
        book=config,
        build_date=build_date().strftime(BUILD_DATE_FORMAT),
        glossary_page=next((page for page in pages if page.kind == "glossary"), None),
        help_page=next((page for page in pages if page.kind == "help"), None),
        icons=read_icons(project, pages),
        mathjax_url=MATHJAX_URL,
    )
    parts = [page for page in pages if page.kind == "part"]
    files = {}
    for page in pages:
        try:
            names = template_names(config, f"{page.kind}.html")
            template = environment.select_template(names)
            page_html = template.render(page=page, parts=parts, load_mathjax=False)
            # Only the finished page shows all of its text: the sidebar prints headings
            # from other pages, and an override can print anything.
            if needs_mathjax(page_html.partition("</head>")[2]):
                page_html = template.render(page=page, parts=parts, load_mathjax=True)
        except jinja2.TemplateError as error:
            raise BuildError(f"{page.source_path}: template error: {error}") from None
        files[page.output_name] = page_html.encode("utf-8")
    return files


def pygments_css(config: BookConfig) -> str:
    """Return the code colours of both colour schemes.

    Raises
    ------
    BuildError
        If a style in `config` does not exist.
    """
    try:
        light = HtmlFormatter(style=config.pygments_light)
        dark = HtmlFormatter(style=config.pygments_dark)
    except ClassNotFound as error:
        raise BuildError(f"book.yaml: {error}") from None
    light_css = light.get_style_defs(".highlight")
    # Pygments writes its line number rules without the selector, so the dark scheme's
    # would reach the light scheme too. book.css colours the numbers in both.
    dark_selector = '[data-theme="dark"] .highlight'
    dark_css = "\n".join(
        dark.get_background_style_defs(dark_selector)
        + dark.get_token_style_defs(dark_selector)
    )
    return f"{light_css}\n{dark_css}\n"


def read_traversable(root: Traversable, prefix: str) -> dict[str, bytes]:
    """Return the files under `root`, by POSIX path starting with `prefix`.

    The walk uses ``Traversable`` because ``importlib.resources.as_file`` accepts a
    directory only from Python 3.12.
    """
    files = {}
    for entry in root.iterdir():
        name = f"{prefix}/{entry.name}"
        if entry.is_dir():
            files.update(read_traversable(entry, name))
        else:
            files[name] = entry.read_bytes()
    return files


def static_files(project: Project, config: BookConfig) -> dict[str, bytes]:
    """Return the package's static files with the book's on top, by name in the site."""
    package_static = resources.files(PACKAGE_NAME) / STATIC_DIR_NAME
    files = read_traversable(package_static, STATIC_DIR_NAME)
    if project.static_dir.is_dir():
        files.update(read_traversable(project.static_dir, STATIC_DIR_NAME))
    if PYGMENTS_CSS_NAME not in files:
        files[PYGMENTS_CSS_NAME] = pygments_css(config).encode("utf-8")
    return files


def site_files(
    project: Project,
    config: BookConfig,
    pages: list[Page],
    converted: ConvertedPages,
) -> dict[str, bytes]:
    """Return every file of the site, by its POSIX path in the site directory."""
    files = page_files(project, config, pages)
    for asset in sorted(converted.assets):
        files[asset.as_posix()] = (project.book_dir / asset).read_bytes()
    files.update(static_files(project, config))
    search_index = json.dumps(converted.search_index, ensure_ascii=False)
    files[SEARCH_INDEX_NAME] = search_index.encode("utf-8")
    files[NOJEKYLL_NAME] = b""
    return files


def find_overrides(project: Project) -> list[str]:
    """Return the files under ``theme/`` in force, as POSIX paths from the project."""
    if not project.theme_dir.is_dir():
        return []
    return sorted(
        path.relative_to(project.project_dir).as_posix()
        for path in project.theme_dir.rglob("*")
        if path.is_file()
    )
