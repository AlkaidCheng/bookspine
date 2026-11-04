"""Shared fixtures: a private copy of the sample book for each test."""

import shutil
from pathlib import Path

import pytest

SAMPLE_BOOK_DIR = Path(__file__).parent / "sample_book"


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Return a copy of the sample book that a test may change."""
    copy_dir = tmp_path.resolve() / "book-project"
    shutil.copytree(
        SAMPLE_BOOK_DIR, copy_dir, ignore=shutil.ignore_patterns("site", ".DS_Store")
    )
    return copy_dir


@pytest.fixture
def plain_project_dir(project_dir: Path) -> Path:
    """Return a copy of the sample book without its theme overrides."""
    shutil.rmtree(project_dir / "theme")
    return project_dir
