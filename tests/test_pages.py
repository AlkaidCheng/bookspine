"""Tests for reading a book's pages in order."""

from pathlib import Path

import pytest

from guidebook.config import BookConfig, ChapterConfig, PartConfig, load_config
from guidebook.errors import BuildError
from guidebook.pages import (
    Page,
    load_pages,
    read_page,
    roman_numeral,
    split_front_matter,
)


def sample_pages(project_dir: Path) -> list[Page]:
    config = load_config(project_dir / "book.yaml")
    return load_pages(config, project_dir / "book")


@pytest.mark.parametrize(
    ("number", "numeral"),
    [(1, "I"), (4, "IV"), (9, "IX"), (12, "XII"), (14, "XIV"), (40, "XL")],
)
def test_roman_numeral(number: int, numeral: str) -> None:
    assert roman_numeral(number) == numeral


def test_front_matter_is_split_from_the_body() -> None:
    meta, body = split_front_matter("---\ntitle: A\n---\nBody\n", Path("a.md"))
    assert meta == {"title": "A"}
    assert body == "Body\n"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("Body\n", "missing YAML front matter"),
        ("---\ntitle: [\n---\nBody\n", "invalid front matter"),
        ("---\n- a\n---\nBody\n", "must be a mapping"),
    ],
)
def test_invalid_front_matter_fails(text: str, message: str) -> None:
    with pytest.raises(BuildError, match=message):
        split_front_matter(text, Path("a.md"))


def test_a_listed_file_must_exist(tmp_path: Path) -> None:
    with pytest.raises(BuildError, match="missing file: a.md"):
        read_page(tmp_path, "chapter", Path("a.md"), "a/")


def test_a_page_needs_a_title(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("---\nsummary: S\n---\nBody\n", encoding="utf-8")
    with pytest.raises(BuildError, match="front matter needs a title"):
        read_page(tmp_path, "chapter", Path("a.md"), "a/")


def test_pages_come_in_reading_order_with_numbers(project_dir: Path) -> None:
    pages = sample_pages(project_dir)
    assert [(page.kind, page.number, page.url) for page in pages] == [
        ("home", "", ""),
        ("part", "I", "methods/"),
        ("chapter", "1", "methods/basics/"),
        ("chapter", "2", "methods/split/"),
        ("section", "2.1", "methods/split/first/"),
        ("section", "2.2", "methods/split/second/"),
    ]


def test_pages_are_linked_to_their_neighbours(project_dir: Path) -> None:
    pages = sample_pages(project_dir)
    assert pages[0].prev is None
    assert pages[-1].next is None
    for before, after in zip(pages, pages[1:], strict=False):
        assert before.next is after
        assert after.prev is before


def test_a_chapter_shares_its_counters_with_its_section_pages(
    project_dir: Path,
) -> None:
    pages = sample_pages(project_dir)
    chapter = pages[3]
    assert [section.chapter for section in chapter.section_pages] == [chapter, chapter]
    assert all(page.counters is chapter.counters for page in chapter.section_pages)
    assert pages[2].counters is not chapter.counters


def test_chapter_numbers_run_through_the_parts(tmp_path: Path) -> None:
    for name in ("index.md", "one/index.md", "two/index.md", "one/a.md", "two/b.md"):
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.write_text("---\ntitle: T\n---\n", encoding="utf-8")
    config = BookConfig(
        title="T",
        author="A",
        parts=(
            PartConfig("one", (ChapterConfig("a", "a.md"),)),
            PartConfig("two", (ChapterConfig("b", "b.md"),)),
        ),
    )
    numbers = [page.number for page in load_pages(config, tmp_path)]
    assert numbers == ["", "I", "1", "II", "2"]


def test_chapter_number_comes_from_the_chapter_on_a_section_page(
    project_dir: Path,
) -> None:
    pages = sample_pages(project_dir)
    assert [page.chapter_number for page in pages] == ["", "", "1", "2", "2", "2"]


def test_an_opener_with_section_pages_leaves_headings_plain(
    project_dir: Path,
) -> None:
    pages = sample_pages(project_dir)
    assert [page.has_numbered_headings for page in pages] == [
        False,
        False,
        True,
        False,
        True,
        True,
    ]


def test_links_between_pages_are_relative(project_dir: Path) -> None:
    pages = sample_pages(project_dir)
    home, section = pages[0], pages[-1]
    assert home.root == "./"
    assert section.root == "../../../"
    assert section.href(home) == "../../../"
    assert home.href(section) == "./methods/split/second/"


def test_a_page_writes_to_index_html_under_its_url(project_dir: Path) -> None:
    pages = sample_pages(project_dir)
    assert pages[0].output_name == "index.html"
    assert pages[2].output_name == "methods/basics/index.html"


def test_pages_with_equal_fields_stay_distinct() -> None:
    fields = {"kind": "chapter", "source_path": Path("a.md"), "url": "a/"}
    first = Page(meta={}, body_md="", **fields)  # type: ignore[arg-type]
    second = Page(meta={}, body_md="", **fields)  # type: ignore[arg-type]
    assert first != second
    assert first == first
