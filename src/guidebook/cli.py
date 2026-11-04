"""The ``guidebook`` command."""

import argparse
import io
import sys

from guidebook import __version__
from guidebook.errors import BuildError
from guidebook.site import build_book

_DESCRIPTION = "Build a textbook-style static site from Markdown chapters."


def make_parser() -> argparse.ArgumentParser:
    """Return the argument parser of the ``guidebook`` command."""
    parser = argparse.ArgumentParser(prog="guidebook", description=_DESCRIPTION)
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="build a book into a site")
    build.add_argument(
        "project_dir",
        nargs="?",
        default=".",
        help="directory holding book.yaml (default: the current directory)",
    )
    build.add_argument(
        "--site-dir",
        help="directory to write the site to (default: site/ in the project directory)",
    )
    build.add_argument(
        "--allow-warnings",
        action="store_true",
        help="do not fail the build on warnings (uncited references)",
    )
    return parser


def run_build(args: argparse.Namespace) -> int:
    """Build the book `args` names and return the exit code."""
    try:
        result = build_book(args.project_dir, args.site_dir)
    except (BuildError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    print(
        f"built {result.page_count} pages ({result.chapter_count} chapters) "
        f"into {result.site_dir}"
    )
    if result.overrides:
        print(f"overrides: {', '.join(result.overrides)}")
    if result.warnings and not args.allow_warnings:
        print(
            "error: warnings are fatal (pass --allow-warnings to override)",
            file=sys.stderr,
        )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the command line and return the exit code."""
    # A console on Windows may not encode every character of a path or a title.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="backslashreplace")
    args = make_parser().parse_args(argv)
    return run_build(args)
