"""Build a textbook-style static site from Markdown chapters."""

from importlib.metadata import version

__version__ = version("bookspine")

from bookspine.errors import BuildError
from bookspine.site import BuildResult, build_book

__all__ = ["BuildError", "BuildResult", "__version__", "build_book"]
