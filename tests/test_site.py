"""Tests that build the sample book from start to finish."""

import json
import os
import re
from importlib import resources
from pathlib import Path

import pytest

from guidebook import BuildError, BuildResult, build_book
from guidebook.equations import MATHJAX_URL
from guidebook.safe_paths import STAMP_NAME
from guidebook.site import read_traversable

PACKAGE_TEMPLATES = [
    "base.html",
    "chapter.html",
    "home.html",
    "part.html",
    "section.html",
]
PACKAGE_STATIC = ["book.css", "book.js", "export.js", "favicon.svg"]


def page_text(site_dir: Path, url: str) -> str:
    return (site_dir / url / "index.html").read_text(encoding="utf-8")


def add_to_config(project_dir: Path, text: str) -> None:
    config_path = project_dir / "book.yaml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8") + text, encoding="utf-8"
    )


def body_tag(page_html: str) -> str:
    match = re.search(r"<body[^>]*>", page_html)
    assert match
    return match.group(0)


@pytest.fixture
def site_dir(project_dir: Path) -> Path:
    return build_book(project_dir).site_dir


def test_the_result_counts_what_was_written(project_dir: Path) -> None:
    result = build_book(project_dir)
    assert isinstance(result, BuildResult)
    assert result.site_dir == project_dir / "site"
    assert result.page_count == 6
    assert result.chapter_count == 2
    assert result.warnings == []


def test_every_page_has_its_file(site_dir: Path) -> None:
    for url in (
        "",
        "methods",
        "methods/basics",
        "methods/split",
        "methods/split/first",
        "methods/split/second",
    ):
        assert (site_dir / url / "index.html").is_file()


def test_the_site_has_its_supporting_files(site_dir: Path) -> None:
    assert (site_dir / ".nojekyll").read_bytes() == b""
    assert (site_dir / STAMP_NAME).is_file()
    assert "highlight" in (site_dir / "static" / "pygments.css").read_text(
        encoding="utf-8"
    )
    assert (site_dir / "static" / "book.js").is_file()


def test_numbers_run_through_a_chapter_and_its_section_pages(site_dir: Path) -> None:
    assert "Figure 1.1" in page_text(site_dir, "methods/basics")
    assert "Figure 2.1" in page_text(site_dir, "methods/split/first")
    assert "Figure 2.2" in page_text(site_dir, "methods/split/second")


def test_equations_carry_their_offset_to_the_next_page(site_dir: Path) -> None:
    assert "data-equation-offset" not in body_tag(
        page_text(site_dir, "methods/split/first")
    )
    assert 'data-equation-offset="1"' in body_tag(
        page_text(site_dir, "methods/split/second")
    )


def test_an_eqref_reaches_other_pages_and_stays_on_its_own(site_dir: Path) -> None:
    second = page_text(site_dir, "methods/split/second")
    assert r"\href{../../../methods/split/first/#mjx-eqn:eq:first}" in second
    assert r"{\text{(2.1)}}" in second
    assert r"\href{../../../methods/basics/#mjx-eqn:eq:one}" in second
    assert r"\eqref{eq:second}" in second


def test_an_eqref_with_no_equation_stops_the_build(project_dir: Path) -> None:
    path = project_dir / "book" / "methods" / "split" / "second.md"
    text = path.read_text(encoding="utf-8").replace("eq:first", "eq:missing")
    path.write_text(text, encoding="utf-8")
    with pytest.raises(BuildError, match=r"\\eqref\{eq:missing\} matches no"):
        build_book(project_dir)


def test_links_and_citations_resolve(site_dir: Path) -> None:
    basics = page_text(site_dir, "methods/basics")
    assert 'href="../../methods/split/"' in basics
    assert '<a class="cite" href="#ref-first-paper">1</a>' in basics


def test_search_holds_every_page(site_dir: Path) -> None:
    entries = json.loads((site_dir / "search.json").read_text(encoding="utf-8"))
    assert {entry["page"] for entry in entries} >= {
        "Sample Book",
        "1. Basics",
        "2.2 Second section",
    }


def test_macros_are_written_into_the_mathjax_configuration(site_dir: Path) -> None:
    home = page_text(site_dir, "")
    assert 'dd: "\\\\mathrm{d}",\n' in home
    assert 'vec: ["\\\\boldsymbol{#1}", 1]\n' in home


def test_a_book_without_macros_defines_none(plain_project_dir: Path) -> None:
    config_path = plain_project_dir / "book.yaml"
    text = config_path.read_text(encoding="utf-8")
    start, end = text.index("mathjax_macros"), text.index("parts:")
    config_path.write_text(text[:start] + text[end:], encoding="utf-8")
    site_dir = build_book(plain_project_dir).site_dir
    assert "macros:" not in page_text(site_dir, "")


def test_mathjax_comes_from_the_version_the_count_follows(site_dir: Path) -> None:
    assert f'<script defer src="{MATHJAX_URL}"></script>' in page_text(site_dir, "")


def test_tables_enlarge_by_default(site_dir: Path) -> None:
    assert "data-enlarge-tables" not in page_text(site_dir, "")
    book_js = (site_dir / "static" / "book.js").read_text(encoding="utf-8")
    assert 'getAttribute("data-enlarge-tables") !== "false"' in book_js


def test_a_book_can_turn_table_enlarging_off(project_dir: Path) -> None:
    add_to_config(project_dir, "\nenlarge_tables: false\n")
    site_dir = build_book(project_dir).site_dir
    assert 'data-enlarge-tables="false"' in body_tag(page_text(site_dir, "methods"))


def test_export_menus_are_on_by_default(site_dir: Path) -> None:
    assert '<script src="./static/export.js" defer></script>' in page_text(site_dir, "")
    assert (site_dir / "static" / "export.js").is_file()


def test_a_book_can_turn_export_menus_off(project_dir: Path) -> None:
    add_to_config(project_dir, "\nexport_menus: false\n")
    site_dir = build_book(project_dir).site_dir
    assert "export.js" not in page_text(site_dir, "methods")


def test_source_and_edit_links_follow_the_config(site_dir: Path) -> None:
    basics = page_text(site_dir, "methods/basics")
    assert '<a href="https://example.org/sample-repo" class="external"' in basics
    assert "Source on ExampleHost" in basics
    edit_url = "https://example.org/sample-repo/edit/methods/basics.md"
    assert f'<a href="{edit_url}" class="external"' in basics


def test_source_and_edit_links_are_left_out_when_unset(project_dir: Path) -> None:
    config_path = project_dir / "book.yaml"
    lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
    kept = [line for line in lines if not line.startswith(("repo", "edit_url"))]
    config_path.write_text("".join(kept), encoding="utf-8")
    home = page_text(build_book(project_dir).site_dir, "")
    assert "sidebar-foot" not in home
    assert "Edit this page" not in home


def test_an_override_extends_the_package_template(site_dir: Path) -> None:
    home = page_text(site_dir, "")
    assert '<link rel="stylesheet" href="./static/sample.css">' in home
    assert '<a class="brand"' in home


def test_an_override_replaces_a_template_whole(project_dir: Path) -> None:
    templates_dir = project_dir / "theme" / "templates"
    (templates_dir / "home.html").write_text("<p>{{ book.title }}</p>")
    site_dir = build_book(project_dir).site_dir
    assert (site_dir / "index.html").read_text(encoding="utf-8") == "<p>Sample Book</p>"
    assert "<title>Part I: Methods" in page_text(site_dir, "methods")


def test_a_book_static_file_is_added_and_one_replaced(site_dir: Path) -> None:
    assert (site_dir / "static" / "sample.css").is_file()
    assert "sample" in (site_dir / "static" / "favicon.svg").read_text(encoding="utf-8")
    assert "--ink" in (site_dir / "static" / "book.css").read_text(encoding="utf-8")


def test_a_book_can_supply_its_own_code_colours(project_dir: Path) -> None:
    (project_dir / "theme" / "static" / "pygments.css").write_text("/* own */")
    site_dir = build_book(project_dir).site_dir
    assert (site_dir / "static" / "pygments.css").read_text(
        encoding="utf-8"
    ) == "/* own */"


def test_code_colours_come_from_the_config(project_dir: Path) -> None:
    site_dir = build_book(project_dir).site_dir
    default_css = (site_dir / "static" / "pygments.css").read_text(encoding="utf-8")
    add_to_config(project_dir, "\npygments_light: bw\npygments_dark: monokai\n")
    build_book(project_dir)
    assert (site_dir / "static" / "pygments.css").read_text(
        encoding="utf-8"
    ) != default_css


def test_an_unknown_colour_style_stops_the_build(project_dir: Path) -> None:
    add_to_config(project_dir, "\npygments_dark: no-such-style\n")
    with pytest.raises(BuildError, match="book.yaml: .*no-such-style"):
        build_book(project_dir)


def test_the_result_lists_the_overrides_in_force(project_dir: Path) -> None:
    assert build_book(project_dir).overrides == [
        "theme/static/favicon.svg",
        "theme/static/sample.css",
        "theme/templates/base.html",
    ]


def test_a_book_without_a_theme_has_no_overrides(plain_project_dir: Path) -> None:
    result = build_book(plain_project_dir)
    assert result.overrides == []
    assert "sample.css" not in page_text(result.site_dir, "")


@pytest.mark.parametrize(
    "template",
    ["{{ page.no_such_field }}", "{% if %}", '{% extends "no-such-template.html" %}'],
)
def test_a_template_mistake_stops_the_build(project_dir: Path, template: str) -> None:
    (project_dir / "theme" / "templates" / "home.html").write_text(template)
    with pytest.raises(BuildError, match="template error"):
        build_book(project_dir)


def test_a_failed_build_leaves_the_site_as_it_was(project_dir: Path) -> None:
    site_dir = build_book(project_dir).site_dir
    home_before = page_text(site_dir, "")
    (project_dir / "theme" / "templates" / "part.html").write_text("{{ missing }}")
    with pytest.raises(BuildError):
        build_book(project_dir)
    assert page_text(site_dir, "") == home_before
    assert (site_dir / "methods" / "index.html").is_file()


def test_a_rebuild_drops_a_removed_part(project_dir: Path) -> None:
    site_dir = build_book(project_dir).site_dir
    (site_dir / "search.json").write_text("stale")
    config_path = project_dir / "book.yaml"
    text = config_path.read_text(encoding="utf-8")
    config_path.write_text(text[: text.index("parts:")], encoding="utf-8")
    build_book(project_dir)
    assert not (site_dir / "methods").exists()
    assert (site_dir / "search.json").read_text(encoding="utf-8") != "stale"


def test_the_site_can_go_to_another_directory(
    project_dir: Path, tmp_path: Path
) -> None:
    public_dir = tmp_path.resolve() / "public"
    result = build_book(project_dir, public_dir)
    assert result.site_dir == public_dir
    assert (public_dir / "index.html").is_file()
    assert not (project_dir / "site").exists()


def test_a_full_folder_is_not_used_as_a_site(project_dir: Path, tmp_path: Path) -> None:
    other_dir = tmp_path / "documents"
    other_dir.mkdir()
    (other_dir / "thesis.tex").write_text("years of work")
    with pytest.raises(BuildError, match="is not empty"):
        build_book(project_dir, other_dir)
    assert (other_dir / "thesis.tex").read_text(encoding="utf-8") == "years of work"


def test_a_link_to_a_full_folder_is_not_used_as_a_site(
    project_dir: Path, tmp_path: Path
) -> None:
    other_dir = tmp_path / "documents"
    other_dir.mkdir()
    (other_dir / "thesis.tex").write_text("years of work")
    try:
        os.symlink(other_dir, project_dir / "site")
    except OSError:
        pytest.skip("this system cannot make symbolic links")
    with pytest.raises(BuildError, match="is not empty"):
        build_book(project_dir)
    assert (other_dir / "thesis.tex").read_text(encoding="utf-8") == "years of work"


def test_the_project_directory_is_not_used_as_a_site(project_dir: Path) -> None:
    with pytest.raises(BuildError, match="it holds"):
        build_book(project_dir, project_dir)


def test_the_date_comes_from_the_source_date_epoch(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1577836800")
    site_dir = build_book(project_dir).site_dir
    assert "Revised January 2020" in page_text(site_dir, "")
    assert "revised January 2020" in page_text(site_dir, "")


@pytest.mark.parametrize("value", ["", "soon", "-1", "1.5", "9" * 40])
def test_a_malformed_source_date_epoch_stops_the_build(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", value)
    with pytest.raises(BuildError, match="SOURCE_DATE_EPOCH"):
        build_book(project_dir)


def test_two_builds_give_the_same_bytes(
    project_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1577836800")
    first_dir = build_book(project_dir, tmp_path / "first").site_dir
    second_dir = build_book(project_dir, tmp_path / "second").site_dir
    first = {p.relative_to(first_dir): p.read_bytes() for p in first_dir.rglob("*.*")}
    second = {
        p.relative_to(second_dir): p.read_bytes() for p in second_dir.rglob("*.*")
    }
    assert first == second


def test_output_uses_unix_line_endings(project_dir: Path) -> None:
    site_dir = build_book(project_dir).site_dir
    for pattern in ("*.html", "*.css", "*.js", "*.json", "*.svg"):
        for path in site_dir.rglob(pattern):
            assert b"\r" not in path.read_bytes(), path


def test_windows_line_endings_in_a_source_change_nothing(project_dir: Path) -> None:
    path = project_dir / "book" / "methods" / "basics.md"
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    site_dir = build_book(project_dir).site_dir
    assert b"\r" not in (site_dir / "methods" / "basics" / "index.html").read_bytes()


def test_the_package_holds_its_templates_and_static_files() -> None:
    package_dir = resources.files("guidebook")
    templates = read_traversable(package_dir / "templates", "templates")
    static = read_traversable(package_dir / "static", "static")
    assert sorted(templates) == [f"templates/{name}" for name in PACKAGE_TEMPLATES]
    assert sorted(static) == [f"static/{name}" for name in PACKAGE_STATIC]
