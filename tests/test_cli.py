"""Tests for the ``guidebook`` command."""

import subprocess
import sys
from pathlib import Path

import pytest

from guidebook import __version__
from guidebook.cli import main


def add_uncited_reference(project_dir: Path) -> None:
    path = project_dir / "book" / "methods" / "index.md"
    text = path.read_text(encoding="utf-8")
    references = "title: Methods\nreferences:\n  unused: A paper.\n"
    path.write_text(text.replace("title: Methods\n", references), encoding="utf-8")


def test_build_reports_what_it_wrote(
    project_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["build", str(project_dir)]) == 0
    output = capsys.readouterr().out
    assert "built 10 pages (2 chapters) into" in output
    assert str(project_dir / "site") in output


def test_build_lists_the_overrides_in_force(
    project_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["build", str(project_dir)])
    assert "overrides: theme/static/favicon.svg" in capsys.readouterr().out


def test_build_prints_no_overrides_line_without_a_theme(
    plain_project_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(["build", str(plain_project_dir)])
    assert "overrides:" not in capsys.readouterr().out


def test_the_project_defaults_to_the_current_directory(
    project_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(project_dir)
    assert main(["build"]) == 0
    assert (project_dir / "site" / "index.html").is_file()


def test_site_dir_chooses_the_output(project_dir: Path, tmp_path: Path) -> None:
    public_dir = tmp_path / "public"
    assert main(["build", str(project_dir), "--site-dir", str(public_dir)]) == 0
    assert (public_dir / "index.html").is_file()


def test_warnings_are_fatal(
    project_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    add_uncited_reference(project_dir)
    assert main(["build", str(project_dir)]) == 1
    error_output = capsys.readouterr().err
    assert "warning: " in error_output
    assert "references never cited: unused" in error_output
    assert "warnings are fatal" in error_output


def test_allow_warnings_lets_them_pass(
    project_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    add_uncited_reference(project_dir)
    assert main(["build", str(project_dir), "--allow-warnings"]) == 0
    assert "references never cited" in capsys.readouterr().err


def test_a_build_error_prints_and_returns_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["build", str(tmp_path)]) == 1
    assert "error: no book.yaml in" in capsys.readouterr().err


def test_version_prints_the_package_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"guidebook {__version__}"


def test_a_command_is_required(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main([])
    assert exit_info.value.code == 2
    assert "build" in capsys.readouterr().err


def test_the_module_runs_the_same_command(project_dir: Path) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "guidebook", "build", str(project_dir)],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert (project_dir / "site" / "index.html").is_file()
