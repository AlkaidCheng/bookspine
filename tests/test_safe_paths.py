"""Tests for the site directory's screening and its stamp.

Every path here is under pytest's temporary directory; the home directory is replaced
by a stand-in where it matters.
"""

import json
import os
from pathlib import Path

import pytest

from guidebook import __version__
from guidebook.errors import BuildError
from guidebook.safe_paths import (
    STAMP_NAME,
    replace_site,
    require_path_component,
    require_site_dir,
)

FILES = {
    "index.html": b"home",
    "search.json": b"[]",
    "hep/index.html": b"part",
    "hep/chapter/index.html": b"chapter",
    "static/book.css": b"css",
}


def stamp_entries(site_dir: Path) -> list[str]:
    record = json.loads((site_dir / STAMP_NAME).read_text(encoding="utf-8"))
    entries: list[str] = record["entries"]
    return entries


def make_symlink(link_path: Path, target: Path) -> None:
    try:
        os.symlink(target, link_path)
    except OSError:
        pytest.skip("this system cannot make symbolic links")


@pytest.fixture
def site_dir(tmp_path: Path) -> Path:
    return tmp_path.resolve() / "project" / "site"


@pytest.fixture
def built_site_dir(site_dir: Path) -> Path:
    replace_site(site_dir, FILES)
    return site_dir


@pytest.mark.parametrize(
    "name", ["hep", "a.md", ".nojekyll", "event-generation.md", "a_b", "2026"]
)
def test_one_component_is_accepted(name: str) -> None:
    assert require_path_component(name, what="A name") == name


@pytest.mark.parametrize(
    "name",
    [
        "",
        ".",
        "..",
        "...",
        "a/b",
        "../a",
        "/etc",
        "a\\b",
        "C:",
        "a\x00b",
        "a b",
        " a",
        "a\n",
        "-x",
        "été",
        3,
        None,
    ],
)
def test_anything_else_is_refused(name: object) -> None:
    with pytest.raises(BuildError, match="must be one plain path component"):
        require_path_component(name, what="A name")


def test_the_site_directory_of_a_project_is_accepted(tmp_path: Path) -> None:
    project_dir = tmp_path.resolve()
    require_site_dir(project_dir / "site", project_dir, [project_dir / "book"])


def test_a_directory_beside_the_project_is_accepted(tmp_path: Path) -> None:
    root_dir = tmp_path.resolve()
    require_site_dir(root_dir / "public", root_dir / "project", [])


def test_the_filesystem_root_is_refused(tmp_path: Path) -> None:
    root_dir = Path(tmp_path.resolve().anchor)
    with pytest.raises(BuildError, match="filesystem root"):
        require_site_dir(root_dir, tmp_path.resolve(), [])


def test_the_project_directory_is_refused(tmp_path: Path) -> None:
    project_dir = tmp_path.resolve()
    with pytest.raises(BuildError, match="it holds"):
        require_site_dir(project_dir, project_dir, [])


def test_an_ancestor_of_the_project_is_refused(tmp_path: Path) -> None:
    project_dir = tmp_path.resolve() / "a" / "b"
    with pytest.raises(BuildError, match="it holds"):
        require_site_dir(tmp_path.resolve(), project_dir, [])


@pytest.mark.parametrize("site_name", ["home", "."])
def test_the_home_directory_and_its_ancestors_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, site_name: str
) -> None:
    root_dir = tmp_path.resolve()
    home_dir = root_dir / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home_dir))
    with pytest.raises(BuildError, match="it holds"):
        require_site_dir((root_dir / site_name).resolve(), root_dir / "x" / "y", [])


@pytest.mark.parametrize("site_name", ["book", "book/site"])
def test_a_directory_in_the_sources_is_refused(tmp_path: Path, site_name: str) -> None:
    project_dir = tmp_path.resolve()
    with pytest.raises(BuildError, match="it is in"):
        require_site_dir(project_dir / site_name, project_dir, [project_dir / "book"])


def test_a_file_is_refused_as_a_site_directory(tmp_path: Path) -> None:
    file_path = tmp_path.resolve() / "site"
    file_path.write_text("a file")
    with pytest.raises(BuildError, match="not a directory"):
        require_site_dir(file_path, tmp_path.resolve() / "project", [])


def test_a_new_folder_gets_the_files_and_a_stamp(built_site_dir: Path) -> None:
    assert (
        built_site_dir / "hep" / "chapter" / "index.html"
    ).read_bytes() == b"chapter"
    assert stamp_entries(built_site_dir) == [
        "hep",
        "index.html",
        "search.json",
        "static",
    ]


def test_the_stamp_names_its_producer_and_version(built_site_dir: Path) -> None:
    record = json.loads((built_site_dir / STAMP_NAME).read_text(encoding="utf-8"))
    assert record["producer"] == "guidebook"
    assert record["version"] == __version__


def test_an_empty_folder_needs_no_stamp(site_dir: Path) -> None:
    site_dir.mkdir(parents=True)
    replace_site(site_dir, FILES)
    assert (site_dir / "index.html").is_file()


def test_a_rebuild_removes_an_entry_it_no_longer_writes(built_site_dir: Path) -> None:
    files = {name: content for name, content in FILES.items() if "hep" not in name}
    replace_site(built_site_dir, files)
    assert not (built_site_dir / "hep").exists()
    assert "hep" not in stamp_entries(built_site_dir)


def test_a_rebuild_removes_a_stale_file_inside_an_entry(built_site_dir: Path) -> None:
    files = dict(FILES)
    del files["hep/chapter/index.html"]
    replace_site(built_site_dir, files)
    assert not (built_site_dir / "hep" / "chapter").exists()
    assert (built_site_dir / "hep" / "index.html").is_file()


def test_junk_inside_an_entry_goes_with_it(built_site_dir: Path) -> None:
    junk_path = built_site_dir / "static" / ".DS_Store"
    junk_path.write_text("junk")
    replace_site(built_site_dir, FILES)
    assert not junk_path.exists()


def test_an_unlisted_top_level_entry_is_left_alone(built_site_dir: Path) -> None:
    file_path = built_site_dir / "notes.pdf"
    folder_path = built_site_dir / "drafts" / "one.md"
    file_path.write_text("mine")
    folder_path.parent.mkdir()
    folder_path.write_text("mine")
    replace_site(built_site_dir, FILES)
    assert file_path.read_text() == "mine"
    assert folder_path.read_text() == "mine"
    assert "notes.pdf" not in stamp_entries(built_site_dir)


def test_a_top_level_name_the_stamp_could_not_hold_stops_the_build(
    built_site_dir: Path,
) -> None:
    with pytest.raises(BuildError, match="must be one plain path component"):
        replace_site(built_site_dir, {"my cover.png": b"png"})
    assert (built_site_dir / "index.html").read_bytes() == b"home"


def test_a_folder_without_a_stamp_stops_the_build(site_dir: Path) -> None:
    site_dir.mkdir(parents=True)
    keepsake_path = site_dir / "index.html"
    keepsake_path.write_text("not from a build")
    with pytest.raises(BuildError, match="no .guidebook-stamp.json"):
        replace_site(site_dir, FILES)
    assert keepsake_path.read_text() == "not from a build"
    assert sorted(path.name for path in site_dir.iterdir()) == ["index.html"]


def test_an_unlisted_entry_the_build_needs_stops_it(built_site_dir: Path) -> None:
    keepsake_path = built_site_dir / "guide" / "notes.md"
    keepsake_path.parent.mkdir()
    keepsake_path.write_text("mine")
    with pytest.raises(BuildError, match="holds guide, which the build needs"):
        replace_site(built_site_dir, {**FILES, "guide/index.html": b"part"})
    assert keepsake_path.read_text() == "mine"
    assert (built_site_dir / "index.html").read_bytes() == b"home"


@pytest.mark.parametrize(
    "stamp_text",
    [
        "not json",
        "[]",
        '{"producer": "other", "entries": []}',
        '{"producer": "guidebook"}',
        '{"producer": "guidebook", "entries": "hep"}',
    ],
)
def test_a_stamp_from_elsewhere_stops_the_build(
    built_site_dir: Path, stamp_text: str
) -> None:
    (built_site_dir / STAMP_NAME).write_text(stamp_text)
    with pytest.raises(BuildError, match="not a stamp this program wrote"):
        replace_site(built_site_dir, FILES)
    assert (built_site_dir / "hep" / "index.html").is_file()


@pytest.mark.parametrize("entry", ["..", "../other", "/etc", "a/b", ""])
def test_a_stamp_cannot_name_anything_outside_the_folder(
    built_site_dir: Path, entry: str
) -> None:
    stamp = {"producer": "guidebook", "entries": ["hep", entry]}
    (built_site_dir / STAMP_NAME).write_text(json.dumps(stamp))
    with pytest.raises(BuildError, match="must be one plain path component"):
        replace_site(built_site_dir, FILES)
    assert (built_site_dir / "hep" / "index.html").is_file()


def test_a_stamp_that_is_a_link_stops_the_build(
    built_site_dir: Path, tmp_path: Path
) -> None:
    other_path = tmp_path / "other.json"
    (built_site_dir / STAMP_NAME).replace(other_path)
    make_symlink(built_site_dir / STAMP_NAME, other_path)
    with pytest.raises(BuildError, match="not a stamp this program wrote"):
        replace_site(built_site_dir, FILES)


def test_a_listed_entry_that_is_a_link_is_refused(
    built_site_dir: Path, tmp_path: Path
) -> None:
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (outside_dir / "keep.txt").write_text("mine")
    hep_dir = built_site_dir / "hep"
    (hep_dir / "chapter" / "index.html").unlink()
    (hep_dir / "chapter").rmdir()
    (hep_dir / "index.html").unlink()
    hep_dir.rmdir()
    make_symlink(hep_dir, outside_dir)
    with pytest.raises(BuildError, match="symbolic link"):
        replace_site(built_site_dir, FILES)
    assert (outside_dir / "keep.txt").read_text() == "mine"
    assert (built_site_dir / "index.html").read_bytes() == b"home"


def test_a_link_inside_an_entry_is_removed_and_not_followed(
    built_site_dir: Path, tmp_path: Path
) -> None:
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (outside_dir / "keep.txt").write_text("mine")
    make_symlink(built_site_dir / "hep" / "link", outside_dir)
    replace_site(built_site_dir, FILES)
    assert (outside_dir / "keep.txt").read_text() == "mine"
    assert not (built_site_dir / "hep" / "link").exists()


def test_a_killed_build_leaves_everything_listed(
    built_site_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    written: list[Path] = []
    write_bytes = Path.write_bytes

    def write_then_die(path: Path, content: bytes) -> int:
        if written:
            raise KeyboardInterrupt
        written.append(path)
        return write_bytes(path, content)

    new_files = {"guide/index.html": b"new part", "index.html": b"new home"}
    with monkeypatch.context() as patch:
        patch.setattr(Path, "write_bytes", write_then_die)
        with pytest.raises(KeyboardInterrupt):
            replace_site(built_site_dir, new_files)

    assert stamp_entries(built_site_dir) == [
        "guide",
        "hep",
        "index.html",
        "search.json",
        "static",
    ]
    replace_site(built_site_dir, FILES)
    assert not (built_site_dir / "guide").exists()
    assert stamp_entries(built_site_dir) == [
        "hep",
        "index.html",
        "search.json",
        "static",
    ]
