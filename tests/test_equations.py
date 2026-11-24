"""Tests for the equation count, which has to agree with MathJax's own numbering."""

from pathlib import Path
from typing import Any

import pytest

from bookspine.config import NARROW_SCREEN_MACROS
from bookspine.equations import (
    INNER_ENVIRONMENTS,
    MARK_ENVIRONMENTS,
    MisplacedMark,
    equation_rows,
    misplaced_mark,
    needs_mathjax,
    number_equations,
    resolve_equation_refs,
)
from bookspine.errors import BuildError
from bookspine.pages import Page

# Display equations and the numbers MathJax 3.2.2 gives them under ``tags: "all"``:
# "#" stands for the next number in the count, anything else for a manual ``\tag``.
NUMBERED_FORMS = [
    (r"x", ["#"]),
    (r"x \notag", []),
    (r"x \nonumber", []),
    (r"x \tag{A}", ["A"]),
    (r"x \tag*{A}", ["A"]),
    (r"x \tag{$a_{1}$}", ["$a_{1}$"]),
    (r"a \\ b", ["#"]),
    ("x % \\notag\n", ["#"]),
    (r"x = 5\% \notag", []),
    (r"\begin{equation} x \end{equation}", ["#"]),
    (r"\begin{equation} x \notag \end{equation}", []),
    (r"\begin{equation} a \\ b \end{equation}", ["#"]),
    (r"\begin{equation} x \end{equation} \notag", ["#"]),
    (r"\notag \begin{equation} x \end{equation}", ["#"]),
    (r"\begin{equation*} x \end{equation*}", []),
    (r"\begin{equation*} x \tag{A} \end{equation*}", ["A"]),
    (r"\begin{multline} a \\ b \end{multline}", ["#"]),
    (r"\begin{multline} a \notag \\ b \end{multline}", []),
    (r"\begin{multline*} a \\ b \end{multline*}", []),
    (r"\begin{align} a \\ b \end{align}", ["#", "#"]),
    (r"\begin{align} a \notag \\ b \end{align}", ["#"]),
    (r"\begin{align} a \notag \\ b \notag \end{align}", []),
    (r"\begin{align} a \tag{A} \\ b \end{align}", ["A", "#"]),
    (r"\begin{align} a \\ \\ b \end{align}", ["#", "#", "#"]),
    (r"\begin{align} a \\[2pt] b \\* c \end{align}", ["#", "#", "#"]),
    (r"\begin{align} a \cr b \newline c \end{align}", ["#", "#", "#"]),
    ("\\begin{align} a \\\\ b \\\\\n\\end{align}", ["#", "#"]),
    ("\\begin{align} a \\\\[2pt]\n\\end{align}", ["#"]),
    ("\\begin{align} a \\\\*\n\\end{align}", ["#"]),
    ("\\begin{align} a \\\\ % note\n\\end{align}", ["#"]),
    ("\\begin{align} a \\\\% note\n b \\end{align}", ["#", "#"]),
    ("\\begin{align} a % \\\\ b\n\\end{align}", ["#"]),
    ("\\begin{align} a \\\\ \\notag\n\\end{align}", ["#"]),
    ("\\begin{align} a \\\\ \\label{x}\n\\end{align}", ["#"]),
    ("\\begin{align} a \\\\ \\tag{A}\n\\end{align}", ["#"]),
    (r"\begin{align} a \end{align} \notag", ["#"]),
    (r"\begin{align} \sum_{\substack{a \\ b}} \\ c \end{align}", ["#", "#"]),
    (r"\begin{align} {a \\ b} \\ c \end{align}", ["#", "#"]),
    (r"\begin{align} \{ a \\ b \} \end{align}", ["#", "#"]),
    (
        r"\begin{align} a = \begin{cases} 1 \\ 2 \end{cases} \\ b \end{align}",
        ["#", "#"],
    ),
    (
        r"\begin{align} a = \begin{cases} 1 \notag \\ 2 \end{cases} \\ b \end{align}",
        ["#"],
    ),
    (
        r"\begin{align} \begin{aligned} a \\ b \end{aligned} \\ c \end{align}",
        ["#", "#"],
    ),
    (
        r"\begin{align} \begin{aligned} a \notag \end{aligned} \\ c \end{align}",
        ["#", "#"],
    ),
    (r"\begin{align} \begin{array}{c} a \\ b \end{array} \\ c \end{align}", ["#", "#"]),
    (r"\begin {align} a \\ b \end {align}", ["#", "#"]),
    (r"y = \begin{align} a \\ b \end{align}", ["#", "#"]),
    (r"\begin{align*} a \\ b \end{align*}", []),
    (r"\begin{align*} a \tag{A} \\ b \tag{B} \end{align*}", ["A", "B"]),
    (r"\begin{gather} a \\ b \end{gather}", ["#", "#"]),
    (r"\begin{gather*} a \\ b \end{gather*}", []),
    (r"\begin{alignat}{2} a &= b \\ c &= d \end{alignat}", ["#", "#"]),
    (r"\begin{alignat*}{2} a &= b \\ c &= d \end{alignat*}", []),
    (r"\begin{eqnarray} a \\ b \end{eqnarray}", ["#", "#"]),
    (r"\begin{eqnarray*} a \\ b \end{eqnarray*}", []),
    (r"\begin{flalign} a \\ b \end{flalign}", ["#", "#"]),
    (r"\begin{flalign*} a \\ b \end{flalign*}", ["#"]),
    (r"\begin{flalign*} a \notag \\ b \end{flalign*}", ["#"]),
    (r"\begin{xalignat}{1} a & b \\ c & d \end{xalignat}", ["#", "#"]),
    (r"\begin{xalignat*}{1} a & b \\ c & d \end{xalignat*}", ["#"]),
    (r"\begin{xxalignat}{1} a & b \\ c & d \end{xxalignat}", ["#"]),
    (r"\begin{equation}\begin{split} a \\ b \end{split}\end{equation}", ["#"]),
    (r"\begin{split} a \\ b \end{split}", ["#"]),
    (r"\begin{aligned} a \\ b \end{aligned}", ["#"]),
    (r"\begin{aligned} a \notag \\ b \end{aligned}", ["#"]),
    (r"\begin{aligned} a \\ b \end{aligned} \notag", []),
    (r"\notag \begin{aligned} a \\ b \end{aligned}", []),
    (r"\begin{gathered} a \\ b \end{gathered}", ["#"]),
    (r"\begin{alignedat}{1} a \\ b \end{alignedat}", ["#"]),
    (r"\begin{cases} a \\ b \end{cases}", ["#"]),
    (r"\begin{cases} a \\ b \end{cases} \nonumber", []),
    (r"\begin{array}{c} a \\ b \end{array}", ["#"]),
    (r"\begin{pmatrix} a \\ b \end{pmatrix}", ["#"]),
]

# Where a ``\label`` takes effect, as (equation, labels that get a number).
LABEL_FORMS = [
    (r"x \label{a}", ["a"]),
    (r"x \label {a}", ["a"]),
    (r"x \notag \label{a}", []),
    (r"x \tag{A} \label{a}", ["a"]),
    (r"\begin{align} a \label{a} \\ b \label{b} \end{align}", ["a", "b"]),
    (r"\begin{align} a \label{a} \notag \\ b \label{b} \end{align}", ["b"]),
    (r"\label{a} \begin{align} a \\ b \end{align}", []),
    (r"\label{a} \begin{equation} x \end{equation}", []),
    (r"\begin{equation}\begin{split} a \label{a} \\ b \end{split}\end{equation}", []),
    (r"\begin{equation}\begin{split} a \\ b \end{split}\label{a}\end{equation}", ["a"]),
    (r"\begin{aligned} a \label{a} \\ b \end{aligned}", []),
    (r"\begin{aligned} a \\ b \end{aligned} \label{a}", ["a"]),
    (r"\label{a} \begin{aligned} a \\ b \end{aligned}", ["a"]),
    (r"\begin{cases} a \label{a} \\ b \end{cases}", ["a"]),
    (r"\begin{align} \begin{aligned} a \label{a} \end{aligned} \\ c \end{align}", []),
    (
        r"\begin{align} \begin{aligned} a \end{aligned} \label{a} \\ c \end{align}",
        ["a"],
    ),
    (
        r"\begin{align} \begin{cases} a \label{a} \\ b \end{cases} \\ c \end{align}",
        ["a"],
    ),
    (r"\begin{align*} a \label{a} \\ b \tag{B} \end{align*}", []),
    (
        r"\begin{align*} a \tag{A} \label{a} \\ b \tag{B} \label{b} \end{align*}",
        ["a", "b"],
    ),
    (r"\begin{equation*} x \tag{A} \label{a} \end{equation*}", ["a"]),
]

# Where a mark may stand. With the definitions of NARROW_SCREEN_MACROS, MathJax 3.2.2
# sets each of these with no error, the numbers of a wide screen and one more row for
# every mark, which starts at the row's &.
MARK_FORMS = [
    r"\begin{aligned} & a \narrowbreak + b \end{aligned}",
    r"\begin{aligned} & a \narrowsep b \end{aligned}",
    r"\begin{aligned} & a \narrowbreak + b , \narrowsep c \narrowbreak + d \end{aligned}",
    r"\begin{aligned} a &= b \narrowbreak + c \\ d &= e \narrowsep f \end{aligned}",
    r"\begin{aligned}[t] & a \narrowbreak + b \end{aligned}",
    r"\begin{split} & a \narrowbreak + b \end{split}",
    r"\begin{equation}\begin{split} & a \narrowsep b \end{split}\end{equation}",
    r"\begin{alignedat}{1} & a \narrowbreak + b \end{alignedat}",
    r"\begin{alignedat}{2} a &= b \narrowsep c \\ d &= e & f &= g \end{alignedat}",
    r"\begin{aligned} & x + y \narrowbreak + z &= w \\ & u &= v \end{aligned}",
    r"\begin{aligned} & a \narrowsep & b \end{aligned}",
    "\\begin{aligned} & a % a comment\n\\narrowbreak + b \\end{aligned}",
    r"\begin{aligned} & a \label{eq:a} \narrowbreak + b \end{aligned}",
    # \narrowbreak before each kind of operator, and \narrowsep before anything.
    r"\begin{aligned} a &= b \narrowbreak - c \end{aligned}",
    r"\begin{aligned} a &= b \narrowbreak = c \end{aligned}",
    r"\begin{aligned} a &= b \narrowbreak \le c \end{aligned}",
    r"\begin{aligned} & a \narrowbreak \times \frac{b}{c} \end{aligned}",
    r"\begin{aligned} & f \narrowbreak \to g \end{aligned}",
    r"\begin{aligned} a &= b \narrowbreak \not= c \end{aligned}",
    r"\begin{aligned} a &= b \narrowbreak \mathrel{\overset{!}{=}} c \end{aligned}",
    r"\begin{aligned} & a \narrowbreak {} + b \end{aligned}",
    r"\begin{aligned} & a = 1 , \narrowsep \frac{b}{c} = 2 \end{aligned}",
    # After groups that have closed, and beside delimiters that open none.
    r"\begin{aligned} & \frac{a}{b} \narrowbreak + \sqrt{c} \end{aligned}",
    r"\begin{aligned} & \left( a \right) \narrowbreak + {b} \end{aligned}",
    r"\begin{aligned} & \bigl( a \narrowbreak + b \bigr) \end{aligned}",
    r"\begin{aligned} & \{ a \narrowbreak + b \} \end{aligned}",
    r"\begin{aligned} & a \leftarrow b \narrowbreak + c \rightarrow d \end{aligned}",
    r"\begin{aligned} & \begin{pmatrix} 1 \\ 2 \end{pmatrix} \narrowbreak + b \end{aligned}",
    # In an environment that stands inside a group or another environment.
    r"\left\{ \begin{aligned} & a \narrowbreak + b \end{aligned} \right.",
    r"{ \begin{aligned} & a \narrowsep b \end{aligned} }",
    r"\boxed{ \begin{aligned} & a \narrowsep b \end{aligned} }",
    r"\begin{equation} \begin{aligned} & a \narrowbreak + b \end{aligned} \end{equation}",
    r"\begin{align} \begin{aligned} & a \narrowbreak + b \end{aligned} \\ c \end{align}",
    r"\begin{gather} \begin{aligned} & a \narrowsep b \end{aligned} \\ c \end{gather}",
    r"\begin{cases} \begin{aligned} & a \narrowbreak + b \end{aligned} \\ c \end{cases}",
]

# Where the build refuses a mark, as (math, the mark and where it stands), grouped by
# what MathJax 3.2.2 makes of it on a narrow screen.
MISPLACED_MARK_FORMS = [
    # "Misplaced &": no table is open to take the row.
    (r"a \narrowbreak + b", r"\narrowbreak outside an environment"),
    (r"a \narrowsep b", r"\narrowsep outside an environment"),
    (
        r"\begin{aligned} & a \end{aligned} \narrowsep b",
        r"\narrowsep outside an environment",
    ),
    # "Misplaced &": a row cannot end inside braces.
    (
        r"\begin{aligned} & {a \narrowbreak + b} \end{aligned}",
        r"\narrowbreak inside braces",
    ),
    (
        r"\begin{aligned} & \frac{a \narrowbreak + b}{c} \end{aligned}",
        r"\narrowbreak inside braces",
    ),
    (
        r"\begin{aligned} & \sqrt{a \narrowbreak + b} \end{aligned}",
        r"\narrowbreak inside braces",
    ),
    (
        r"\begin{aligned} & x^{a \narrowbreak + b} \end{aligned}",
        r"\narrowbreak inside braces",
    ),
    (
        r"\begin{aligned} & { { a } \narrowsep b } \end{aligned}",
        r"\narrowsep inside braces",
    ),
    (
        r"\begin{split} & {a \narrowbreak + b} \end{split}",
        r"\narrowbreak inside braces",
    ),
    (
        r"\begin{alignedat}{1} & {a \narrowbreak + b} \end{alignedat}",
        r"\narrowbreak inside braces",
    ),
    # "Misplaced &": nor can a row end between \left and \right.
    (
        r"\begin{aligned} & \left( a \narrowbreak + b \right) \end{aligned}",
        r"\narrowbreak between \left and \right",
    ),
    (
        r"\begin{aligned} & \left[ a \narrowsep b \right] \end{aligned}",
        r"\narrowsep between \left and \right",
    ),
    (
        r"\begin{aligned} & \left( \left( a \right) \narrowbreak + b \right) \end{aligned}",
        r"\narrowbreak between \left and \right",
    ),
    (
        r"\begin{aligned} & \left( a \middle| b \narrowbreak + c \right) \end{aligned}",
        r"\narrowbreak between \left and \right",
    ),
    (
        r"\begin{split} & \left( a \narrowbreak + b \right) \end{split}",
        r"\narrowbreak between \left and \right",
    ),
    # "Misplaced &" in `equation`, and "The rows within the multline environment must
    # have exactly one column".
    (
        r"\begin{equation} a \narrowbreak + b \end{equation}",
        r"\narrowbreak in equation",
    ),
    (
        r"\begin{equation*} a \narrowbreak + b \end{equation*}",
        r"\narrowbreak in equation*",
    ),
    (
        r"\begin{multline} a \narrowbreak + b \end{multline}",
        r"\narrowbreak in multline",
    ),
    (r"\begin{multline*} a \narrowsep b \end{multline*}", r"\narrowsep in multline*"),
    # No error, and a second number, which the build's count lacks.
    (r"\begin{align} a \narrowbreak + b \end{align}", r"\narrowbreak in align"),
    (
        r"\begin{alignat}{1} & a \narrowbreak + b \end{alignat}",
        r"\narrowbreak in alignat",
    ),
    (r"\begin{gather} a \narrowsep b \end{gather}", r"\narrowsep in gather"),
    (r"\begin{eqnarray} a \narrowsep b \end{eqnarray}", r"\narrowsep in eqnarray"),
    (r"\begin{flalign} & a \narrowsep b \end{flalign}", r"\narrowsep in flalign"),
    (r"\begin{xalignat}{1} & a \narrowsep b \end{xalignat}", r"\narrowsep in xalignat"),
    # No error and no number: a row of its own in an environment that tags by row.
    (r"\begin{align*} & a \narrowbreak + b \end{align*}", r"\narrowbreak in align*"),
    (
        r"\begin{alignat*}{1} & a \narrowbreak + b \end{alignat*}",
        r"\narrowbreak in alignat*",
    ),
    (r"\begin{gather*} a \narrowsep b \end{gather*}", r"\narrowsep in gather*"),
    (r"\begin{eqnarray*} a \narrowsep b \end{eqnarray*}", r"\narrowsep in eqnarray*"),
    # No error: a row of a table that is not the equation's aligned rows.
    (r"\begin{gathered} a \narrowsep b \end{gathered}", r"\narrowsep in gathered"),
    (r"\begin{cases} a \narrowbreak + b \end{cases}", r"\narrowbreak in cases"),
    (
        r"\begin{aligned} & a = \begin{cases} 1 \narrowsep 2 \end{cases} \end{aligned}",
        r"\narrowsep in cases",
    ),
    (r"\begin{array}{c} a \narrowsep b \end{array}", r"\narrowsep in array"),
    (r"\begin{pmatrix} a \narrowsep b \end{pmatrix}", r"\narrowsep in pmatrix"),
    (
        r"\begin{aligned} & \sum_{\substack{a \narrowsep b}} \end{aligned}",
        r"\narrowsep inside braces",
    ),
    # No error and the one number, as in `aligned`: displays of their own in amsmath.
    (
        r"\begin{flalign*} & a \narrowbreak + b \end{flalign*}",
        r"\narrowbreak in flalign*",
    ),
    (
        r"\begin{xalignat*}{1} & a \narrowbreak + b \end{xalignat*}",
        r"\narrowbreak in xalignat*",
    ),
    (
        r"\begin{xxalignat}{1} & a \narrowbreak + b \end{xxalignat}",
        r"\narrowbreak in xxalignat",
    ),
    # No error, but the rest of the row leaves its column, and the alignment of the
    # other rows changes.
    (
        r"\begin{aligned} a + b \narrowbreak + c &= d \\ e &= f \end{aligned}",
        r"\narrowbreak with no & before it in its row",
    ),
    (
        r"\begin{aligned} a + b + c \narrowbreak + d \\ e \end{aligned}",
        r"\narrowbreak with no & before it in its row",
    ),
    (
        r"\begin{alignedat}{2} a &= b &\quad c &= d \narrowsep e = f \end{alignedat}",
        r"\narrowsep after a second & in its row",
    ),
    # No error, but an empty row.
    (
        r"\begin{aligned} & a + b \narrowsep \\ & c \end{aligned}",
        r"\narrowsep at the end of a row",
    ),
    (
        r"\begin{aligned} & a + b \narrowbreak \end{aligned}",
        r"\narrowbreak at the end of a row",
    ),
    (
        r"\begin{aligned} & \narrowsep a + b \end{aligned}",
        r"\narrowsep at the start of a row",
    ),
    (
        r"\begin{alignedat}[t]{1} & \narrowsep a \end{alignedat}",
        r"\narrowsep at the start of a row",
    ),
    (
        r"\begin{aligned} & a \narrowbreak \narrowbreak + b \end{aligned}",
        r"\narrowbreak next to another mark",
    ),
    (
        r"\begin{aligned} & a \narrowsep \label{eq:b} \narrowsep b \end{aligned}",
        r"\narrowsep next to another mark",
    ),
    # No error, but the new row does not start with a relation or a binary operator.
    (r"\begin{aligned} & a \narrowbreak b \end{aligned}", r"\narrowbreak before b"),
    (r"\begin{aligned} & \sin \narrowbreak x \end{aligned}", r"\narrowbreak before x"),
    (
        r"\begin{aligned} & \frac{a}{b} \narrowbreak \frac{c}{d} \end{aligned}",
        r"\narrowbreak before \frac",
    ),
    (
        r"\begin{aligned} & a \narrowbreak \cdots + b \end{aligned}",
        r"\narrowbreak before \cdots",
    ),
    (
        r"\begin{aligned} & a \narrowbreak \, + b \end{aligned}",
        r"\narrowbreak before \,",
    ),
    (
        r"\begin{aligned} & \left( a \right. \narrowbreak \left. + b \right) \end{aligned}",
        r"\narrowbreak before \left",
    ),
]

# The rule each kind of misplaced mark breaks, as the build states it.
MISPLACED_MARK_MESSAGES = [
    (
        r"a \narrowsep b",
        r"\narrowsep outside an environment: a mark must stand in aligned, alignedat "
        "or split",
    ),
    (
        r"\begin{aligned} & {a \narrowbreak + b} \end{aligned}",
        r"\narrowbreak inside braces: a row cannot end inside braces or between \left "
        r"and \right",
    ),
    (
        r"\begin{aligned} a \narrowsep b \end{aligned}",
        r"\narrowsep with no & before it in its row: a mark must stand after its row's "
        "first & and before its second",
    ),
    (
        r"\begin{aligned} & a \narrowsep \end{aligned}",
        r"\narrowsep at the end of a row: it would leave an empty row on a narrow "
        "screen",
    ),
    (
        r"\begin{aligned} & a \narrowbreak b \end{aligned}",
        r"\narrowbreak before b: \narrowbreak must come right before a relation or "
        "binary operator, such as = or +",
    ),
]


def display(tex: str) -> str:
    """Wrap TeX as the Markdown step emits a display equation."""
    return f'<div class="arithmatex">\\[{tex}\\]</div>\n'


def inline(tex: str) -> str:
    """Wrap TeX as the Markdown step emits inline math."""
    return f'<span class="arithmatex">\\({tex}\\)</span>'


def on_a_narrow_screen(tex: str) -> str:
    """Give each mark of `tex` its definition for a narrow screen."""
    for name, definition in NARROW_SCREEN_MACROS.items():
        tex = tex.replace(f"\\{name}", definition)
    return tex


def make_page(name: str, body_html: str, **fields: Any) -> Page:
    fields.setdefault("kind", "chapter")
    fields.setdefault("number", "1")
    return Page(
        source_path=Path(f"{name}.md"),
        url=f"{name}/",
        meta={},
        body_md="",
        body_html=body_html,
        **fields,
    )


def make_section(chapter: Page, name: str, body_html: str, number: str) -> Page:
    return make_page(
        name,
        body_html,
        kind="section",
        number=number,
        chapter=chapter,
        counters=chapter.counters,
    )


@pytest.mark.parametrize(("tex", "expected"), NUMBERED_FORMS)
def test_numbers_follow_mathjax(tex: str, expected: list[str]) -> None:
    numbers = ["#" if row.counted else row.tag for row in equation_rows(tex)]
    assert [number for number in numbers if number] == expected


@pytest.mark.parametrize(("tex", "expected"), LABEL_FORMS)
def test_labels_follow_mathjax(tex: str, expected: list[str]) -> None:
    rows = equation_rows(tex)
    labels = [row.label for row in rows if row.label and (row.counted or row.tag)]
    assert labels == expected


def where(found: MisplacedMark | None) -> str:
    """Name a misplaced mark and where it stands."""
    return f"{found.mark} {found.place}" if found else ""


@pytest.mark.parametrize("tex", MARK_FORMS)
def test_a_mark_in_its_place_is_accepted(tex: str) -> None:
    assert misplaced_mark(tex) is None


@pytest.mark.parametrize("tex", MARK_FORMS)
def test_a_mark_in_its_place_changes_no_number_on_a_narrow_screen(tex: str) -> None:
    # A narrow screen reads the mark as a new row, and the mark's environment takes
    # no number of its own whatever its rows.
    narrow_tex = on_a_narrow_screen(tex)
    assert r"\\ &" in narrow_tex
    assert equation_rows(narrow_tex) == equation_rows(tex)


def test_a_mark_stands_in_an_environment_without_numbers_of_its_own() -> None:
    assert set(MARK_ENVIRONMENTS) < INNER_ENVIRONMENTS


@pytest.mark.parametrize(("tex", "expected"), MISPLACED_MARK_FORMS)
def test_a_misplaced_mark_is_found_with_its_place(tex: str, expected: str) -> None:
    assert where(misplaced_mark(tex)) == expected


@pytest.mark.parametrize(("tex", "expected"), MISPLACED_MARK_MESSAGES)
def test_a_misplaced_mark_states_the_rule_it_breaks(tex: str, expected: str) -> None:
    assert str(misplaced_mark(tex)) == expected


@pytest.mark.parametrize(
    "tex",
    [r"a \narrowsep b", r"\begin{aligned} & a \narrowbreak + b \end{aligned}"],
    ids=["outside an environment", "in aligned"],
)
def test_no_mark_stands_in_inline_math(tex: str) -> None:
    found = misplaced_mark(tex, inline=True)
    assert found and found.place == "in inline math"
    assert found.rule == "only a display equation breaks"


@pytest.mark.parametrize(
    "tex",
    [
        "x % \\narrowsep\n",
        r"x \narrowseparator",
        r"\begin{cases} a \\narrowsep \end{cases}",
    ],
    ids=["comment", "longer name", "after a row end"],
)
def test_text_that_is_no_mark_is_left_alone(tex: str) -> None:
    assert misplaced_mark(tex) is None


def test_the_first_misplaced_mark_is_the_one_reported() -> None:
    tex = r"\begin{aligned} & a \narrowsep {b \narrowbreak} \end{aligned} \narrowsep c"
    assert where(misplaced_mark(tex)) == r"\narrowbreak inside braces"


def test_a_misplaced_mark_stops_the_build_and_names_its_page() -> None:
    tex = r"\begin{aligned} & \frac{a \narrowbreak + b}{c} \end{aligned}"
    page = make_page("book/page", display("x") + display(tex))
    message = (
        r"page\.md: \\narrowbreak inside braces: a row cannot end inside braces or "
        r"between \\left and \\right$"
    )
    with pytest.raises(BuildError, match=message):
        number_equations(page, {})


@pytest.mark.parametrize(
    ("body", "place"),
    [
        (inline(r"a \narrowsep b"), "in inline math"),
        (display(r"a &#92;narrowsep b"), "outside an environment"),
    ],
    ids=["inline math", "escaped backslash"],
)
def test_a_misplaced_mark_is_found_wherever_mathjax_reads_it(
    body: str, place: str
) -> None:
    with pytest.raises(BuildError, match=rf"page\.md: \\narrowsep {place}: "):
        number_equations(make_page("page", body), {})


def test_a_mark_in_its_place_leaves_the_page_and_the_count_as_they_were() -> None:
    # The page escapes the & and the <, which MathJax reads as an & and a relation.
    aligned = r"\begin{aligned} &amp; a \narrowbreak &lt; b \end{aligned}"
    body = display(aligned + r" \label{eq:a}") + f"<p>{inline('x')}</p>"
    page = make_page("page", body)
    labels: dict[str, tuple[Page, str]] = {}
    number_equations(page, labels)
    assert page.body_html == body
    assert labels == {"eq:a": (page, "1.1")}
    assert page.counters["equation"] == 1


def test_count_runs_through_section_pages() -> None:
    chapter = make_page("opener", display(r"x \label{a}"), number="2")
    rows = display(r"\begin{align} a \\ b \label{b} \end{align}")
    first = make_section(chapter, "first", rows, "2.1")
    second_body = display(r"x \notag") + display(r"y \label{c}")
    second = make_section(chapter, "second", second_body, "2.2")
    labels: dict[str, tuple[Page, str]] = {}
    for page in (chapter, first, second):
        number_equations(page, labels)
    assert [p.equation_offset for p in (chapter, first, second)] == [0, 1, 3]
    assert labels == {"a": (chapter, "2.1"), "b": (first, "2.3"), "c": (second, "2.4")}


def test_each_chapter_counts_from_one() -> None:
    one = make_page("one", display("x"))
    two = make_page("two", display(r"y \label{a}"), number="2")
    labels: dict[str, tuple[Page, str]] = {}
    number_equations(one, labels)
    number_equations(two, labels)
    assert two.equation_offset == 0
    assert labels["a"] == (two, "2.1")


def test_page_outside_a_chapter_has_no_prefix() -> None:
    page = make_page("home", display(r"x \label{a}"), kind="home", number="")
    labels: dict[str, tuple[Page, str]] = {}
    number_equations(page, labels)
    assert labels["a"] == (page, "1")


def test_manual_tag_keeps_its_text_and_skips_the_count() -> None:
    page = make_page("page", display(r"x \tag{A} \label{a}") + display(r"y \label{b}"))
    labels: dict[str, tuple[Page, str]] = {}
    number_equations(page, labels)
    assert labels == {"a": (page, "A"), "b": (page, "1.1")}


def test_escaped_tex_is_read_as_written() -> None:
    body = display(r"\begin{align} a &amp;&lt; b \\ c &amp;= d \end{align}")
    page = make_page("page", body)
    number_equations(page, {})
    assert page.counters["equation"] == 2


def test_repeated_label_fails() -> None:
    labels: dict[str, tuple[Page, str]] = {}
    number_equations(make_page("one", display(r"x \label{a}")), labels)
    with pytest.raises(BuildError, match=r"two\.md: equation label a .* one\.md"):
        number_equations(make_page("two", display(r"y \label{a}")), labels)


@pytest.fixture
def chapter() -> Page:
    return make_page("book/chapter", display(r"x \label{eq:a}"))


@pytest.fixture
def other() -> Page:
    return make_page("book/other", "", number="2")


@pytest.fixture
def labels(chapter: Page, other: Page) -> dict[str, tuple[Page, str]]:
    return {"eq:a": (chapter, "1.1"), "eq b": (other, "2.3")}


def test_reference_on_the_same_page_stays_with_mathjax(
    chapter: Page, labels: dict[str, tuple[Page, str]]
) -> None:
    body = chapter.body_html + inline(r"\eqref{eq:a}")
    chapter.body_html = body
    resolve_equation_refs(chapter, labels)
    assert chapter.body_html == body


def test_reference_to_another_page_becomes_a_link(
    other: Page, labels: dict[str, tuple[Page, str]]
) -> None:
    other.body_html = inline(r"\eqref{eq:a}")
    resolve_equation_refs(other, labels)
    link = r"\href{../../book/chapter/#mjx-eqn:eq:a}{\text{(1.1)}}"
    assert other.body_html == inline(link)


def test_plain_ref_prints_no_parentheses(
    other: Page, labels: dict[str, tuple[Page, str]]
) -> None:
    other.body_html = inline(r"\ref{eq:a}")
    resolve_equation_refs(other, labels)
    assert r"{\text{1.1}}" in other.body_html


def test_reference_inside_a_display_equation(
    other: Page, labels: dict[str, tuple[Page, str]]
) -> None:
    other.body_html = display(r"x = \eqref{eq:a}")
    resolve_equation_refs(other, labels)
    assert r"\href{../../book/chapter/#mjx-eqn:eq:a}" in other.body_html


def test_spaces_in_a_label_become_underscores_in_the_anchor(
    chapter: Page, labels: dict[str, tuple[Page, str]]
) -> None:
    chapter.body_html = inline(r"\eqref{eq b}")
    resolve_equation_refs(chapter, labels)
    assert "#mjx-eqn:eq_b}" in chapter.body_html


def test_bare_reference_on_the_same_page_stays_with_mathjax(
    chapter: Page, labels: dict[str, tuple[Page, str]]
) -> None:
    body = chapter.body_html + r"<p>See \eqref{eq:a} and \ref {eq:a}.</p>"
    chapter.body_html = body
    resolve_equation_refs(chapter, labels)
    assert chapter.body_html == body


def test_bare_reference_to_another_page_becomes_a_link(
    other: Page, labels: dict[str, tuple[Page, str]]
) -> None:
    other.body_html = r"<p>See \eqref{eq:a} and \ref{eq:a}.</p>"
    resolve_equation_refs(other, labels)
    link = r"\href{../../book/chapter/#mjx-eqn:eq:a}"
    with_parentheses = inline(link + r"{\text{(1.1)}}")
    number_alone = inline(link + r"{\text{1.1}}")
    assert other.body_html == f"<p>See {with_parentheses} and {number_alone}.</p>"


def test_bare_reference_beside_math_and_tags(
    other: Page, labels: dict[str, tuple[Page, str]]
) -> None:
    link = inline(r"\href{../../book/chapter/#mjx-eqn:eq:a}{\text{(1.1)}}")
    other.body_html = f'<p>{inline("x")} in <a href="a/">\\eqref{{eq:a}}</a></p>'
    resolve_equation_refs(other, labels)
    assert other.body_html == f'<p>{inline("x")} in <a href="a/">{link}</a></p>'


@pytest.mark.parametrize(
    "body",
    [
        r"<p><code>\eqref{eq:missing}</code></p>",
        r'<div class="highlight"><pre><code>\eqref{eq:missing}</code></pre></div>',
        r'<p><a href="a/" title="x > 0 in \eqref{eq:missing}">text</a></p>',
        r"<!-- don't cite \eqref{eq:missing} yet -->",
        r"<p>Write it as \\eqref{eq:missing}.</p>",
    ],
    ids=["inline code", "code block", "attribute", "comment", "escaped backslash"],
)
def test_reference_mathjax_does_not_read_is_left_alone(
    body: str, chapter: Page, labels: dict[str, tuple[Page, str]]
) -> None:
    chapter.body_html = body
    resolve_equation_refs(chapter, labels)
    assert chapter.body_html == body


@pytest.mark.parametrize(
    "body",
    [inline(r"\eqref{eq:missing}"), r"<p>See \eqref{eq:missing}.</p>"],
    ids=["in math", "bare"],
)
def test_unknown_label_fails(
    body: str, chapter: Page, labels: dict[str, tuple[Page, str]]
) -> None:
    chapter.body_html = body
    with pytest.raises(
        BuildError, match=r"chapter\.md: \\eqref\{eq:missing\} matches no"
    ):
        resolve_equation_refs(chapter, labels)


@pytest.mark.parametrize(
    "text",
    [
        r"<p>\(x\)</p>",
        r"<div>\[x\]</div>",
        r"<div>\begin{align}x\end{align}</div>",
        r"\begin {align}",
        r"see \eqref{eq:a}",
        r"see \ref {eq:a}",
        r"two \\ backslashes",
        r"a \$ sign",
        "&#92;(x",
    ],
)
def test_text_that_mathjax_acts_on_needs_it(text: str) -> None:
    assert needs_mathjax(text)


@pytest.mark.parametrize(
    "text",
    [
        "<p>Plain text with $x$ and $$y$$.</p>",
        r"<p>C:\dir and \alpha</p>",
        r"<code>\(x\)</code>",
        r'<pre class="a">\[x\]</pre>',
        "",
    ],
)
def test_text_that_mathjax_leaves_alone_does_not_need_it(text: str) -> None:
    assert not needs_mathjax(text)
