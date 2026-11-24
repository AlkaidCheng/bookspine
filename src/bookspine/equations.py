"""The equation count, which has to agree with MathJax's own numbering.

MathJax numbers equations in the browser, page by page. The build counts them too, so
that a chapter's count can run through its section pages and an ``\\eqref`` can reach
another page.

The build also reads where the marks for a narrow screen stand, because MathJax reports a
misplaced one only on such a screen.
"""

import html
import re
from dataclasses import dataclass
from typing import NamedTuple

from bookspine.config import EQUATION_ANCHOR_PREFIX, WIDE_SCREEN_MACROS
from bookspine.errors import BuildError
from bookspine.mathjax_operators import (
    BINARY_OPERATOR_WORDS,
    OPERATOR_CHARACTERS,
    OPERATOR_MAKING_WORDS,
    RELATION_WORDS,
)
from bookspine.pages import GlossaryEntry, Page
from bookspine.passes import CODE_SEGMENT_PATTERN, outside_code

# The one version that cannot float: the environment sets below copy its rules, so an
# upgrade must recheck them against tests/test_equations.py.
# https://github.com/mathjax/MathJax-src/releases/tag/3.2.2
MATHJAX_URL = "https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-chtml.js"

# What MathJax acts on in a page's text as base.html configures it: the delimiters, an
# environment, a reference, and the escapes \\ and \$.
# https://github.com/mathjax/MathJax-src/blob/3.2.2/ts/input/tex/FindTeX.ts#L107
_MATHJAX_TEXT_PATTERN = re.compile(r"\\(?:[(\[\\$]|begin\s*\{|(?:eq)?ref\s*\{)")

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

# Where a mark of ``WIDE_SCREEN_MACROS`` may stand. A narrow screen reads it as the end
# of a row and an ``&`` that opens the next, which MathJax takes only from a table, with
# no brace and no ``\left`` open inside it; anywhere else it reports "Misplaced &". The
# table must also align its rows at ``&`` under the display's one number. `gathered`
# centres its rows, so the ``&`` opens a second column there. `flalign*`, `xalignat*`
# and `xxalignat` take a mark as `aligned` does, and are left out because amsmath has
# each as a display of its own.
# https://github.com/mathjax/MathJax-src/blob/3.2.2/ts/input/tex/StackItem.ts#L469
MARK_ENVIRONMENTS = ("aligned", "alignedat", "split")

# The arguments after ``\begin{name}`` of a mark's environment, which are not part of
# its first row: `aligned` has an optional position, `alignedat` that and its number
# of column pairs, and `split` none.
# https://github.com/mathjax/MathJax-src/blob/3.2.2/ts/input/tex/ams/AmsMethods.ts#L64
# https://github.com/mathjax/MathJax-src/blob/3.2.2/ts/input/tex/ams/AmsMethods.ts#L84
_MARK_ENVIRONMENT_ARGUMENT_PATTERNS = {
    "aligned": re.compile(r"\s*\[[^\]]*\]"),
    "alignedat": re.compile(r"\s*(?:\[[^\]]*\])?\s*\{[^{}]*\}"),
}

# Math as the Markdown step emits it: a display in a ``div``, inline math in a ``span``.
_MATH_PATTERN = re.compile(
    r'<(?P<element>div|span) class="arithmatex">(?P<tex>.*?)</(?P=element)>', re.S
)
_DISPLAY_MATH_PATTERN = re.compile(r'<div class="arithmatex">\\\[(.*?)\\\]</div>', re.S)
_EQUATION_REF = r"\\(?P<command>eqref|ref)\s*\{(?P<label>[^}]*)\}"
_EQUATION_REF_PATTERN = re.compile(_EQUATION_REF)
# The parts of a page's HTML that matter to a reference outside code. MathJax reads a
# reference inside math and bare in the text. It reads none in a comment or in a tag,
# which is matched whole because a quoted attribute value may hold a >. In the text it
# prints ``\\`` as one backslash, so the name after that is not a command.
# https://github.com/mathjax/MathJax-src/blob/3.2.2/ts/input/tex/FindTeX.ts#L107
_REF_TOKEN_PATTERN = re.compile(
    rf"""
    (?P<math><(?P<element>div|span)\ class="arithmatex">.*?</(?P=element)>)
    | <!--.*?-->
    | <(?:[^>"']|"[^"]*"|'[^']*')+>
    | \\\\
    | {_EQUATION_REF}
    """,
    re.X | re.S,
)
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
    | \\(?P<word>[A-Za-z]+)
    | \\.
    | (?P<ampersand>&)
    | (?P<character>\S)
    """,
    re.X | re.S,
)
_ROW_MARKS = {"label", "glossary", "tag", "notag"}

# The groups a formula opens besides environments, with the words an error has for a
# mark inside one.
_OPEN_BRACE = "{"
_OPEN_LEFT = r"\left"
_GROUP_PLACES = {_OPEN_BRACE: "inside braces", _OPEN_LEFT: r"between \left and \right"}

# The rules a misplaced mark breaks, as its error states them. The column rule keeps
# every cell in its column, since a narrow screen starts the new row in the second. The operator rule is the convention of breaking a display before a relation
# or a binary operator, which keeps the symbols the same on every screen: a product is
# broken before a \times the page writes, rather than one a narrow screen would add.
# https://web.mit.edu/course/21/21.guide/equation.htm
_MARK_RULES = {
    "inline": "only a display equation breaks",
    "environment": f"a mark must stand in {', '.join(MARK_ENVIRONMENTS[:-1])} "
    f"or {MARK_ENVIRONMENTS[-1]}",
    "group": r"a row cannot end inside braces or between \left and \right",
    "column": "a mark must stand after its row's first & and before its second",
    "empty": "it would leave an empty row on a narrow screen",
    "operator": r"\narrowbreak must come right before a relation or binary operator, "
    "such as = or +",
}
_OPERATOR_WORDS = BINARY_OPERATOR_WORDS | RELATION_WORDS | OPERATOR_MAKING_WORDS

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


class MisplacedMark(NamedTuple):
    """A mark that a narrow screen cannot read as the start of a row of its own.

    Parameters
    ----------
    mark : str
        The mark as written, such as ``\\narrowbreak``.
    place : str
        Where it stands, such as ``inside braces``.
    rule : str
        The rule that place breaks.
    """

    mark: str
    place: str
    rule: str

    def __str__(self) -> str:
        return f"{self.mark} {self.place}: {self.rule}"


@dataclass
class _Group:
    """A group open in a formula: an environment, a brace or a ``\\left``.

    For an environment, the other fields describe its current row as far as it has
    been read.
    """

    name: str
    ampersands: int = 0
    has_content: bool = False

    @property
    def is_environment(self) -> bool:
        return self.name not in _GROUP_PLACES

    def start_row(self) -> None:
        self.ampersands, self.has_content = 0, False


class _MarkReader:
    """Read a formula one token at a time, as far as the placement of marks needs."""

    def __init__(self, tex: str, *, inline: bool) -> None:
        self.tex = tex
        self.inline = inline
        self.groups: list[_Group] = []
        self.waiting = ""  # a mark whose next token is not read yet
        self.arguments_end = 0  # where the arguments of the last \begin end

    def environment(self) -> _Group | None:
        """Return the innermost open environment."""
        return next(
            (group for group in reversed(self.groups) if group.is_environment), None
        )

    def row(self) -> _Group | None:
        """Return the innermost group when it is an environment, which owns an & there."""
        if self.groups and self.groups[-1].is_environment:
            return self.groups[-1]
        return None

    def read(self, token: re.Match[str]) -> MisplacedMark | None:
        """Take in the next token and return the mark it shows to be misplaced."""
        kind, word = token.lastgroup, token["word"]
        if token.start() < self.arguments_end or kind in _ROW_MARKS:
            return None
        if self.waiting and kind not in ("open", "close"):
            if misplaced := self.check_next(token):
                return misplaced
        if word in WIDE_SCREEN_MACROS:
            return self.read_mark(f"\\{word}")
        row = self.row()
        if kind == "ampersand":
            if row:
                row.ampersands += 1
        elif kind == "row_end":
            if row:
                row.start_row()
        elif kind in ("end", "close") or word == "right":
            del self.groups[-1:]
        else:
            environment = self.environment()
            if environment and kind != "open":
                environment.has_content = True
            if kind == "begin":
                self.open_environment(token)
            elif kind == "open":
                self.groups.append(_Group(_OPEN_BRACE))
            elif word == "left":
                self.groups.append(_Group(_OPEN_LEFT))
        return None

    def open_environment(self, begin: re.Match[str]) -> None:
        name = begin["begin"]
        self.groups.append(_Group(name))
        pattern = _MARK_ENVIRONMENT_ARGUMENT_PATTERNS.get(name)
        if pattern and (arguments := pattern.match(self.tex, begin.end())):
            self.arguments_end = arguments.end()

    def read_mark(self, mark: str) -> MisplacedMark | None:
        if self.inline:
            return MisplacedMark(mark, "in inline math", _MARK_RULES["inline"])
        if not self.groups:
            place = "outside an environment"
            return MisplacedMark(mark, place, _MARK_RULES["environment"])
        innermost = self.groups[-1]
        if not innermost.is_environment:
            place = _GROUP_PLACES[innermost.name]
            return MisplacedMark(mark, place, _MARK_RULES["group"])
        if innermost.name not in MARK_ENVIRONMENTS:
            place = f"in {innermost.name}"
            return MisplacedMark(mark, place, _MARK_RULES["environment"])
        if innermost.ampersands != 1:
            place = (
                "after a second &" if innermost.ampersands else "with no & before it"
            )
            return MisplacedMark(mark, f"{place} in its row", _MARK_RULES["column"])
        if not innermost.has_content:
            return MisplacedMark(mark, "at the start of a row", _MARK_RULES["empty"])
        self.waiting = mark
        return None

    def check_next(self, token: re.Match[str]) -> MisplacedMark | None:
        """Check the token after a mark, which starts the mark's new row."""
        mark, self.waiting = self.waiting, ""
        kind, word = token.lastgroup, token["word"]
        if kind in ("row_end", "end"):
            return MisplacedMark(mark, "at the end of a row", _MARK_RULES["empty"])
        if word in WIDE_SCREEN_MACROS:
            return MisplacedMark(mark, "next to another mark", _MARK_RULES["empty"])
        is_operator = word in _OPERATOR_WORDS or (
            kind == "character" and token.group() in OPERATOR_CHARACTERS
        )
        if mark == r"\narrowbreak" and not is_operator:
            place = f"before {token.group()}"
            return MisplacedMark(mark, place, _MARK_RULES["operator"])
        return None


def misplaced_mark(tex: str, *, inline: bool = False) -> MisplacedMark | None:
    r"""Find the first mark in `tex` that a narrow screen cannot read as a row's start.

    A mark may stand only in a display equation, in an environment of
    ``MARK_ENVIRONMENTS``, with every brace and ``\left`` opened there closed again.
    It must stand in its row's second column, between the first ``&`` and any second,
    with content on both sides in its row. ``\narrowbreak`` must come right before a
    relation or a binary operator.

    Parameters
    ----------
    tex : str
        The TeX of one formula.
    inline : bool, optional
        Whether the formula is inline math, where no mark may stand.

    Returns
    -------
    MisplacedMark or None
        The first mark that breaks one of these rules, or None if none does.
    """
    reader = _MarkReader(_TEX_COMMENT_PATTERN.sub(r"\1", tex), inline=inline)
    for token in _TEX_TOKEN_PATTERN.finditer(reader.tex):
        if misplaced := reader.read(token):
            return misplaced
    return None


def equation_anchor(label: str) -> str:
    """Return the id MathJax gives the equation carrying `label`."""
    return EQUATION_ANCHOR_PREFIX + re.sub(r"\s", "_", label)


def needs_mathjax(page_body: str) -> bool:
    """Return whether MathJax would change anything in the HTML `page_body`.

    Code is left out because MathJax skips ``pre`` and ``code`` elements.
    """
    text = html.unescape(CODE_SEGMENT_PATTERN.sub("", page_body))
    return _MATHJAX_TEXT_PATTERN.search(text) is not None


def number_equations(page: Page, equation_labels: dict[str, tuple[Page, str]]) -> None:
    """Carry the chapter's equation count through `page` and record its labels.

    A ``\\glossary`` tag makes a row a named equation, and leaves the page here. The
    marks for a narrow screen are checked in all of the page's math.

    Raises
    ------
    BuildError
        If a label is already in `equation_labels`; if a tag has no name, stands
        outside its environment, or sits on a row with no label or no number; or if
        :func:`misplaced_mark` finds a mark.
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

    for math in _MATH_PATTERN.finditer(page.body_html):
        tex = html.unescape(math["tex"])
        if misplaced := misplaced_mark(tex, inline=math["element"] == "span"):
            raise BuildError(f"{page.source_path}: {misplaced}")
    page.body_html = _DISPLAY_MATH_PATTERN.sub(replace, page.body_html)


def resolve_equation_refs(
    page: Page, equation_labels: dict[str, tuple[Page, str]]
) -> None:
    """Check every equation reference and turn those that leave the page into links.

    A reference is read where MathJax reads one: inside math, and bare in the text
    around it, where a link is set as inline math. Code, comments and the attributes
    of a tag are left as written.

    Raises
    ------
    BuildError
        If a reference matches no label in `equation_labels`.
    """

    def link_tex(reference: re.Match[str]) -> str:
        command, label = reference["command"], reference["label"]
        if label not in equation_labels:
            raise BuildError(
                f"{page.source_path}: \\{command}{{{label}}} matches no numbered equation"
            )
        target, number = equation_labels[label]
        if target is page:
            return ""  # MathJax resolves references within a page
        text = f"({number})" if command == "eqref" else number
        anchor = equation_anchor(label)
        return rf"\href{{{page.href(target)}#{anchor}}}{{\text{{{text}}}}}"

    def replace(token: re.Match[str]) -> str:
        if token["math"]:
            return _EQUATION_REF_PATTERN.sub(
                lambda reference: link_tex(reference) or reference.group(0),
                token.group(0),
            )
        if token["command"] and (tex := link_tex(token)):
            return rf'<span class="arithmatex">\({tex}\)</span>'
        return token.group(0)

    page.body_html = outside_code(
        page.body_html, lambda text: _REF_TOKEN_PATTERN.sub(replace, text)
    )
