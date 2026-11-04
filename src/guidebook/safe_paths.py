"""Replace a site directory's contents without touching anything else.

A site directory carries a stamp, ``.guidebook-stamp.json``, naming the top-level
entries the last build wrote there. A rebuild removes those entries whole and leaves
every other top-level entry alone. A folder that is not empty and has no stamp stops
the build, which is what keeps a mistyped ``--site-dir`` from costing anything.

The stamp says that a build wrote a folder, not which book did, and it holds no record
of an entry's contents: a file added inside a listed entry is removed with it, which
is how system files and sync conflicts there go away. A link in place of the site
directory is judged by its target. Stamps guard against mistakes; anyone who can write
to a directory can also edit its stamp.
"""

import json
import os
import re
import shutil
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from guidebook import __version__
from guidebook.errors import BuildError

STAMP_NAME = ".guidebook-stamp.json"

_PRODUCER = "guidebook"
_TEMPORARY_STAMP_NAME = f"{STAMP_NAME}.tmp"

# One path component on every system, an allow-list because a name is rejected, never
# repaired. The optional leading dot admits .nojekyll; a dot alone or .. never matches.
_PLAIN_NAME_PATTERN = re.compile(r"\.?[A-Za-z0-9_][A-Za-z0-9_.-]*")


def require_path_component(name: Any, *, what: str) -> str:
    """Return `name` if it is one path component.

    Raises
    ------
    BuildError
        If `name` is anything but ASCII letters, digits, ``_``, ``-`` and ``.``,
        starting with a letter, digit or ``_`` after one optional leading dot.
    """
    if not isinstance(name, str) or not _PLAIN_NAME_PATTERN.fullmatch(name):
        raise BuildError(f"{what} must be one plain path component, not {name!r}")
    return name


def require_site_dir(
    site_dir: Path, project_dir: Path, source_dirs: Iterable[Path]
) -> None:
    """Refuse a site directory that holds, or lies in, something a build must keep.

    Parameters
    ----------
    site_dir : Path
        The resolved site directory.
    project_dir : Path
        The resolved project directory.
    source_dirs : iterable of Path
        The directories holding the book's sources.

    Raises
    ------
    BuildError
        If `site_dir` is a filesystem root, the home or project directory or an
        ancestor of one, lies in a source directory, or is not a directory.
    """
    if site_dir == Path(site_dir.anchor):
        raise BuildError(f"refusing to build into the filesystem root {site_dir}")
    for protected_dir in (_home_dir(), project_dir):
        if protected_dir is not None and protected_dir.is_relative_to(site_dir):
            raise BuildError(
                f"refusing to build into {site_dir}: it holds {protected_dir}"
            )
    for source_dir in source_dirs:
        if site_dir.is_relative_to(source_dir):
            raise BuildError(
                f"refusing to build into {site_dir}: it is in {source_dir}"
            )
    if site_dir.exists() and not site_dir.is_dir():
        raise BuildError(f"{site_dir} is not a directory")


def replace_site(site_dir: Path, files: Mapping[str, bytes]) -> None:
    """Replace what the last build left in `site_dir` with `files`.

    The stamp is rewritten to cover the old and new entries before anything is
    removed, so a build killed at any point leaves every entry it wrote listed.

    Parameters
    ----------
    site_dir : Path
        The resolved site directory, already screened by :func:`require_site_dir`.
    files : Mapping[str, bytes]
        The content of each file, by its POSIX path relative to `site_dir`.

    Raises
    ------
    BuildError
        If `site_dir` is not empty and has no stamp, if its stamp is not one this
        program wrote, if the build needs a name the stamp does not list, or if a
        top-level name in `files` is not a plain path component.
    """
    stamped_entries = _stamped_entries(site_dir)
    entries = sorted(
        require_path_component(name.split("/", 1)[0], what="A top-level site entry")
        for name in {name.split("/", 1)[0] for name in files}
    )
    unlisted_entries = [
        name
        for name in entries
        if name not in stamped_entries and _is_occupied(site_dir / name)
    ]
    if unlisted_entries:
        raise BuildError(
            f"{site_dir} holds {', '.join(unlisted_entries)}, which the build needs "
            "and did not write; move it out of the way"
        )
    stale_paths = _checked_removals(site_dir, stamped_entries)

    site_dir.mkdir(parents=True, exist_ok=True)
    _write_stamp(site_dir, sorted({*stamped_entries, *entries}))
    for path in stale_paths:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    for name, content in files.items():
        path = site_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    _write_stamp(site_dir, entries)


def _home_dir() -> Path | None:
    try:
        return Path.home().resolve()
    except RuntimeError:  # No home directory can be determined.
        return None


def _is_occupied(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def _stamped_entries(site_dir: Path) -> list[str]:
    """Return the entries the last build left in `site_dir`, none in a new folder."""
    if not site_dir.exists():
        return []
    entries = _read_stamp(site_dir)
    if entries is not None:
        return entries
    if any(site_dir.iterdir()):
        raise BuildError(
            f"{site_dir} is not empty and has no {STAMP_NAME}, so it is not a site "
            "this program wrote; delete it or choose another site directory"
        )
    return []


def _read_stamp(site_dir: Path) -> list[str] | None:
    stamp_path = site_dir / STAMP_NAME
    if not _is_occupied(stamp_path):
        return None
    if stamp_path.is_symlink() or not stamp_path.is_file():
        raise BuildError(f"{stamp_path} is not a stamp this program wrote")
    try:
        record = json.loads(stamp_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise BuildError(f"{stamp_path} is not a stamp this program wrote") from None
    if (
        not isinstance(record, dict)
        or record.get("producer") != _PRODUCER
        or not isinstance(record.get("entries"), list)
    ):
        raise BuildError(f"{stamp_path} is not a stamp this program wrote")
    return [
        require_path_component(name, what=f"An entry of {stamp_path}")
        for name in record["entries"]
    ]


def _write_stamp(site_dir: Path, entries: list[str]) -> None:
    record = {"producer": _PRODUCER, "version": __version__, "entries": entries}
    temporary_path = site_dir / _TEMPORARY_STAMP_NAME
    temporary_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary_path, site_dir / STAMP_NAME)


def _checked_removals(site_dir: Path, entries: Iterable[str]) -> list[Path]:
    """Return the paths of `entries` still present, each checked before any is removed.

    Each path is one plain name inside `site_dir`, so only a link can lead out of it.
    Directory trees are later removed with :func:`shutil.rmtree`, which deletes the
    symbolic links inside a tree rather than following them and refuses a Windows
    junction.
    """
    paths = []
    for name in entries:
        path = site_dir / name
        if path.is_symlink():
            raise BuildError(f"refusing to remove {path}: it is a symbolic link")
        if not path.exists():
            continue
        paths.append(path)
    return paths
