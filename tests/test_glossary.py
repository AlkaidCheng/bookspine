"""Tests for the glossary: its tags, its page and its place in the book."""

import json
from pathlib import Path
from typing import Any

import pytest

from bookspine import BuildError, build_book
from bookspine.equations import number_equations
from bookspine.glossary import collect_terms, make_glossary_pages
from bookspine.pages import GlossaryEntry, Page
from bookspine.passes import number_boxes, number_headings


def make_page(body_html: str = "", **fields: Any) -> Page:
    fields.setdefault("kind", "chapter")
    fields.setdefault("number", "1")
    fields.setdefault("source_path", Path("part/page.md"))
    fields.setdefault("url", "part/page/")
    fields.setdefault("meta", {})
    fields.setdefault("title", "A chapter")
    return Page(body_md="", body_html=body_html, **fields)


def box(kind: str, title: str, body: str) -> str:
    return (
        f'<div class="admonition {kind}">\n'
        f'<p class="admonition-title">{title}</p>\n{body}\n</div>'
    )


def display(tex: str) -> str:
    return f'<div class="arithmatex">\\[{tex}\\]</div>\n'


def named_equation(page: Page) -> GlossaryEntry:
    (entry,) = page.named_equations
    return entry


def page_text(site_dir: Path, url: str) -> str:
    return (site_dir / url / "index.html").read_text(encoding="utf-8")


def add_to_config(project_dir: Path, text: str) -> None:
    config_path = project_dir / "book.yaml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8") + text, encoding="utf-8"
    )


def test_a_tag_in_a_paragraph_makes_a_term_of_it() -> None:
    page = make_page("<p>A jet is a spray of hadrons. \\glossary{Jet}</p>")
    collect_terms(page)
    (term,) = page.terms
    assert term.name == "Jet"
    assert term.anchor == "term-jet"
    assert page.body_html == (
        '<p>A jet is a spray of hadrons. <span id="term-jet"></span></p>'
    )


def test_a_term_is_located_by_its_section() -> None:
    page = make_page('<h2 id="a">One</h2>\n<p>Text. \\glossary{Jet}</p>')
    number_headings(page)
    collect_terms(page)
    assert page.terms[0].locator == "Section 1.1"


def test_a_term_before_any_section_is_located_by_its_page() -> None:
    page = make_page("<p>Text. \\glossary{Jet}</p>")
    collect_terms(page)
    assert page.terms[0].locator == "A chapter"


def test_a_name_is_read_as_text() -> None:
    page = make_page("<p>Text. \\glossary{R&amp;D}</p>")
    collect_terms(page)
    assert page.terms[0].name == "R&D"


def test_a_tag_in_code_stays_as_written() -> None:
    body = "<p>Write <code>\\glossary{Jet}</code>.</p><pre>\\glossary{Jet}</pre>"
    page = make_page(body)
    collect_terms(page)
    assert page.terms == []
    assert page.body_html == body


def test_a_bare_tag_needs_a_box() -> None:
    page = make_page("<p>Text. \\glossary</p>")
    with pytest.raises(BuildError, match="needs a name outside the start of a box"):
        collect_terms(page)


def test_a_longer_command_is_not_a_tag() -> None:
    body = "<p>Text \\glossaryentry here.</p>"
    page = make_page(body)
    collect_terms(page)
    assert page.body_html == body


def test_a_box_gives_its_title_and_number() -> None:
    page = make_page(box("definition", "Jet", "<p>\\glossary\nA spray.</p>"))
    number_boxes(page)
    collect_terms(page)
    (term,) = page.terms
    assert term.name == "Jet"
    assert term.anchor == "definition-1-1"
    assert term.locator == "Definition 1.1"
    assert "\\glossary" not in page.body_html


def test_a_tag_alone_in_a_box_leaves_no_empty_paragraph() -> None:
    page = make_page(box("definition", "Jet", "<p>\\glossary</p>\n<p>A spray.</p>"))
    number_boxes(page)
    collect_terms(page)
    assert "<p></p>" not in page.body_html


def test_a_name_in_a_box_replaces_its_title() -> None:
    page = make_page(box("definition", "Jet", "<p>\\glossary{Hadron jet} A spray.</p>"))
    number_boxes(page)
    collect_terms(page)
    assert page.terms[0].name == "Hadron jet"


def test_a_box_without_an_id_gets_one() -> None:
    page = make_page(box("note", "Jet", "<p>\\glossary A spray.</p>"))
    number_boxes(page)
    collect_terms(page)
    assert page.terms[0].anchor == "term-jet"
    assert '<div class="admonition note" id="term-jet">' in page.body_html


def test_a_box_with_no_title_needs_a_name() -> None:
    page = make_page(box("note", "Note", "<p>\\glossary A spray.</p>"))
    number_boxes(page)
    with pytest.raises(BuildError, match="needs a name in a box with no title"):
        collect_terms(page)


def test_a_tag_later_in_a_box_needs_a_name_of_its_own() -> None:
    page = make_page(box("definition", "Jet", "<p>Text.</p><p>\\glossary</p>"))
    number_boxes(page)
    with pytest.raises(BuildError, match="needs a name outside the start of a box"):
        collect_terms(page)


def test_a_tag_names_an_equation() -> None:
    page = make_page(display(r"x = 1 \label{eq:a} \glossary{Unit value}"))
    number_equations(page, {})
    entry = named_equation(page)
    assert entry.name == "Unit value"
    assert entry.anchor == "mjx-eqn:eq:a"
    assert entry.locator == "Equation (1.1)"


def test_the_tag_leaves_the_equation_for_mathjax() -> None:
    page = make_page(display(r"x = 1 \label{eq:a} \glossary{Unit value}"))
    number_equations(page, {})
    assert "\\glossary" not in page.body_html
    assert r"\label{eq:a}" in page.body_html


def test_a_tag_names_one_row_of_an_equation() -> None:
    tex = (
        r"\begin{align} a \label{eq:a} \\ b \label{eq:b} \glossary{Second} \end{align}"
    )
    page = make_page(display(tex))
    number_equations(page, {})
    entry = named_equation(page)
    assert entry.anchor == "mjx-eqn:eq:b"
    assert entry.locator == "Equation (1.2)"


def test_a_tag_inside_an_inner_environment_counts() -> None:
    tex = r"\begin{aligned} a \glossary{Name} \\ b \end{aligned} \label{eq:a}"
    page = make_page(display(tex))
    number_equations(page, {})
    assert named_equation(page).name == "Name"


def test_a_tag_on_an_empty_last_row_fails() -> None:
    tex = "\\begin{align} a \\\\ \\glossary{Name}\n\\end{align}"
    page = make_page(display(tex))
    with pytest.raises(BuildError, match="needs a name"):
        number_equations(page, {})


def test_a_manual_tag_is_the_number_shown() -> None:
    page = make_page(display(r"x \tag{A} \label{eq:a} \glossary{Name}"))
    number_equations(page, {})
    assert named_equation(page).locator == "Equation (A)"


@pytest.mark.parametrize(
    "tex", [r"x \glossary{Name}", r"x \label{eq:a} \notag \glossary{Name}"]
)
def test_a_named_equation_needs_a_label_and_a_number(tex: str) -> None:
    page = make_page(display(tex))
    with pytest.raises(BuildError, match="needs a .label and a number"):
        number_equations(page, {})


@pytest.mark.parametrize(
    "tex",
    [
        r"x \label{eq:a} \glossary",
        r"\begin{align} a \label{eq:a} \end{align} \glossary{Name}",
    ],
)
def test_a_tag_in_an_equation_needs_a_name_and_its_environment(tex: str) -> None:
    page = make_page(display(tex))
    with pytest.raises(BuildError, match="needs a name"):
        number_equations(page, {})


def make_entry(name: str) -> GlossaryEntry:
    return GlossaryEntry(name=name, anchor="a", locator="Here")


def test_no_tags_make_no_pages() -> None:
    assert make_glossary_pages([make_page()]) == []


def test_entries_are_sorted_without_regard_to_case() -> None:
    page = make_page(terms=[make_entry(name) for name in ("b", "C", "a")])
    _, terms = make_glossary_pages([page])
    positions = [terms.body_html.index(f">{name}</a>") for name in ("a", "b", "C")]
    assert positions == sorted(positions)


def test_each_kind_has_a_page_of_its_own() -> None:
    page = make_page(terms=[make_entry("a")], named_equations=[make_entry("b")])
    _, terms, equations = make_glossary_pages([page])
    assert (terms.title, terms.url) == ("Terms", "glossary/terms/")
    assert (equations.title, equations.url) == ("Equations", "glossary/equations/")
    assert ">a</a>" in terms.body_html and ">b</a>" not in terms.body_html
    assert ">b</a>" in equations.body_html and ">a</a>" not in equations.body_html


def test_the_opener_comes_first_and_lists_the_pages() -> None:
    page = make_page(terms=[make_entry("a")], named_equations=[make_entry("b")])
    opener, terms, equations = make_glossary_pages([page])
    assert (opener.title, opener.url) == ("Glossary", "glossary/")
    assert opener.chapters == [terms, equations]


def test_a_kind_without_entries_has_no_page() -> None:
    opener, only = make_glossary_pages([make_page(named_equations=[make_entry("a")])])
    assert only.title == "Equations"
    assert opener.chapters == [only]


def test_a_summary_counts_the_entries() -> None:
    one = make_page(terms=[make_entry("a")])
    two = make_page(named_equations=[make_entry("a"), make_entry("b")])
    assert make_glossary_pages([one])[1].summary == "1 term defined in this book."
    assert make_glossary_pages([two])[1].summary == "2 equations named in this book."


def test_an_entry_links_to_its_place() -> None:
    _, terms = make_glossary_pages([make_page(terms=[make_entry("a")])])
    assert '<a href="../../part/page/#a">a</a>' in terms.body_html
    assert "Here, A chapter" in terms.body_html


def test_an_entry_shows_no_definition() -> None:
    page = make_page("<p>A spray of hadrons. \\glossary{Jet}</p>")
    collect_terms(page)
    _, terms = make_glossary_pages([page])
    assert "spray" not in terms.body_html


def test_a_name_is_escaped_on_the_page() -> None:
    _, terms = make_glossary_pages([make_page(terms=[make_entry("R&D")])])
    assert ">R&amp;D</a>" in terms.body_html


def test_a_name_used_twice_fails() -> None:
    first = make_page(terms=[make_entry("Jet")], source_path=Path("one.md"))
    second = make_page(terms=[make_entry("jet")], source_path=Path("two.md"))
    with pytest.raises(BuildError, match=r"two\.md: glossary entry jet .* one\.md"):
        make_glossary_pages([first, second])


def test_the_same_name_may_be_a_term_and_an_equation() -> None:
    page = make_page(terms=[make_entry("Jet")], named_equations=[make_entry("Jet")])
    assert len(make_glossary_pages([page])) == 3


@pytest.mark.parametrize("url", ["glossary/", "glossary/terms/"])
def test_a_page_at_a_glossary_address_fails(url: str) -> None:
    taken = make_page(url=url, terms=[make_entry("a")])
    with pytest.raises(BuildError, match=f"needs the address {url}"):
        make_glossary_pages([taken])


@pytest.fixture
def site_dir(project_dir: Path) -> Path:
    return build_book(project_dir).site_dir


def test_the_pages_are_written_with_their_entries(site_dir: Path) -> None:
    terms = page_text(site_dir, "glossary/terms")
    assert '<a href="../../methods/basics/#definition-1-1">Term</a>' in terms
    assert ">Prose term</a>" in terms
    equations = page_text(site_dir, "glossary/equations")
    assert '<a href="../../methods/basics/#mjx-eqn:eq:one">Unit value</a>' in equations


def test_the_opener_links_to_each_page(site_dir: Path) -> None:
    opener = page_text(site_dir, "glossary")
    assert '<a href="../glossary/terms/">' in opener
    assert '<a href="../glossary/equations/">' in opener
    assert "2 terms defined in this book." in opener
    assert "1 equation named in this book." in opener


def test_a_page_links_back_to_the_opener(site_dir: Path) -> None:
    terms = page_text(site_dir, "glossary/terms")
    assert (
        '<p class="chapter-kicker"><a href="../../glossary/">Glossary</a></p>' in terms
    )
    assert "chapter-kicker" not in page_text(site_dir, "glossary")


def test_the_sidebar_lists_each_page(site_dir: Path) -> None:
    basics = page_text(site_dir, "methods/basics")
    assert 'class="toc-part-link" href="../../glossary/"' in basics
    assert '<a href="../../glossary/terms/"><span class="toc-title">Terms' in basics
    assert (
        '<a href="../../glossary/equations/"><span class="toc-title">Equations'
        in basics
    )


def test_the_sidebar_marks_the_current_page(site_dir: Path) -> None:
    terms = page_text(site_dir, "glossary/terms")
    assert '<li class="unnumbered active"><a href="../../glossary/terms/">' in terms
    assert '<li class="unnumbered"><a href="../../glossary/equations/">' in terms
    opener = page_text(site_dir, "glossary")
    assert 'class="toc-part-link active" href="../glossary/"' in opener


def test_the_contents_list_each_page(site_dir: Path) -> None:
    home = page_text(site_dir, "")
    assert 'class="contents-part-link" href="./glossary/"' in home
    assert '<a href="./glossary/terms/">' in home
    assert '<a href="./glossary/equations/">' in home


def test_the_pages_come_last_in_reading_order(site_dir: Path) -> None:
    assert '<a class="pagenav-next" href="../../../glossary/">' in page_text(
        site_dir, "methods/split/second"
    )
    opener = page_text(site_dir, "glossary")
    assert '<a class="pagenav-prev" href="../methods/split/second/">' in opener
    assert '<a class="pagenav-next" href="../glossary/terms/">' in opener
    terms = page_text(site_dir, "glossary/terms")
    assert '<a class="pagenav-prev" href="../../glossary/">' in terms
    assert '<a class="pagenav-next" href="../../glossary/equations/">' in terms
    equations = page_text(site_dir, "glossary/equations")
    assert '<a class="pagenav-prev" href="../../glossary/terms/">' in equations
    assert "pagenav-next" not in equations


def test_a_glossary_page_has_no_edit_link(site_dir: Path) -> None:
    assert "Edit this page" not in page_text(site_dir, "glossary/terms")
    assert "Edit this page" in page_text(site_dir, "methods/basics")


def test_search_finds_the_pages(site_dir: Path) -> None:
    entries = json.loads((site_dir / "search.json").read_text(encoding="utf-8"))
    assert {entry["page"] for entry in entries} >= {"Terms", "Equations"}


def test_a_kind_without_tags_stays_out_of_the_book(project_dir: Path) -> None:
    path = project_dir / "book" / "methods" / "basics.md"
    text = path.read_text(encoding="utf-8").replace(" \\glossary{Unit value}", "")
    path.write_text(text, encoding="utf-8")
    site_dir = build_book(project_dir).site_dir
    assert (site_dir / "glossary" / "terms" / "index.html").is_file()
    assert not (site_dir / "glossary" / "equations").exists()
    assert "glossary/equations" not in page_text(site_dir, "methods/basics")


def test_the_glossary_can_be_turned_off(project_dir: Path) -> None:
    add_to_config(project_dir, "\nglossary: false\n")
    result = build_book(project_dir)
    assert not (result.site_dir / "glossary").exists()
    basics = page_text(result.site_dir, "methods/basics")
    assert "glossary/" not in basics
    assert "\\glossary" not in basics


def test_a_book_without_tags_has_no_glossary(plain_project_dir: Path) -> None:
    for path in (plain_project_dir / "book").rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        text = text.replace(" \\glossary{Unit value}", "")
        text = text.replace("    \\glossary\n", "")
        text = text.replace(
            "A prose term is defined in a sentence. \\glossary{Prose term}", ""
        )
        path.write_text(text, encoding="utf-8")
    site_dir = build_book(plain_project_dir).site_dir
    assert not (site_dir / "glossary").exists()
    assert "glossary" not in page_text(site_dir, "")
