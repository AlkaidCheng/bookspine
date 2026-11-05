"""Tests for the help page: its page, its link and its place outside the book."""

import json
import re
from pathlib import Path

import pytest
import yaml

from guidebook import BuildError, build_book
from guidebook.config import load_config
from guidebook.pages import load_pages

HELP_NAME = "help.md"
HELP_URL = "help/"
HELP_TITLE = "Help"
CURRENT_MARK = 'aria-current="page"'


def page_text(site_dir: Path, url: str) -> str:
    return (site_dir / url / "index.html").read_text(encoding="utf-8")


def sidebar_foot(page_html: str) -> str:
    match = re.search(r'<div class="sidebar-foot">.*?</div>', page_html, re.S)
    assert match
    return match.group(0)


def set_config_keys(project_dir: Path, **keys: object) -> None:
    """Change `keys` in the project's ``book.yaml``, removing those set to None."""
    config_path = project_dir / "book.yaml"
    record = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    record.update(keys)
    record = {key: value for key, value in record.items() if value is not None}
    config_path.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")


def write_page(path: Path, title: str, body: str = "Text.\n") -> None:
    path.write_text(f"---\ntitle: {title}\n---\n\n{body}", encoding="utf-8")


@pytest.fixture
def site_dir(project_dir: Path) -> Path:
    return build_book(project_dir).site_dir


def test_the_help_page_stands_outside_the_reading_order(project_dir: Path) -> None:
    config = load_config(project_dir / "book.yaml")
    *reading_pages, help_page = load_pages(config, project_dir / "book")
    assert help_page.kind == "help"
    assert help_page.url == HELP_URL
    assert help_page.prev is None
    assert help_page.next is None
    assert reading_pages[-1].next is None


def test_a_book_without_the_key_has_no_help_page(project_dir: Path) -> None:
    set_config_keys(project_dir, help_page=None)
    site_dir = build_book(project_dir).site_dir
    assert not (site_dir / HELP_URL).exists()
    assert f">{HELP_TITLE}</a>" not in page_text(site_dir, "")


@pytest.mark.parametrize(
    ("url", "href"),
    [
        ("", "./help/"),
        ("methods", "../help/"),
        ("methods/basics", "../../help/"),
        ("methods/split/first", "../../../help/"),
        ("glossary/terms", "../../help/"),
        ("help", "../help/"),
    ],
)
def test_every_page_links_to_the_help_page(site_dir: Path, url: str, href: str) -> None:
    assert f'<a href="{href}"' in sidebar_foot(page_text(site_dir, url))


def test_the_link_stands_above_the_source_link(site_dir: Path) -> None:
    foot = sidebar_foot(page_text(site_dir, ""))
    assert foot.index(f">{HELP_TITLE}</a>") < foot.index(">Source on ExampleHost</a>")


def test_only_the_help_page_marks_its_link_as_current(site_dir: Path) -> None:
    assert CURRENT_MARK in sidebar_foot(page_text(site_dir, "help"))
    assert CURRENT_MARK not in page_text(site_dir, "")


def test_a_book_without_a_repository_keeps_the_link(project_dir: Path) -> None:
    set_config_keys(project_dir, repo=None, repo_host=None)
    foot = sidebar_foot(page_text(build_book(project_dir).site_dir, ""))
    assert f">{HELP_TITLE}</a>" in foot
    assert "Source on" not in foot


def test_a_book_with_neither_has_no_sidebar_foot(project_dir: Path) -> None:
    set_config_keys(project_dir, help_page=None, repo=None, repo_host=None)
    site_dir = build_book(project_dir).site_dir
    assert "sidebar-foot" not in page_text(site_dir, "")


def test_the_help_page_shows_its_title_and_summary(site_dir: Path) -> None:
    help_html = page_text(site_dir, "help")
    assert f'<h1 class="chapter-title">{HELP_TITLE}</h1>' in help_html
    assert '<p class="lede">The conventions of this book' in help_html
    assert f"<title>{HELP_TITLE} · Sample Book</title>" in help_html


def test_a_summary_is_optional(project_dir: Path) -> None:
    write_page(project_dir / "book" / HELP_NAME, HELP_TITLE)
    site_dir = build_book(project_dir).site_dir
    assert '<p class="lede">' not in page_text(site_dir, "help")


def test_the_help_page_has_no_numbers_and_no_neighbours(site_dir: Path) -> None:
    help_html = page_text(site_dir, "help")
    assert '<h2 id="conventions">Conventions' in help_html
    assert 'class="pagenav' not in help_html


def test_no_page_leads_to_the_help_page_except_its_link(site_dir: Path) -> None:
    assert page_text(site_dir, "").count(HELP_URL) == 1
    assert page_text(site_dir, "glossary/equations").count(HELP_URL) == 1
    assert 'class="pagenav-next"' not in page_text(site_dir, "glossary/equations")


def test_the_search_covers_the_help_page_after_the_chapters(site_dir: Path) -> None:
    index = json.loads((site_dir / "search.json").read_text(encoding="utf-8"))
    urls = [entry["url"] for entry in index]
    assert "help/#conventions" in urls
    first_help_entry = urls.index("help/#conventions")
    assert all(not url.startswith("methods/") for url in urls[first_help_entry:])


def test_a_page_can_link_to_the_help_page(project_dir: Path) -> None:
    chapter_path = project_dir / "book" / "methods" / "basics.md"
    link = "[the help page](../help.md)"
    chapter_path.write_text(
        chapter_path.read_text(encoding="utf-8") + f"\n{link}\n", encoding="utf-8"
    )
    site_dir = build_book(project_dir).site_dir
    assert '<a href="../../help/">the help page</a>' in page_text(
        site_dir, "methods/basics"
    )


def test_the_help_page_has_an_edit_link(site_dir: Path) -> None:
    edit_link = "https://example.org/sample-repo/edit/help.md"
    assert edit_link in page_text(site_dir, "help")


def test_the_glossary_follows_the_last_page_of_a_book_without_parts(
    tmp_path: Path,
) -> None:
    (tmp_path / "book.yaml").write_text(
        f"title: T\nauthor: A\nhelp_page: {HELP_NAME}\n", encoding="utf-8"
    )
    book_dir = tmp_path / "book"
    book_dir.mkdir()
    write_page(book_dir / "index.md", "T", "\\glossary{A term} Text.\n")
    write_page(book_dir / HELP_NAME, HELP_TITLE)
    site_dir = build_book(tmp_path).site_dir
    assert '<a class="pagenav-next" href="./glossary/">' in page_text(site_dir, "")
    assert 'class="pagenav' not in page_text(site_dir, "help")


def test_a_help_page_must_exist(project_dir: Path) -> None:
    (project_dir / "book" / HELP_NAME).unlink()
    with pytest.raises(BuildError, match="missing file: help.md"):
        build_book(project_dir)


def test_the_help_page_cannot_be_the_home_page(project_dir: Path) -> None:
    set_config_keys(project_dir, help_page="index.md")
    with pytest.raises(BuildError, match="help_page index.md clashes"):
        build_book(project_dir)


def test_the_help_page_cannot_take_a_part_s_address(project_dir: Path) -> None:
    write_page(project_dir / "book" / "methods.md", "Methods")
    set_config_keys(project_dir, help_page="methods.md")
    with pytest.raises(BuildError, match="help_page methods.md clashes"):
        build_book(project_dir)


def test_the_help_page_cannot_take_the_glossary_s_address(project_dir: Path) -> None:
    write_page(project_dir / "book" / "glossary.md", "Glossary")
    set_config_keys(project_dir, help_page="glossary.md")
    with pytest.raises(BuildError, match="address glossary/, which is taken"):
        build_book(project_dir)
