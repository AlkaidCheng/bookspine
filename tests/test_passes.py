"""Tests for the passes over a page's HTML."""

from pathlib import Path
from typing import Any

import pytest

from guidebook.config import SEARCH_TEXT_LIMIT
from guidebook.errors import BuildError
from guidebook.pages import Page
from guidebook.passes import (
    mark_external_links,
    number_boxes,
    number_figures_and_tables,
    number_headings,
    outside_code,
    resolve_citations,
    rewrite_links,
    search_entries,
)
from guidebook.site import make_markdown


def make_page(body_html: str = "", **fields: Any) -> Page:
    fields.setdefault("kind", "chapter")
    fields.setdefault("number", "3")
    fields.setdefault("source_path", Path("part/page.md"))
    fields.setdefault("url", "part/page/")
    fields.setdefault("meta", {})
    return Page(body_md="", body_html=body_html, **fields)


TABLE = "<table><tr><td>a</td></tr></table>"


def test_outside_code_leaves_code_alone() -> None:
    text = "a <code>a</code> a <pre>a</pre>"
    transformed = outside_code(text, lambda segment: segment.replace("a", "b"))
    assert transformed == "b <code>a</code> b <pre>a</pre>"


def test_headings_are_numbered_within_the_chapter() -> None:
    page = make_page(
        '<h2 id="one">One</h2><h3 id="two">Two</h3><h2 id="three">Three</h2>'
    )
    number_headings(page)
    assert [section["number"] for section in page.sections] == ["3.1", "3.1.1", "3.2"]
    assert '<span class="secnum">3.1.1</span> Two' in page.body_html
    assert 'href="#two"' in page.body_html


def test_a_section_page_numbers_within_itself() -> None:
    page = make_page('<h2 id="one">One</h2>', kind="section", number="3.2")
    number_headings(page)
    assert page.sections[0]["number"] == "3.2.1"


@pytest.mark.parametrize("title", ["References", "Further reading", "further reading"])
def test_closing_headings_stay_unnumbered(title: str) -> None:
    page = make_page(f'<h2 id="a">One</h2><h2 id="b">{title}</h2><h2 id="c">Two</h2>')
    number_headings(page)
    assert [section["number"] for section in page.sections] == ["3.1", "", "3.2"]


def test_an_opener_with_section_pages_has_plain_headings() -> None:
    opener = make_page('<h2 id="one">One</h2>', section_pages=[make_page()])
    number_headings(opener)
    assert opener.sections[0]["number"] == ""
    assert "secnum" not in opener.body_html


def test_figures_are_numbered_with_their_alt_text(tmp_path: Path) -> None:
    page = make_page('<p><img alt="A caption" src="a.png"></p>')
    number_figures_and_tables(page, tmp_path)
    assert '<figure id="fig-1">' in page.body_html
    assert '<span class="caplabel">Figure 3.1</span> A caption' in page.body_html


def test_a_local_svg_is_inlined_without_its_xml_declaration(tmp_path: Path) -> None:
    svg_path = tmp_path / "part" / "a.svg"
    svg_path.parent.mkdir()
    svg_path.write_text('<?xml version="1.0"?>\n<svg viewBox="0 0 1 1"/>')
    page = make_page('<p><img alt="A &amp; B" src="a.svg"></p>')
    number_figures_and_tables(page, tmp_path)
    assert '<svg class="inline-svg" role="img"' in page.body_html
    assert "<?xml" not in page.body_html


def test_a_remote_svg_stays_an_image(tmp_path: Path) -> None:
    img = '<img alt="A" src="https://example.org/a.svg">'
    page = make_page(f"<p>{img}</p>")
    number_figures_and_tables(page, tmp_path)
    assert img in page.body_html


def test_a_missing_figure_fails(tmp_path: Path) -> None:
    page = make_page('<p><img alt="A" src="a.svg"></p>')
    with pytest.raises(BuildError, match="missing figure: a.svg"):
        number_figures_and_tables(page, tmp_path)


def test_only_captioned_tables_are_numbered(tmp_path: Path) -> None:
    page = make_page(f"{TABLE}\n{TABLE}\n<p>Table: A caption</p>")
    number_figures_and_tables(page, tmp_path)
    assert page.body_html.count('<figure class="table">') == 1
    assert '<figure class="table" id="tab-1">' in page.body_html
    assert '<span class="caplabel">Table 3.1</span> A caption' in page.body_html


def test_counts_run_through_shared_counters(tmp_path: Path) -> None:
    counters: dict[str, int] = {}
    first = make_page(f"{TABLE}<p>Table: A</p>", counters=counters)
    second = make_page(f"{TABLE}<p>Table: B</p>", counters=counters)
    number_figures_and_tables(first, tmp_path)
    number_figures_and_tables(second, tmp_path)
    assert "Table 3.2" in second.body_html


def box(kind: str, title: str) -> str:
    return (
        f'<div class="admonition {kind}">\n'
        f'<p class="admonition-title">{title}</p>\n<p>Body</p>\n</div>'
    )


def test_numbered_boxes_count_within_the_chapter() -> None:
    page = make_page(box("definition", "Term") + box("definition", "Definition"))
    number_boxes(page)
    assert '<span class="boxlabel">Definition 3.1</span>' in page.body_html
    assert '<span class="boxtitle">Term</span>' in page.body_html
    assert 'id="definition-3-2"' in page.body_html
    assert page.body_html.count("boxtitle") == 1


def test_labelled_boxes_take_no_number() -> None:
    page = make_page(box("note", "Note") + box("warning", "Watch out"))
    number_boxes(page)
    assert '<span class="boxlabel">Note</span></p>' in page.body_html
    assert '<span class="boxtitle">Watch out</span>' in page.body_html


def test_other_boxes_are_left_alone() -> None:
    body = box("summary", "Key points")
    page = make_page(body)
    number_boxes(page)
    assert page.body_html == body


def test_citations_are_numbered_by_first_use() -> None:
    meta = {"references": {"a": "Paper *A*", "b": "Paper B"}}
    page = make_page("<p>[@b] and [@a; @b]</p>", meta=meta)
    assert resolve_citations(page, make_markdown()) == []
    assert '<a class="cite" href="#ref-b">1</a>' in page.body_html
    assert '<a class="cite" href="#ref-a">2</a>, ' in page.body_html
    assert '<li id="ref-a">Paper <em>A</em></li>' in page.body_html


def test_an_unknown_citation_fails() -> None:
    page = make_page("<p>[@a]</p>")
    with pytest.raises(BuildError, match=r"citation \[@a\] has no entry"):
        resolve_citations(page, make_markdown())


def test_an_uncited_reference_warns() -> None:
    page = make_page("<p>Text</p>", meta={"references": {"a": "Paper"}})
    (warning,) = resolve_citations(page, make_markdown())
    assert "references never cited: a" in warning


def test_citations_in_code_stay_as_written() -> None:
    page = make_page("<code>[@a]</code>")
    resolve_citations(page, make_markdown())
    assert page.body_html == "<code>[@a]</code>"


def test_references_must_be_a_mapping() -> None:
    page = make_page("<p>Text</p>", meta={"references": ["a"]})
    with pytest.raises(BuildError, match="must be a mapping"):
        resolve_citations(page, make_markdown())


def test_a_markdown_link_becomes_a_site_url(tmp_path: Path) -> None:
    target = make_page(source_path=Path("other/target.md"), url="other/target/")
    page = make_page('<a href="../other/target.md#a-section">x</a>')
    rewrite_links(page, {target.source_path: target}, set(), tmp_path)
    assert page.body_html == '<a href="../../other/target/#a-section">x</a>'


def test_a_link_to_a_page_not_in_the_book_fails(tmp_path: Path) -> None:
    page = make_page('<a href="missing.md">x</a>')
    with pytest.raises(BuildError, match="not in book.yaml: missing.md"):
        rewrite_links(page, {}, set(), tmp_path)


def test_a_link_out_of_the_book_fails(tmp_path: Path) -> None:
    page = make_page('<a href="../../outside.md">x</a>')
    with pytest.raises(BuildError, match="link escapes the book"):
        rewrite_links(page, {}, set(), tmp_path)


def test_a_local_asset_is_recorded_and_its_link_kept(tmp_path: Path) -> None:
    asset_path = tmp_path / "part" / "figures" / "a.png"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_bytes(b"png")
    page = make_page('<img src="figures/a.png">')
    assets: set[Path] = set()
    rewrite_links(page, {}, assets, tmp_path)
    assert assets == {Path("part/figures/a.png")}
    assert page.body_html == '<img src="../../part/figures/a.png">'


def test_a_missing_asset_fails(tmp_path: Path) -> None:
    page = make_page('<img src="figures/a.png">')
    with pytest.raises(BuildError, match="missing asset: figures/a.png"):
        rewrite_links(page, {}, set(), tmp_path)


@pytest.mark.parametrize(
    "link", ['<a href="https://example.org/a.md">x</a>', '<a href="/a.md">x</a>']
)
def test_absolute_links_are_left_alone(tmp_path: Path, link: str) -> None:
    page = make_page(link)
    rewrite_links(page, {}, set(), tmp_path)
    assert page.body_html == link


def test_external_links_are_marked() -> None:
    page = make_page('<a href="https://example.org">x</a><a href="#a">y</a>')
    mark_external_links(page)
    assert 'class="external" rel="noopener"' in page.body_html
    assert '<a href="#a">y</a>' in page.body_html


def test_search_has_one_entry_per_section() -> None:
    page = make_page(
        '<p>Opening text</p><h2 id="one">One</h2><p>First &amp; text</p>'
        '<h2 id="two">Two</h2><p>Second text</p>',
        title="A title",
    )
    entries = search_entries(page)
    assert [entry["url"] for entry in entries] == [
        "part/page/",
        "part/page/#one",
        "part/page/#two",
    ]
    assert entries[1]["section"] == "One"
    assert entries[1]["text"] == "First & text"
    assert entries[1]["page"] == "3. A title"


def test_search_names_a_section_page_by_its_number() -> None:
    page = make_page("<p>Text</p>", kind="section", number="3.1", title="A title")
    assert search_entries(page)[0]["page"] == "3.1 A title"


def test_search_text_is_cut_to_its_limit() -> None:
    page = make_page("<p>" + "word " * SEARCH_TEXT_LIMIT + "</p>")
    assert len(search_entries(page)[0]["text"]) == SEARCH_TEXT_LIMIT
