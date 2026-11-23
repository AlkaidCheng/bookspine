"""Write src/bookspine/mathjax_operators.py from MathJax's own tables.

The module lists the TeX that MathJax sets as a binary operator or a relation, which a
``\\narrowbreak`` mark must stand before. Run this script from the repository root
whenever MathJax is upgraded, with the new version as its argument:

    python scripts/write_mathjax_operators.py 3.2.2

A control word's class is the one MathJax's symbol table gives it, or else the class of
its character in the operator dictionary's infix forms.
"""

import argparse
import re
import textwrap
import urllib.request
from pathlib import Path

SOURCE_URL = "https://raw.githubusercontent.com/mathjax/MathJax-src/{version}/ts/{path}"
PAGE_URL = "https://github.com/mathjax/MathJax-src/blob/{version}/ts/{path}"
BASE_MAPPINGS_PATH = "input/tex/base/BaseMappings.ts"
AMS_MAPPINGS_PATH = "input/tex/ams/AmsMappings.ts"
OPERATOR_DICTIONARY_PATH = "core/MmlTree/OperatorDictionary.ts"
# The symbol tables, each a map from a control word to its character.
SYMBOL_TABLES = (
    (BASE_MAPPINGS_PATH, "mathchar0mo"),
    (AMS_MAPPINGS_PATH, "AMSmath-mathchar0mo"),
    (AMS_MAPPINGS_PATH, "AMSsymbols-mathchar0mo"),
)
# Control words that set what follows them, or what they stand for, as one class:
# mathbin and mathrel (TeXAtom), stackbin and stackrel, not (Not) and the macros
# iff, implies and impliedby, each defined in the 'macros' table of the file named.
OPERATOR_MAKING_WORDS = {
    BASE_MAPPINGS_PATH: ("iff", "mathbin", "mathrel", "not", "stackbin", "stackrel"),
    AMS_MAPPINGS_PATH: ("impliedby", "implies"),
}
OUTPUT_PATH = Path("src/bookspine/mathjax_operators.py")
LINE_WIDTH = 84

_OPERATOR_KIND_PATTERN = re.compile(
    r"^  (\w+):\s+OPDEF\(\d+, \d+, TEXCLASS\.(\w+)", re.M
)
_INFIX_ENTRY_PATTERN = re.compile(r"^    '((?:[^'\\]|\\.)+)':\s+([^/\n]+)", re.M)
_SYMBOL_ENTRY_PATTERN = re.compile(
    r"^  '?(\w+)'?:\s+\[?'((?:[^'\\]|\\.)+)'([^\n]*)", re.M
)
_TEX_CLASS_PATTERN = re.compile(r"TEXCLASS\.(\w+)")
_UNICODE_ESCAPE_PATTERN = re.compile(r"\\u([0-9A-Fa-f]{4})")


def read_source(version: str, path: str) -> str:
    url = SOURCE_URL.format(version=version, path=path)
    with urllib.request.urlopen(url) as response:  # noqa: S310 (a fixed https URL)
        text: str = response.read().decode("utf-8")
    return text


def unescape(text: str) -> str:
    return _UNICODE_ESCAPE_PATTERN.sub(lambda match: chr(int(match[1], 16)), text)


def table(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    return text[begin : text.index(end, begin + len(start))]


def infix_classes(dictionary: str) -> dict[str, str]:
    """Return the TeX class of each character in the infix forms of the dictionary."""
    kinds = dict(_OPERATOR_KIND_PATTERN.findall(dictionary))
    classes = {}
    for key, value in _INFIX_ENTRY_PATTERN.findall(
        table(dictionary, "  infix: {", "\n  }")
    ):
        if value.startswith("MO."):
            classes[unescape(key)] = kinds[value[3:].rstrip(", ")]
        elif found := _TEX_CLASS_PATTERN.search(value):
            classes[unescape(key)] = found[1]
    return classes


def word_classes(
    mappings: str, map_name: str, classes: dict[str, str]
) -> dict[str, str]:
    """Return the TeX class of each control word in one symbol table."""
    entries = table(mappings, f"new sm.CharacterMap('{map_name}'", "\n});")
    words = {}
    for word, character, rest in _SYMBOL_ENTRY_PATTERN.findall(entries):
        override = _TEX_CLASS_PATTERN.search(rest)
        words[word] = override[1] if override else classes.get(unescape(character), "")
    return words


def words_assignment(name: str, words: list[str]) -> str:
    lines = textwrap.wrap(" ".join(words), LINE_WIDTH - 4)
    body = "\n".join(f"    {line}" for line in lines)
    return f'{name} = frozenset("""\n{body}\n    """.split())\n'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", help="a MathJax-src tag, such as 3.2.2")
    version = parser.parse_args().version
    sources = {
        path: read_source(version, path)
        for path in (BASE_MAPPINGS_PATH, AMS_MAPPINGS_PATH, OPERATOR_DICTIONARY_PATH)
    }
    classes = infix_classes(sources[OPERATOR_DICTIONARY_PATH])
    words: dict[str, str] = {}
    for path, map_name in SYMBOL_TABLES:
        words.update(word_classes(sources[path], map_name, classes))
    for path, names in OPERATOR_MAKING_WORDS.items():
        for name in names:
            if not re.search(rf"^  {name}:", sources[path], re.M):
                raise SystemExit(f"{name} is not defined in {path} of {version}")
    characters = sorted(
        character
        for character, kind in classes.items()
        if len(character) == 1 and character.isascii() and kind in ("BIN", "REL")
    )
    links = "\n".join(PAGE_URL.format(version=version, path=path) for path in sources)
    making = sorted(name for names in OPERATOR_MAKING_WORDS.values() for name in names)
    module = (
        f'"""The TeX that MathJax {version} sets as a binary operator or a relation.\n\n'
        "Written by scripts/write_mathjax_operators.py from MathJax's symbol tables and\n"
        "operator dictionary; run it again when MathJax is upgraded.\n"
        f'{links}\n"""\n\n'
        "# Characters, as typed.\n"
        f'OPERATOR_CHARACTERS = frozenset("{"".join(characters)}")\n\n'
        "# Control words that each stand for one symbol.\n"
        + words_assignment(
            "BINARY_OPERATOR_WORDS",
            sorted(word for word, kind in words.items() if kind == "BIN"),
        )
        + words_assignment(
            "RELATION_WORDS",
            sorted(word for word, kind in words.items() if kind == "REL"),
        )
        + "\n# Control words that make a binary operator or a relation of what follows.\n"
        + words_assignment("OPERATOR_MAKING_WORDS", making)
    )
    OUTPUT_PATH.write_text(module, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
