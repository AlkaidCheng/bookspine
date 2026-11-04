"""Build a textbook-style static site from Markdown chapters."""

__version__ = "0.1.0"

from guidebook.errors import BuildError
from guidebook.site import BuildResult, build_book

__all__ = ["BuildError", "BuildResult", "__version__", "build_book"]
