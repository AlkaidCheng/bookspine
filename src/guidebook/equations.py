"""The equation count, which has to agree with MathJax's own numbering.

MathJax numbers equations in the browser, page by page. The build counts them too, so
that a chapter's count can run through its section pages and an ``\\eqref`` can reach
another page.
"""

import html
import re
from dataclasses import dataclass

from guidebook.errors import BuildError
from guidebook.pages import GlossaryEntry, Page

# The one version that cannot float: the environment sets below copy its rules, so an
# upgrade must recheck them against tests/test_equations.py.
# https://github.com/mathjax/MathJax-src/releases/tag/3.2.2
MATHJAX_URL = "https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-chtml.js"

# How MathJax numbers a display equation under ``tags: "all"``. These environments own
# the display's numbers: the first set has one per row, the second one in all, and a
# starred name means none unless a row carries ``\tag``. The third set takes no number
# of its own and discards any ``\label``, ``\tag`` or ``\notag`` written inside it. Any
# other display takes one number.
# https://github.com/mathjax/MathJax-src/blob/3.2.2/ts/input/tex/ams/AmsMappings.ts#L102
# https://github.com/mathjax/MathJax-src/blob/3.2.2/ts/input/tex/base/BaseMappings.ts#L703
# https://github.com/mathjax/MathJax-src/blob/3.2.2/ts/input/tex/base/BaseItems.ts#L1105
# https://github.com/mathjax/MathJax-src/blob/3.2.2/ts/input/tex/Tags.ts#L572
ROW_ENVIRONMENTS = {
    "align",
    "align*",
    "alignat",
    "alignat*",
    "eqnarray",
    "eqnarray*",
    "flalign",
    "gather",
    "gather*",
    "xalignat",
}
ONE_ROW_ENVIRONMENTS = {"equation", "equation*", "multline", "multline*"}
INNER_ENVIRONMENTS = {
    "aligned",
    "alignedat",
    "flalign*",
    "gathered",
    "split",
    "xalignat*",
    "xxalignat",
}

_DISPLAY_MATH_PATTERN = re.compile(r'<div class="arithmatex">\\\[(.*?)\\\]</div>', re.S)
_MATH_PATTERN = re.compile(r'<(div|span) class="arithmatex">.*?</\1>', re.S)
_EQUATION_REF_PATTERN = re.compile(r"\\(eqref|ref)\s*\{([^}]*)\}")
_TEX_COMMENT_PATTERN = re.compile(r"((?<!\\)(?:\\\\)*)%.*")
_TEX_TOKEN_PATTERN = re.compile(
    r"""
    \\begin\s*\{(?P<begin>[^}]*)\}
    | \\end\s*\{(?P<end>[^}]*)\}
    | \\label\s*\{(?P<label>[^}]*)\}
    | \\glossary\s*\{(?P<glossary>[^{}]*)\}
    | \\tag\*?\s*\{(?P<tag>(?:[^{}]|\{[^{}]*\})*)\}
    | (?P<notag>\\(?:notag|nonumber)\b)
    | (?P<row_end>\\\\\*?(?:\[[^\]]*\])?|\\(?:cr|newline)\b)
    | (?P<open>\{)
    | (?P<close>\})
    | \\.
    """,
    re.X | re.S,
)
_ROW_MARKS = {"label", "glossary", "tag", "notag"}

# Tags only the build reads, which MathJax must not see.
_GLOSSARY_TAG_PATTERN = re.compile(r"\\glossary(?![A-Za-z])\s*(?:\{[^{}]*\})?")


@dataclass
class EquationRow:
    """One row of a display equation that MathJax may number.

    Parameters
    ----------
    label : str
        The row's ``\\label``.
    tag : str
        The text of a manual ``\\tag``.
    counted : bool
        Whether the row takes the next number in the running count.
    name : str
        The name a ``\\glossary`` tag gives the row.
    """

    label: str = ""
    tag: str = ""
    counted: bool = True
    name: str = ""


def is_empty_row(tex: str) -> bool:
    """Whether a row holds nothing but marks; MathJax drops such a row at a table's end."""
    without_marks = _TEX_TOKEN_PATTERN.sub(
        lambda token: "" if token.lastgroup in _ROW_MARKS else token.group(), tex
    )
    return not without_marks.strip()


def equation_rows(tex: str) -> list[EquationRow]:
    """Split a display equation into the rows MathJax can number, in page order."""
    tex = _TEX_COMMENT_PATTERN.sub(r"\1", tex)
    rows: list[EquationRow] = []
    row = EquationRow()
    environments: list[str] = []
    braces = 0
    outer = ""  # the environment that owns the display's numbers
    row_start = 0

    for token in _TEX_TOKEN_PATTERN.finditer(tex):
        kind = token.lastgroup
        in_outer = bool(outer) and len(environments) == 1 and not braces
        if kind == "begin":
            name = token["begin"]
            if not environments and name in ROW_ENVIRONMENTS | ONE_ROW_ENVIRONMENTS:
                outer = name
                row = EquationRow(counted=not name.endswith("*"))
                row_start = token.end()
            environments.append(name)
        elif kind == "end":
            if in_outer:
                if not is_empty_row(tex[row_start : token.start()]):
                    rows.append(row)
                row = EquationRow()
            del environments[-1:]
        elif kind == "row_end" and in_outer and outer in ROW_ENVIRONMENTS:
            rows.append(row)
            row = EquationRow(counted=not outer.endswith("*"))
            row_start = token.end()
        elif kind == "open":
            braces += 1
        elif kind == "close":
            braces -= 1
        elif kind == "glossary":
            row.name = token["glossary"]  # read by the build, so any row can hold it
        elif kind in _ROW_MARKS and INNER_ENVIRONMENTS.isdisjoint(environments):
            if kind == "label":
                row.label = token["label"]
            elif kind == "tag":
                row.tag = token["tag"]
                row.counted = False
            else:
                row.counted = False
    return rows if outer else [row]


def equation_anchor(label: str) -> str:
    """Return the id MathJax gives the equation carrying `label`."""
    return "mjx-eqn:" + re.sub(r"\s", "_", label)


def number_equations(page: Page, equation_labels: dict[str, tuple[Page, str]]) -> None:
    """Carry the chapter's equation count through `page` and record its labels.

    A ``\\glossary`` tag makes a row a named equation, and leaves the page here.

    Raises
    ------
    BuildError
        If a label is already in `equation_labels`, or a tag has no name, stands
        outside its environment, or sits on a row with no label or no number.
    """
    counters = page.counters
    prefix = f"{page.chapter_number}." if page.chapter_number else ""
    page.equation_offset = counters.get("equation", 0)

    def number_row(row: EquationRow) -> None:
        number = row.tag
        if row.counted:
            counters["equation"] = counters.get("equation", 0) + 1
            number = f"{prefix}{counters['equation']}"
        if row.name and not (row.label and number):
            raise BuildError(
                f"{page.source_path}: named equation {row.name} "
                "needs a \\label and a number"
            )
        if not row.label or not number:
            return
        if row.label in equation_labels:
            other = equation_labels[row.label][0].source_path
            raise BuildError(
                f"{page.source_path}: equation label {row.label} "
                f"is also used in {other}"
            )
        equation_labels[row.label] = (page, number)
        if row.name:
            page.named_equations.append(
                GlossaryEntry(
                    name=row.name,
                    anchor=equation_anchor(row.label),
                    locator=f"Equation ({number})",
                )
            )

    def replace(match: re.Match[str]) -> str:
        tex = html.unescape(match.group(1))
        rows = equation_rows(tex)
        tag_count = len(_GLOSSARY_TAG_PATTERN.findall(tex))
        if tag_count != sum(1 for row in rows if row.name):
            raise BuildError(
                f"{page.source_path}: \\glossary in an equation needs a name "
                "and must stand inside the equation's environment"
            )
        for row in rows:
            number_row(row)
        return _GLOSSARY_TAG_PATTERN.sub("", match.group(0))

    page.body_html = _DISPLAY_MATH_PATTERN.sub(replace, page.body_html)


def resolve_equation_refs(
    page: Page, equation_labels: dict[str, tuple[Page, str]]
) -> None:
    """Check every equation reference and turn those that leave the page into links.

    Raises
    ------
    BuildError
        If a reference matches no label in `equation_labels`.
    """

    def replace(match: re.Match[str]) -> str:
        command, label = match.group(1), match.group(2)
        if label not in equation_labels:
            raise BuildError(
                f"{page.source_path}: \\{command}{{{label}}} matches no numbered equation"
            )
        target, number = equation_labels[label]
        if target is page:
            return match.group(0)  # MathJax resolves references within a page
        text = f"({number})" if command == "eqref" else number
        anchor = equation_anchor(label)
        return rf"\href{{{page.href(target)}#{anchor}}}{{\text{{{text}}}}}"

    page.body_html = _MATH_PATTERN.sub(
        lambda math: _EQUATION_REF_PATTERN.sub(replace, math.group(0)), page.body_html
    )
