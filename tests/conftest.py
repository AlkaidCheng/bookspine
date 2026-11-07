"""Shared fixtures: a private copy of a sample project for each test."""

import shutil
from pathlib import Path

import pytest

SAMPLE_BOOK_DIR = Path(__file__).parent / "sample_book"
SAMPLE_REFERENCE_DIR = Path(__file__).parent / "sample_reference"


def copy_project(source_dir: Path, copy_dir: Path) -> Path:
    shutil.copytree(
        source_dir, copy_dir, ignore=shutil.ignore_patterns("site", ".DS_Store")
    )
    return copy_dir


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Return a copy of the sample book that a test may change."""
    return copy_project(SAMPLE_BOOK_DIR, tmp_path.resolve() / "book-project")


@pytest.fixture
def reference_dir(tmp_path: Path) -> Path:
    """Return a copy of the sample reference site that a test may change."""
    return copy_project(SAMPLE_REFERENCE_DIR, tmp_path.resolve() / "reference-project")


@pytest.fixture
def plain_project_dir(project_dir: Path) -> Path:
    """Return a copy of the sample book without its theme overrides."""
    shutil.rmtree(project_dir / "theme")
    return project_dir
