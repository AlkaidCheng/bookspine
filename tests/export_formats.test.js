/* Tests for the text formats of export.js, which need no browser. */
"use strict";

const assert = require("node:assert/strict");
const { test } = require("node:test");
const formats = require("../src/guidebook/static/export.js");

const plain = (text) => [{ text }];

const table = {
  header: [plain("Name"), plain("Value")],
  align: ["left", "right"],
  rows: [
    [plain("a"), plain("1")],
    [[{ text: "b", bold: true }], [{ text: "x_1", math: true }]],
  ],
  caption: plain("A caption."),
};

test("CSV quotes what needs it and ends lines with CRLF", () => {
  const quoted = {
    header: [plain("a,b")],
    align: [""],
    rows: [[plain('say "hi"')]],
  };
  assert.equal(formats.toCsv(quoted), '"a,b"\r\n"say ""hi"""\r\n');
});

test("CSV writes formulas as dollar-delimited TeX", () => {
  assert.equal(formats.toCsv(table), "Name,Value\r\na,1\r\nb,$x_1$\r\n");
});

test("Markdown writes a table with its alignment and caption", () => {
  assert.equal(
    formats.toMarkdown(table),
    "| Name | Value |\n| :--- | ---: |\n| a | 1 |\n| **b** | $x_1$ |\n\nTable: A caption.\n",
  );
});

test("Markdown escapes pipes and keeps emphasis off spaces", () => {
  const marked = {
    header: [plain("a")],
    align: [""],
    rows: [
      [[{ text: "x | y" }]],
      [[{ text: "b ", bold: true }, { text: "c" }]],
      [[{ text: "p|q", code: true }]],
      [[{ text: "tick`", code: true }]],
      [[{ text: "both", bold: true, italic: true }]],
      [[{ text: "site", href: "https://example.org" }]],
    ],
    caption: null,
  };
  assert.equal(
    formats.toMarkdown(marked),
    [
      "| a |",
      "| --- |",
      "| x \\| y |",
      "| **b** c |",
      "| `p\\|q` |",
      "| `` tick` `` |",
      "| ***both*** |",
      "| [site](https://example.org) |",
      "",
    ].join("\n"),
  );
});

test("LaTeX writes a booktabs table", () => {
  assert.equal(
    formats.toLatex(table, {}),
    [
      "% Needs \\usepackage{booktabs}",
      "\\begin{table}",
      "  \\centering",
      "  \\caption{A caption.}",
      "  \\begin{tabular}{lr}",
      "    \\toprule",
      "    Name & Value \\\\",
      "    \\midrule",
      "    a & 1 \\\\",
      "    \\textbf{b} & $x_1$ \\\\",
      "    \\bottomrule",
      "  \\end{tabular}",
      "\\end{table}",
      "",
    ].join("\n"),
  );
});

test("LaTeX escapes special characters outside formulas", () => {
  const special = {
    header: [plain("50% & a_b #1 {x} ~ ^ \\ $")],
    align: [""],
    rows: [[[{ text: "a_b", math: true }]], [[{ text: "c_d", code: true }]]],
    caption: null,
  };
  const latex = formats.toLatex(special, {});
  assert.ok(
    latex.includes(
      "50\\% \\& a\\_b \\#1 \\{x\\} \\textasciitilde{} \\textasciicircum{} \\textbackslash{} \\$ \\\\",
    ),
  );
  assert.ok(latex.includes("$a_b$ \\\\"));
  assert.ok(latex.includes("\\texttt{c\\_d} \\\\"));
});

test("LaTeX names hyperref only for a table with a link", () => {
  const linked = {
    header: [plain("a")],
    align: [""],
    rows: [[[{ text: "site", href: "https://example.org/a%20b#c" }]]],
    caption: null,
  };
  const latex = formats.toLatex(linked, {});
  assert.ok(latex.includes("% Needs \\usepackage{hyperref}"));
  assert.ok(latex.includes("\\href{https://example.org/a\\%20b\\#c}{site}"));
  assert.ok(!formats.toLatex(table, {}).includes("hyperref"));
});

test("macros are defined only when used, with their argument count", () => {
  const macros = { dd: "\\mathrm{d}", vec: ["\\boldsymbol{#1}", 1], unused: "x" };
  assert.deepEqual(formats.macroDefinitions("\\dd x + \\vec{p}", macros), [
    "\\providecommand{\\dd}{}\\renewcommand{\\dd}{\\mathrm{d}}",
    "\\providecommand{\\vec}{}\\renewcommand{\\vec}[1]{\\boldsymbol{#1}}",
  ]);
});

test("a macro name is not matched inside a longer command", () => {
  assert.deepEqual(formats.macroDefinitions("\\ddot{x}", { dd: "d" }), []);
});

test("an equation is wrapped unless it brings its own environment", () => {
  assert.equal(
    formats.equationLatex("x = 1", {}),
    "\\begin{equation}\nx = 1\n\\end{equation}\n",
  );
  const aligned = "\\begin{align} a \\\\ b \\end{align}";
  assert.equal(formats.equationLatex(aligned, {}), aligned + "\n");
  assert.ok(
    formats.equationLatex("\\begin{aligned} a \\end{aligned}", {}).startsWith(
      "\\begin{equation}",
    ),
  );
});

test("CSS variables take the page's value, then their fallback", () => {
  const lookup = (name) => ({ "--ink": "#111111" })[name] || "";
  assert.equal(
    formats.resolveVariables('fill="var(--ink, #222222)"', lookup),
    'fill="#111111"',
  );
  assert.equal(
    formats.resolveVariables("fill: var(--other, #222222);", lookup),
    "fill: #222222;",
  );
  assert.equal(formats.resolveVariables("var(--unknown)", lookup), "var(--unknown)");
});

test("names become file names", () => {
  assert.equal(formats.slug("Table 1.2"), "table-1-2");
  assert.equal(formats.slug("  Definition 3.1 "), "definition-3-1");
});

test("code files take the usual extension", () => {
  assert.equal(formats.codeExtension("python"), "py");
  assert.equal(formats.codeExtension("sql"), "sql");
  assert.equal(formats.codeExtension(""), "txt");
});
