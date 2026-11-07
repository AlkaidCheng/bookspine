"""Tests for turning Markdown into the HTML the later passes read."""

import random
import re

import pytest

from bookspine.converter import convert_markdown

# What Python-Markdown and pymdown-extensions gave for each source, which the adapters
# keep. Only whitespace between tags may differ.
REFERENCE_OUTPUT = {
    "\\begin{align}\na &= b \\\\\nc &< d\n\\end{align}\n": '<div class="arithmatex">\\[\\begin{align}\na &amp;= b \\\\\nc &amp;&lt; d\n\\end{align}\\]</div>',
    "Text\n\n\\begin{equation}\nx\n\\end{equation}\n\nMore\n": '<p>Text</p>\n<div class="arithmatex">\\[\\begin{equation}\nx\n\\end{equation}\\]</div>\n<p>More</p>',
    "\\[\nx < y\n\\]\n": '<div class="arithmatex">\\[\nx &lt; y\n\\]</div>',
    "\\[ x \\]\n": '<div class="arithmatex">\\[ x \\]</div>',
    "Inline \\(a < b\\) and \\(c\\).\n": '<p>Inline <span class="arithmatex">\\(a &lt; b\\)</span> and <span class="arithmatex">\\(c\\)</span>.</p>',
    "`\\(not\\)` and \\(yes\\)\n": '<p><code>\\(not\\)</code> and <span class="arithmatex">\\(yes\\)</span></p>',
    'HTML and `HTML` and XHTML.\n\n*[HTML]: Hyper "Text" Markup\n': '<p><abbr title="Hyper &quot;Text&quot; Markup">HTML</abbr> and <code>HTML</code> and XHTML.</p>',
    "The W3C said.\n\n*[W3C]: World\n*[HTML]: x\n": '<p>The <abbr title="World">W3C</abbr> said.</p>',
    "$HTML$ HTML [HTML](a.md)\n\n*[HTML]: H\n": '<p><span class="arithmatex">\\(HTML\\)</span> <abbr title="H">HTML</abbr> <a href="a.md"><abbr title="H">HTML</abbr></a></p>',
    "## HTML\n\n*[HTML]: H\n": '<h2 id="html"><abbr title="H">HTML</abbr></h2>',
    "Text\n{: .x #y }\n": '<p class="x" id="y">Text</p>',
    'Text\n{: .a .b data-k="v" }\n': '<p class="a b" data-k="v">Text</p>',
    "One\nTwo\n{: #z }\n": '<p id="z">One\nTwo</p>',
    "Run `#!python x = 1` now\n": '<p>Run <code class="highlight"><span class="n">x</span> <span class="o">=</span> <span class="mi">1</span></code> now</p>',
    "`#!not-a-lang x`\n": '<p><code class="highlight">x</code></p>',
    "`#!python` alone\n": "<p><code>#!python</code> alone</p>",
    "`:::python x = 1`\n": '<p><code class="highlight"><span class="n">x</span> <span class="o">=</span> <span class="mi">1</span></code></p>',
    '```python title="a.py"\nx = 1\n```\n': '<div class="highlight"><span class="filename">a.py</span><pre><span></span><code><span class="n">x</span> <span class="o">=</span> <span class="mi">1</span>\n</code></pre></div>',
    '```python hl_lines="2"\nx = 1\ny = 2\nz = 3\n```\n': '<div class="highlight"><pre><span></span><code><span class="n">x</span> <span class="o">=</span> <span class="mi">1</span>\n<span class="hll"><span class="n">y</span> <span class="o">=</span> <span class="mi">2</span>\n</span><span class="n">z</span> <span class="o">=</span> <span class="mi">3</span>\n</code></pre></div>',
    '```python hl_lines="1 3-4"\na\nb\nc\nd\n```\n': '<div class="highlight"><pre><span></span><code><span class="hll"><span class="n">a</span>\n</span><span class="n">b</span>\n<span class="hll"><span class="n">c</span>\n</span><span class="hll"><span class="n">d</span>\n</span></code></pre></div>',
    '```python linenums="1"\nx = 1\ny = 2\n```\n': '<div class="highlight"><table class="highlighttable"><tr><td class="linenos"><div class="linenodiv"><pre><span></span><span class="normal">1</span>\n<span class="normal">2</span></pre></div></td><td class="code"><div><pre><span></span><code><span class="n">x</span> <span class="o">=</span> <span class="mi">1</span>\n<span class="n">y</span> <span class="o">=</span> <span class="mi">2</span>\n</code></pre></div></td></tr></table></div>',
    '```python linenums="5" hl_lines="1" title="t"\nx = 1\ny = 2\n```\n': '<div class="highlight"><table class="highlighttable"><tr><th colspan="2" class="filename"><span class="filename">t</span></th></tr><tr><td class="linenos"><div class="linenodiv"><pre><span></span><span class="normal">5</span>\n<span class="normal">6</span></pre></div></td><td class="code"><div><pre><span></span><code><span class="hll"><span class="n">x</span> <span class="o">=</span> <span class="mi">1</span>\n</span><span class="n">y</span> <span class="o">=</span> <span class="mi">2</span>\n</code></pre></div></td></tr></table></div>',
    '```title="plain"\nx\n```\n': '<div class="highlight"><span class="filename">plain</span><pre><span></span><code>x\n</code></pre></div>',
    "A[^1] and B[^n].\n\n[^1]: One\n[^n]: Two\n    more\n\n    para\n": '<p>A<sup id="fnref:1"><a class="footnote-ref" href="#fn:1">1</a></sup> and B<sup id="fnref:n"><a class="footnote-ref" href="#fn:n">2</a></sup>.</p>\n<div class="footnote">\n<hr />\n<ol>\n<li id="fn:1">\n<p>One&#160;<a class="footnote-backref" href="#fnref:1" title="Back to text">&#8617;</a></p>\n</li>\n<li id="fn:n">\n<p>Two\nmore</p>\n<p>para&#160;<a class="footnote-backref" href="#fnref:n" title="Back to text">&#8617;</a></p>\n</li>\n</ol>\n</div>',
    "B[^b] then A[^a].\n\n[^a]: Aye\n[^b]: Bee\n": '<p>B<sup id="fnref:b"><a class="footnote-ref" href="#fn:b">2</a></sup> then A<sup id="fnref:a"><a class="footnote-ref" href="#fn:a">1</a></sup>.</p>\n<div class="footnote">\n<hr />\n<ol>\n<li id="fn:a">\n<p>Aye&#160;<a class="footnote-backref" href="#fnref:a" title="Back to text">&#8617;</a></p>\n</li>\n<li id="fn:b">\n<p>Bee&#160;<a class="footnote-backref" href="#fnref:b" title="Back to text">&#8617;</a></p>\n</li>\n</ol>\n</div>',
    "Twice[^1] again[^1].\n\n[^1]: One\n": '<p>Twice<sup id="fnref:1"><a class="footnote-ref" href="#fn:1">1</a></sup> again<sup id="fnref2:1"><a class="footnote-ref" href="#fn:1">1</a></sup>.</p>\n<div class="footnote">\n<hr />\n<ol>\n<li id="fn:1">\n<p>One&#160;<a class="footnote-backref" href="#fnref:1" title="Back to text">&#8617;</a><a class="footnote-backref" href="#fnref2:1" title="Back to text">&#8617;</a></p>\n</li>\n</ol>\n</div>',
    "Missing[^x].\n": "<p>Missing[^x].</p>",
    "Unused.\n\n[^u]: Note\n": '<p>Unused.</p>\n<div class="footnote">\n<hr />\n<ol>\n<li id="fn:u">\n<p>Note&#160;<a class="footnote-backref" href="#fnref:u" title="Back to text">&#8617;</a></p>\n</li>\n</ol>\n</div>',
    "`[^1]` A[^1]\n\n[^1]: One\n": '<p><code>[^1]</code> A<sup id="fnref:1"><a class="footnote-ref" href="#fn:1">1</a></sup></p>\n<div class="footnote">\n<hr />\n<ol>\n<li id="fn:1">\n<p>One&#160;<a class="footnote-backref" href="#fnref:1" title="Back to text">&#8617;</a></p>\n</li>\n</ol>\n</div>',
    "!!! note\n    In box[^1]\n\n[^1]: One\n": '<div class="admonition note">\n<p class="admonition-title">Note</p>\n<p>In box<sup id="fnref:1"><a class="footnote-ref" href="#fn:1">1</a></sup></p>\n</div>\n<div class="footnote">\n<hr />\n<ol>\n<li id="fn:1">\n<p>One&#160;<a class="footnote-backref" href="#fnref:1" title="Back to text">&#8617;</a></p>\n</li>\n</ol>\n</div>',
    "Press ++ctrl+alt+delete++ now\n": '<p>Press <span class="keys"><kbd class="key-control">Ctrl</kbd><span>+</span><kbd class="key-alt">Alt</kbd><span>+</span><kbd class="key-delete">Del</kbd></span> now</p>',
    "++enter++ ++a++ ++f12++ ++page-up++ ++arrow-left++ ++cmd+s++ ++1++ ++tab++\n": '<p><span class="keys"><kbd class="key-enter">Enter</kbd></span> <span class="keys"><kbd class="key-a">A</kbd></span> <span class="keys"><kbd class="key-f12">F12</kbd></span> <span class="keys"><kbd class="key-page-up">Page Up</kbd></span> <span class="keys"><kbd class="key-arrow-left">Left</kbd></span> <span class="keys"><kbd class="key-command">Cmd</kbd><span>+</span><kbd class="key-s">S</kbd></span> <span class="keys"><kbd class="key-1">1</kbd></span> <span class="keys"><kbd class="key-tab">Tab</kbd></span></p>',
    "++foo++ and ++ctrl+foo++\n": "<p>++foo++ and ++ctrl+foo++</p>",
    "`++a++`\n": "<p><code>++a++</code></p>",
    "!!! note\n\tA box indented by a tab.\n": '<div class="admonition note">\n<p class="admonition-title">Note</p>\n<p>A box indented by a tab.</p>\n</div>',
    "```python\n\tx = 1\n```\n": '<div class="highlight"><pre><span></span><code>    <span class="n">x</span> <span class="o">=</span> <span class="mi">1</span>\n</code></pre></div>',
    "[^1]: One\n\n\tTwo\n\nA[^1]\n": '<p>A<sup id="fnref:1"><a class="footnote-ref" href="#fn:1">1</a></sup></p>\n<div class="footnote">\n<hr />\n<ol>\n<li id="fn:1">\n<p>One</p>\n<p>Two&#160;<a class="footnote-backref" href="#fnref:1" title="Back to text">&#8617;</a></p>\n</li>\n</ol>\n</div>',
    "- a\n\n\tb\n": "<ul>\n<li>\n<p>a</p>\n<p>b</p>\n</li>\n</ul>",
}


def spaced(html: str) -> str:
    return re.sub(r"\s+", " ", html).strip()


@pytest.mark.parametrize("source", sorted(REFERENCE_OUTPUT))
def test_the_adapters_keep_the_old_output(source: str) -> None:
    assert spaced(convert_markdown(source)) == spaced(REFERENCE_OUTPUT[source])


def test_a_box_holds_its_title_and_text() -> None:
    assert convert_markdown('!!! note "Careful"\n    Mind the gap.\n') == (
        '<div class="admonition note">\n<p class="admonition-title">Careful</p>\n'
        "<p>Mind the gap.</p>\n</div>"
    )


def test_a_box_without_a_title_takes_its_kind() -> None:
    assert '<p class="admonition-title">Tip</p>' in convert_markdown("!!! tip\n    A\n")


def test_an_empty_title_leaves_the_title_out() -> None:
    assert "admonition-title" not in convert_markdown('!!! note ""\n    A\n')


def test_a_box_keeps_its_extra_classes() -> None:
    assert '<div class="admonition note wide">' in convert_markdown(
        "!!! note wide\n    A\n"
    )


def test_a_box_title_reads_markdown_and_math() -> None:
    html = convert_markdown('!!! example "A *matched* $Z$ sample"\n    A\n')
    assert '<em>matched</em> <span class="arithmatex">\\(Z\\)</span>' in html


def test_a_box_ends_at_the_first_line_outside_it() -> None:
    html = convert_markdown("!!! note\n    One\n\n    Two\n\nThree\n")
    assert html.endswith("<p>Two</p>\n</div>\n<p>Three</p>")


def test_boxes_nest() -> None:
    html = convert_markdown("!!! note\n    A\n\n    !!! tip\n        B\n\nC\n")
    assert html.index("admonition note") < html.index("admonition tip")
    assert html.index("<p>B</p>") < html.index("<p>C</p>")
    assert "\ue000" not in html


def test_two_boxes_keep_their_order() -> None:
    html = convert_markdown("!!! note\n    A\n\n!!! tip\n    B\n")
    assert html.index("<p>A</p>") < html.index("<p>B</p>")


def test_a_box_can_sit_in_a_list() -> None:
    html = convert_markdown("- Item\n\n    !!! note\n        A\n")
    assert '<li>\n<p>Item</p>\n<div class="admonition note">' in html


def test_a_box_holds_code_and_lists() -> None:
    html = convert_markdown("!!! note\n    - a\n\n    ```python\n    x = 1\n    ```\n")
    assert "<li>a</li>" in html
    assert '<div class="highlight">' in html


def test_box_syntax_in_code_stays_as_code() -> None:
    html = convert_markdown("```\n!!! note\n    A\n```\n")
    assert "admonition" not in html
    assert "!!! note" in html


@pytest.mark.parametrize("marker, attribute", [("???", ""), ("???+", ' open="open"')])
def test_a_collapsible_box(marker: str, attribute: str) -> None:
    assert convert_markdown(f'{marker} note "More"\n    A\n') == (
        f'<details class="note"{attribute}>\n<summary>More</summary>\n<p>A</p>\n'
        "</details>"
    )


def test_code_takes_the_colours_of_its_language() -> None:
    html = convert_markdown("```python\nx = 1\n```\n")
    assert html.startswith('<div class="highlight"><pre><span></span><code>')
    assert '<span class="mi">1</span>' in html


@pytest.mark.parametrize("fence", ["```", "```not-a-language"])
def test_code_without_a_known_language_stays_plain(fence: str) -> None:
    html = convert_markdown(f"{fence}\na < b\n```\n")
    assert "<code>a &lt; b\n</code>" in html


def test_blank_lines_at_the_edges_of_code_stay() -> None:
    assert "<code>\na\n\n</code>" in convert_markdown("```\n\na\n\n```\n")


def test_inline_math_takes_mathjax_delimiters() -> None:
    assert convert_markdown("Energy $E = mc^2$.") == (
        '<p>Energy <span class="arithmatex">\\(E = mc^2\\)</span>.</p>'
    )


def test_display_math_is_a_block_of_its_own() -> None:
    assert convert_markdown("$$\nx \\label{eq:a}\n$$\n") == (
        '<div class="arithmatex">\\[\nx \\label{eq:a}\n\\]</div>'
    )


def test_a_dollar_in_prose_is_not_math() -> None:
    assert "arithmatex" not in convert_markdown("It costs $5 or $ 6.")


def test_math_keeps_its_backslashes() -> None:
    source = "\\frac{a}{b} \\\\ c"
    assert source in convert_markdown(f"$$\n{source}\n$$\n")


@pytest.mark.parametrize(
    "heading, anchor",
    [
        ("## A heading", "a-heading"),
        ("## It's *here*", "its-here"),
        ("## Caf\u00e9 au lait", "cafe-au-lait"),
        ("## `code` and more", "code-and-more"),
        ("## \u03b1", "_1"),
    ],
)
def test_a_heading_takes_its_anchor_from_its_text(heading: str, anchor: str) -> None:
    assert convert_markdown(heading).startswith(f'<h2 id="{anchor}">')


def test_repeated_headings_stay_unique() -> None:
    html = convert_markdown("## A\n\n## A\n\n## A\n")
    assert [f'id="{a}"' in html for a in ("a", "a_1", "a_2")] == [True, True, True]


def test_a_written_anchor_is_kept_and_counts_as_taken() -> None:
    html = convert_markdown("## One {: #two }\n\n## Two\n")
    assert '<h2 id="two">One</h2>' in html
    assert '<h2 id="two_1">Two</h2>' in html


def test_a_heading_takes_a_class() -> None:
    assert 'class="unnumbered"' in convert_markdown("## One {: .unnumbered }\n")


def test_headings_in_boxes_take_anchors_too() -> None:
    assert '<h3 id="inside">' in convert_markdown("!!! note\n    ### Inside\n")


def test_punctuation_is_set() -> None:
    assert convert_markdown('It\'s "quoted" -- and...') == (
        "<p>It\u2019s \u201cquoted\u201d \u2013 and\u2026</p>"
    )


def test_tables_and_definition_lists_are_read() -> None:
    assert "<table>" in convert_markdown("| a |\n|---|\n| b |\n")
    assert "<dd>" in convert_markdown("Term\n:   Meaning\n")


def test_lists_follow_commonmark() -> None:
    assert "<ul>\n<li>b</li>" in convert_markdown("- a\n  - b\n")
    assert convert_markdown("text\n- a\n").startswith("<p>text</p>\n<ul>")


def test_html_passes_through() -> None:
    assert '<div class="x">a</div>' in convert_markdown('<div class="x">a</div>\n')


def test_math_inside_display_math_stays_in_one_block() -> None:
    html = convert_markdown("$$\n\\begin{aligned}\na &= b\n\\end{aligned}\n$$\n")
    assert html.count('class="arithmatex"') == 1
    assert html.startswith('<div class="arithmatex">\\[\n\\begin{aligned}')


def test_an_unclosed_environment_stays_as_text() -> None:
    assert "arithmatex" not in convert_markdown("\\begin{align}\nx\n")


def test_an_environment_inside_a_paragraph_stays_as_text() -> None:
    assert "arithmatex" not in convert_markdown("Text\n\\begin{a}\nx\n\\end{a}\n")


def test_a_paragraph_of_inline_math_keeps_its_paragraph() -> None:
    assert convert_markdown("\\(x\\)\n").startswith('<p><span class="arithmatex">')


def test_the_longest_abbreviation_wins() -> None:
    html = convert_markdown("A B\n\n*[A]: One\n*[A B]: Two\n")
    assert html == '<p><abbr title="Two">A B</abbr></p>'


def test_abbreviations_stay_out_of_math_and_tags() -> None:
    html = convert_markdown("$A$ [x](A.md) A\n\n*[A]: Letter\n")
    assert html.count("<abbr") == 1
    assert 'href="A.md"' in html


def test_attributes_reach_a_list_item() -> None:
    assert '<li class="x">a</li>' in convert_markdown("- a\n{: .x }\n")


def test_attribute_values_keep_their_quotes() -> None:
    assert 'title="a b"' in convert_markdown('Text\n{: title="a b" }\n')


def test_a_quote_before_attributes_still_closes() -> None:
    assert convert_markdown('"Text"\n{: .x }\n') == (
        '<p class="x">\u201cText\u201d</p>'
    )


def test_attributes_with_nothing_to_hold_them_are_dropped() -> None:
    assert "\ue002" not in convert_markdown("| a |\n|---|\n| b |\n{: .x }\n")


@pytest.mark.parametrize("before", ["", "## Title\n"])
def test_an_attribute_line_with_no_text_before_it_stays_as_text(before: str) -> None:
    assert convert_markdown(f"{before}{{: .x }}\n").endswith("<p>{: .x }</p>")


def test_inline_code_colours_leave_code_blocks_alone() -> None:
    html = convert_markdown("```\n#!python x\n```\n")
    assert 'code class="highlight"' not in html
    assert "#!python x" in html


def test_code_options_reach_blocks_in_boxes_and_lists() -> None:
    box = '!!! note\n    ```python title="a.py"\n    x = 1\n    ```\n'
    assert '<span class="filename">a.py</span>' in convert_markdown(box)
    item = '- a\n\n    ```python hl_lines="1"\n    x = 1\n    ```\n'
    assert '<span class="hll">' in convert_markdown(item)


@pytest.mark.parametrize("options", ["", ' linenums="1"'])
def test_a_code_title_is_escaped(options: str) -> None:
    assert "a&lt;b" in convert_markdown(f'```text title="a<b"{options}\nx\n```\n')


def test_a_block_with_options_needs_no_language() -> None:
    html = convert_markdown('``` title="a.py"\nx = 1\n```\n')
    assert '<span class="filename">a.py</span>' in html
    assert "x = 1" in html


@pytest.mark.parametrize("line", ["```", "````python"])
def test_a_fence_closes_only_on_a_bare_line_as_long_as_itself(line: str) -> None:
    html = convert_markdown(f"````\n{line}\n[^1]: x\n````\n")
    assert "[^1]: x" in html
    assert "footnote" not in html


def test_a_footnote_ending_in_a_list_gets_its_own_backlink() -> None:
    html = convert_markdown("A[^1]\n\n[^1]: Note\n\n    - item\n")
    assert '</ul>\n<p>&#160;<a class="footnote-backref"' in html


def test_the_lines_after_a_footnote_may_start_a_list() -> None:
    assert "<ul>" in convert_markdown("A[^1]\n\n[^1]: Note\n    - item\n")


def test_footnotes_can_use_abbreviations_and_cite_each_other() -> None:
    html = convert_markdown("A[^1]\n\n[^1]: The W3C[^2]\n[^2]: Two\n\n*[W3C]: World\n")
    assert '<abbr title="World">W3C</abbr><sup id="fnref:2">' in html


def test_definitions_inside_code_stay_as_code() -> None:
    html = convert_markdown("```\n[^1]: x\n*[A]: y\n```\n")
    assert "[^1]: x" in html
    assert "*[A]: y" in html
    assert "footnote" not in html


@pytest.mark.parametrize("seed", range(10))
def test_no_marker_survives_any_text(seed: int) -> None:
    pieces = [
        "a ",
        "\n",
        "\n\n",
        "    ",
        "!!! note\n",
        "```\n",
        "$$\n",
        "$x$ ",
        r"\(y\) ",
        r"\[",
        r"\]",
    ]
    pieces += [
        "{: .x }\n",
        "[^a]",
        "[^a]: b\n",
        "*[a]: c\n",
        "- ",
        "\t",
        "++a++ ",
        r"\begin{b}",
        r"\end{b}",
    ]
    rng = random.Random(seed)
    for _ in range(50):
        html = convert_markdown("".join(rng.choices(pieces, k=30)))
        assert not re.search("[\ue000-\ue007]", html)


TWO_TABS = """\
=== "One"

    First.

=== "Two"

    Second.
"""


def tab_set_classes(body: str) -> list[str]:
    return re.findall(r'<div class="(tabbed-set[^"]*)">', body)


def test_tabs_in_a_row_make_one_set() -> None:
    body = convert_markdown(TWO_TABS)
    assert tab_set_classes(body) == ["tabbed-set"]
    assert re.findall(r"<label[^>]*>(.*?)</label>", body) == ["One", "Two"]
    assert "<p>First.</p>" in body
    assert "<p>Second.</p>" in body


def test_only_the_first_tab_starts_checked() -> None:
    inputs = re.findall(r"<input [^>]*>", convert_markdown(TWO_TABS))
    assert ["checked" in tab_input for tab_input in inputs] == [True, False]


def test_each_label_names_the_input_before_it() -> None:
    pairs = re.findall(
        r'id="([^"]+)"[^>]*>\n<label for="([^"]+)">', convert_markdown(TWO_TABS)
    )
    assert len(pairs) == 2
    assert all(tab_id == target for tab_id, target in pairs)


def test_tab_ids_stay_unique_across_a_page() -> None:
    body = convert_markdown(f"{TWO_TABS}\nBetween.\n\n{TWO_TABS}")
    ids = re.findall(r'<input [^>]*id="([^"]+)"', body)
    assert len(ids) == 4
    assert len(set(ids)) == 4


def test_text_between_tabs_starts_a_new_set() -> None:
    body = convert_markdown(f"{TWO_TABS}\nBetween.\n\n{TWO_TABS}")
    assert len(tab_set_classes(body)) == 2
    assert "<p>Between.</p>" in body


def test_the_text_after_a_set_stays_outside_it() -> None:
    body = convert_markdown(f"{TWO_TABS}\nAfter.\n")
    assert body.endswith("</div>\n</div>\n<p>After.</p>")


def test_a_label_reads_as_markdown() -> None:
    body = convert_markdown('=== "The `ls` tool"\n\n    Text.\n')
    assert '">The <code>ls</code> tool</label>' in body


def test_tabs_of_code_alone_make_a_card() -> None:
    body = convert_markdown(
        '=== "A"\n\n    ```text\n    a\n    ```\n\n'
        '=== "B"\n\n    ```python title="b.py"\n    b = 1\n    ```\n'
    )
    assert tab_set_classes(body) == ["tabbed-set code-card"]


def test_a_tab_with_line_numbers_still_makes_a_card() -> None:
    body = convert_markdown('=== "A"\n\n    ```python linenums="1"\n    a\n    ```\n')
    assert tab_set_classes(body) == ["tabbed-set code-card"]


@pytest.mark.parametrize(
    "panels",
    [
        '=== "A"\n\n    ```text\n    a\n    ```\n\n    Prose.\n',
        '=== "A"\n\n    ```text\n    a\n    ```\n\n=== "B"\n\n    Prose.\n',
        '=== "A"\n\n=== "B"\n',
    ],
)
def test_a_tab_with_anything_but_code_keeps_the_plain_set(panels: str) -> None:
    assert tab_set_classes(convert_markdown(panels)) == ["tabbed-set"]


def test_tabs_each_holding_a_card_make_a_switch() -> None:
    card = '    === "A"\n\n        ```text\n        a\n        ```\n'
    body = convert_markdown(f'=== "One"\n\n{card}\n=== "Two"\n\n{card}')
    assert tab_set_classes(body) == [
        "tabbed-set card-switch",
        "tabbed-set code-card",
        "tabbed-set code-card",
    ]


def test_tabs_holding_plain_sets_are_no_switch() -> None:
    body = convert_markdown('=== "One"\n\n    === "A"\n\n        Prose.\n')
    assert tab_set_classes(body) == ["tabbed-set", "tabbed-set"]


def test_a_box_can_hold_tabs_and_a_tab_a_box() -> None:
    inner_tabs = '!!! note\n\n    === "A"\n\n        Text.\n'
    assert tab_set_classes(convert_markdown(inner_tabs)) == ["tabbed-set"]
    inner_box = convert_markdown('=== "A"\n\n    !!! note\n\n        Text.\n')
    assert '<div class="tabbed-block">\n<div class="admonition note">' in inner_box


def test_a_tab_line_in_a_code_block_stays_code() -> None:
    body = convert_markdown('```text\n=== "A"\n```\n')
    assert not tab_set_classes(body)
    assert "=== " in body
