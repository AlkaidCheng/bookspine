"""Tests for reading and checking ``book.yaml``."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from guidebook.config import (
    DEFAULT_PYGMENTS_DARK,
    DEFAULT_PYGMENTS_LIGHT,
    ChapterConfig,
    Project,
    load_config,
)
from guidebook.errors import BuildError


def config_path_with(tmp_path: Path, **keys: Any) -> Path:
    config_path = tmp_path / "book.yaml"
    record = {"title": "A title", "author": "An author", **keys}
    config_path.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")
    return config_path


def test_defaults_fill_every_optional_key(tmp_path: Path) -> None:
    config = load_config(config_path_with(tmp_path))
    assert config.title == "A title"
    assert config.subtitle == ""
    assert config.repo == ""
    assert config.parts == ()
    assert config.enlarge_tables is True
    assert config.export_menus is True
    assert config.wrap_code is True
    assert config.help_page == ""
    assert config.mathjax_macros == {}
    assert config.pygments_light == DEFAULT_PYGMENTS_LIGHT
    assert config.pygments_dark == DEFAULT_PYGMENTS_DARK


def test_book_keys_override_the_defaults(tmp_path: Path) -> None:
    config = load_config(
        config_path_with(
            tmp_path,
            enlarge_tables=False,
            pygments_light="default",
            help_page="help.md",
            repo="https://example.org/repo",
            repo_host="ExampleHost",
        )
    )
    assert config.enlarge_tables is False
    assert config.pygments_light == "default"
    assert config.help_page == "help.md"
    assert config.repo_host == "ExampleHost"


def test_a_chapter_is_a_file_or_a_directory_of_sections(tmp_path: Path) -> None:
    parts = [
        {
            "dir": "part/",
            "title": "A part",
            "chapters": ["one.md", {"dir": "two", "sections": ["a.md", "b.md"]}],
        }
    ]
    config = load_config(config_path_with(tmp_path, parts=parts))
    (part,) = config.parts
    assert part.dir_name == "part"
    assert part.chapters == (
        ChapterConfig(dir_name="one", source_name="one.md"),
        ChapterConfig(
            dir_name="two",
            source_name="two/index.md",
            section_names=("a.md", "b.md"),
        ),
    )


def test_macros_keep_their_order_and_definitions(tmp_path: Path) -> None:
    macros = {"zz": r"\mathrm{z}", "aa": [r"\boldsymbol{#1}", 1]}
    config = load_config(config_path_with(tmp_path, mathjax_macros=macros))
    assert list(config.mathjax_macros.items()) == list(macros.items())


@pytest.mark.parametrize(
    ("keys", "message"),
    [
        ({"enlarge_table": False}, "unknown key: enlarge_table"),
        ({"title": ""}, "needs a title"),
        ({"author": ""}, "needs a author"),
        ({"subtitle": 3}, "subtitle must be text"),
        ({"help_page": 3}, "help_page must be text"),
        ({"help_page": ""}, "one plain path component"),
        ({"help_page": "../help.md"}, "one plain path component"),
        ({"help_page": "part/help.md"}, "one plain path component"),
        ({"repo": "https://example.org"}, "repo needs a repo_host"),
        ({"enlarge_tables": "no"}, "enlarge_tables must be true or false"),
        ({"export_menus": 1}, "export_menus must be true or false"),
        ({"wrap_code": "yes"}, "wrap_code must be true or false"),
        ({"mathjax_macros": ["dd"]}, "mathjax_macros must be a mapping"),
        ({"mathjax_macros": {"d d": "x"}}, "not a TeX macro name"),
        ({"mathjax_macros": {"dd": 3}}, "macro dd must be"),
        ({"mathjax_macros": {"dd": ["x"]}}, "macro dd must be"),
        ({"mathjax_macros": {"dd": ["x", True]}}, "macro dd must be"),
        ({"parts": "hep"}, "parts must be a list"),
        ({"parts": [{"title": "No dir"}]}, "every part needs a dir"),
        ({"parts": [{"dir": "a", "colour": "red"}]}, "unknown key: colour"),
        ({"parts": [{"dir": "a", "chapters": "one.md"}]}, "must be a list"),
        ({"parts": [{"dir": "../a"}]}, "one plain path component"),
        ({"parts": [{"dir": "a b"}]}, "one plain path component"),
        ({"parts": [{"dir": "-a"}]}, "one plain path component"),
        (
            {"parts": [{"dir": "a", "chapters": ["../b.md"]}]},
            "one plain path component",
        ),
        ({"parts": [{"dir": "a", "chapters": [3]}]}, "a file name or has a dir"),
        (
            {"parts": [{"dir": "a", "chapters": [{"dir": "b", "pages": []}]}]},
            "unknown key: pages",
        ),
        (
            {"parts": [{"dir": "a", "chapters": [{"dir": "b", "sections": "c.md"}]}]},
            "must be a list",
        ),
        (
            {"parts": [{"dir": "a", "chapters": [{"dir": "b", "sections": ["../c"]}]}]},
            "one plain path component",
        ),
    ],
)
def test_invalid_keys_fail(tmp_path: Path, keys: dict[str, Any], message: str) -> None:
    with pytest.raises(BuildError, match=message):
        load_config(config_path_with(tmp_path, **keys))


def test_missing_file_fails(tmp_path: Path) -> None:
    with pytest.raises(BuildError, match="no book.yaml in"):
        load_config(tmp_path / "book.yaml")


def test_invalid_yaml_fails(tmp_path: Path) -> None:
    config_path = tmp_path / "book.yaml"
    config_path.write_text("title: [", encoding="utf-8")
    with pytest.raises(BuildError, match="invalid YAML"):
        load_config(config_path)


def test_a_file_that_is_no_mapping_fails(tmp_path: Path) -> None:
    config_path = tmp_path / "book.yaml"
    config_path.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(BuildError, match="must be a mapping"):
        load_config(config_path)


def test_project_finds_its_files_from_the_directory(tmp_path: Path) -> None:
    project = Project.locate(tmp_path)
    resolved_dir = tmp_path.resolve()
    assert project.project_dir == resolved_dir
    assert project.site_dir == resolved_dir / "site"
    assert project.config_path == resolved_dir / "book.yaml"
    assert project.book_dir == resolved_dir / "book"
    assert project.templates_dir == resolved_dir / "theme" / "templates"
    assert project.static_dir == resolved_dir / "theme" / "static"


def test_project_takes_another_site_directory(tmp_path: Path) -> None:
    project = Project.locate(tmp_path, tmp_path / "public")
    assert project.site_dir == tmp_path.resolve() / "public"
