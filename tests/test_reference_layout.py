"""Tests for the reference layout, on the sample reference site."""

import json
import re
from pathlib import Path

import pytest

from bookspine import build_book
from bookspine.errors import BuildError


@pytest.fixture
def reference_site_dir(reference_dir: Path) -> Path:
    return build_book(reference_dir).site_dir


def page_text(site_dir: Path, url: str = "") -> str:
    return (site_dir / url / "index.html").read_text(encoding="utf-8")


def body_of(page_html: str) -> str:
    return page_html.partition('class="prose"')[2]


def test_pages_keep_their_addresses(reference_site_dir: Path) -> None:
    for url in ("tools/", "tools/find/", "tools/deep/", "tools/deep/first/", "notes/"):
        assert (reference_site_dir / url / "index.html").is_file()


@pytest.mark.parametrize(
    "url", ["", "tools/", "tools/find/", "tools/deep/first/", "notes/", "help/"]
)
def test_no_page_shows_a_number_or_the_books_words(
    reference_site_dir: Path, url: str
) -> None:
    text = page_text(reference_site_dir, url)
    assert "Part I" not in text
    assert "Chapter" not in text
    assert "toc-num" not in text
    assert "secnum" not in text
    assert "chapter-number" not in text


def test_headings_keep_their_anchors(reference_site_dir: Path) -> None:
    assert '<h2 id="count-files">Count files' in page_text(
        reference_site_dir, "tools/find/"
    )


def test_figures_count_within_the_page(reference_site_dir: Path) -> None:
    assert ">Figure 1</span>" in page_text(reference_site_dir, "tools/find/")


def test_the_first_paragraph_opens_the_page_head(reference_site_dir: Path) -> None:
    text = page_text(reference_site_dir, "tools/find/")
    head, _, _ = text.partition('class="prose"')
    assert '<p class="lede">Search a tree' in head
    assert "Search a tree" not in body_of(text)


def test_a_link_in_the_lede_reaches_its_page(reference_site_dir: Path) -> None:
    assert 'href="../../tools/plain/"' in page_text(reference_site_dir, "tools/find/")
    assert 'href="../tools/find/"' in page_text(reference_site_dir, "tools/")


def test_the_search_keeps_the_first_paragraph(reference_site_dir: Path) -> None:
    index = json.loads((reference_site_dir / "search.json").read_text(encoding="utf-8"))
    entries = [entry for entry in index if entry["url"] == "tools/find/"]
    assert "Search a tree" in entries[0]["text"]
    assert entries[0]["page"] == "Tools › Finding files"


def test_the_contents_show_summaries_as_markdown(reference_site_dir: Path) -> None:
    text = page_text(reference_site_dir)
    assert '<span class="chapter-list-summary">Count files with <code>' in text


def test_the_description_is_plain_text(reference_site_dir: Path) -> None:
    text = page_text(reference_site_dir, "tools/find/")
    assert '<meta name="description" content="Count files with find.">' in text


def test_the_home_page_lists_the_contents_before_its_text(
    reference_site_dir: Path,
) -> None:
    text = page_text(reference_site_dir)
    assert text.index('id="contents"') < text.index("Each page answers one question")


def test_a_part_lists_its_pages_before_its_text(reference_site_dir: Path) -> None:
    text = page_text(reference_site_dir, "tools/")
    assert ">Pages</h2>" in text
    assert text.index(">Pages</h2>") < text.index('class="prose"')


def test_a_part_without_pages_is_in_preparation(reference_site_dir: Path) -> None:
    assert ">In preparation.</p>" in page_text(reference_site_dir)
    assert "in preparation.</p>" in page_text(reference_site_dir, "notes/")


def test_an_unfinished_page_says_so(reference_site_dir: Path) -> None:
    assert 'class="status-note">This page is in preparation.' in page_text(
        reference_site_dir, "tools/plain/"
    )


def test_a_part_shows_its_icon(reference_site_dir: Path) -> None:
    text = page_text(reference_site_dir, "tools/find/")
    icon = '<svg class="icon" aria-hidden="true" fill="currentColor"'
    assert text.count(icon) == 2
    assert icon in page_text(reference_site_dir)


def test_a_part_without_an_icon_needs_none(reference_site_dir: Path) -> None:
    text = page_text(reference_site_dir, "notes/")
    assert '<p class="chapter-kicker">Topic</p>' in text


def test_a_missing_icon_stops_the_build(reference_dir: Path) -> None:
    (reference_dir / "theme/icons/wrench.svg").unlink()
    with pytest.raises(BuildError, match="no such icon: wrench"):
        build_book(reference_dir)


@pytest.mark.parametrize("name", ["../secret", "a/b", ".."])
def test_an_icon_name_cannot_leave_its_directory(
    reference_dir: Path, name: str
) -> None:
    opener_path = reference_dir / "book/tools/index.md"
    text = opener_path.read_text(encoding="utf-8").replace("wrench", name)
    opener_path.write_text(text, encoding="utf-8")
    with pytest.raises(BuildError, match="one plain path component"):
        build_book(reference_dir)


def test_on_this_page_needs_two_headings(reference_site_dir: Path) -> None:
    text = page_text(reference_site_dir, "tools/find/")
    assert '<p class="itc-label">On this page</p>' in text
    assert "itc-label" not in page_text(reference_site_dir, "tools/plain/")


def test_the_sidebar_lists_the_headings_of_the_current_page(
    reference_site_dir: Path,
) -> None:
    sidebar = page_text(reference_site_dir, "tools/find/").partition("<main class")[0]
    assert '<a href="#count-by-type">' in sidebar
    other = page_text(reference_site_dir, "tools/plain/").partition("<main class")[0]
    assert '<a href="#count-by-type">' not in other


def test_a_page_with_section_pages_lists_them(reference_site_dir: Path) -> None:
    text = page_text(reference_site_dir, "tools/deep/")
    assert ">Sections</h2>" in text
    assert 'href="../../tools/deep/first/"' in text


def test_a_section_page_leads_back_to_its_chapter(reference_site_dir: Path) -> None:
    text = page_text(reference_site_dir, "tools/deep/first/")
    assert re.search(r'chapter-kicker"><a href="[^"]*deep/">.*Deep dive</a>', text)


def test_no_page_links_to_its_neighbours(reference_site_dir: Path) -> None:
    assert 'class="pagenav"' not in page_text(reference_site_dir, "tools/find/")


def test_a_help_page_keeps_its_first_paragraph(reference_site_dir: Path) -> None:
    assert "first paragraph stays" in body_of(page_text(reference_site_dir, "help/"))


def test_the_search_box_uses_the_sites_words(reference_site_dir: Path) -> None:
    text = page_text(reference_site_dir)
    assert 'placeholder="Search the site…"' in text
    assert "Type what you are looking for." in text


def test_a_book_keeps_its_own_search_words(project_dir: Path) -> None:
    text = page_text(build_book(project_dir).site_dir)
    assert 'placeholder="Search the book…"' in text
    assert "Type to search chapter and section text." in text


def test_inline_code_breaks_only_at_spaces(reference_site_dir: Path) -> None:
    text = page_text(reference_site_dir, "tools/find/")
    assert '<span class="tok">-type</span> <span class="tok">f</span>' in text


def test_a_theme_template_replaces_the_layouts_own(reference_dir: Path) -> None:
    templates_dir = reference_dir / "theme/templates/reference"
    templates_dir.mkdir(parents=True)
    (templates_dir / "part.html").write_text("Own part page", encoding="utf-8")
    site_dir = build_book(reference_dir).site_dir
    assert page_text(site_dir, "tools/") == "Own part page"
