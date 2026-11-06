"""Build a textbook-style static site from Markdown chapters."""

from importlib.metadata import version

__version__ = version("guidebook")

from guidebook.errors import BuildError
from guidebook.site import BuildResult, build_book

__all__ = ["BuildError", "BuildResult", "__version__", "build_book"]
