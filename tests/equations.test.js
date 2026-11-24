/* Tests for the parts of equations.js that need no browser. */
"use strict";

const assert = require("node:assert/strict");
const { test } = require("node:test");
const equations = require("../src/bookspine/static/equations.js");

test("an equation that fits its box keeps its size", () => {
  assert.equal(equations.fitScale(600, 600), 1);
  assert.equal(equations.fitScale(600, 420), 1);
});

test("an equation with no width, as in a closed box, keeps its size", () => {
  assert.equal(equations.fitScale(0, 0), 1);
});

test("an equation wider than its box is drawn a hair smaller than their ratio", () => {
  const scale = equations.fitScale(343, 428);
  assert.equal(scale, (343 / 428) * equations.FIT_MARGIN);
  assert.ok(428 * scale < 343);
});

test("an equation is drawn no smaller than the smallest scale", () => {
  assert.equal(equations.fitScale(343, 343 / equations.MIN_SCALE + 1), equations.MIN_SCALE);
  assert.equal(equations.fitScale(343, 2000), equations.MIN_SCALE);
});

test("an equation that fits at the smallest scale or larger does not overflow", () => {
  assert.equal(equations.overflows(288, 288), false);
  assert.equal(equations.overflows(288, 380), false);
  assert.equal(equations.overflows(288, 288 / equations.MIN_SCALE), false);
});

test("an equation still wider than its box at the smallest scale overflows", () => {
  assert.equal(equations.overflows(288, 288 / equations.MIN_SCALE + 1), true);
  assert.equal(equations.overflows(288, 426), true);
});

test("an equation with no width, as in a closed box, does not overflow", () => {
  assert.equal(equations.overflows(0, 0), false);
});

test("each macro is redefined in TeX, an empty definition included", () => {
  assert.equal(
    equations.redefinitions({ narrowbreak: "\\\\ & \\quad {}", narrowsep: "\\\\ &" }),
    "\\renewcommand{\\narrowbreak}{\\\\ & \\quad {}}\\renewcommand{\\narrowsep}{\\\\ &}",
  );
  assert.equal(equations.redefinitions({ narrowbreak: "" }), "\\renewcommand{\\narrowbreak}{}");
});

test("a macro is found by its whole name", () => {
  assert.equal(equations.usesMacro("a \\narrowbreak + b", ["narrowbreak", "narrowsep"]), true);
  assert.equal(equations.usesMacro("a ,\\narrowsep b", ["narrowbreak", "narrowsep"]), true);
  assert.equal(equations.usesMacro("a \\narrowbreaks b", ["narrowbreak"]), false);
  assert.equal(equations.usesMacro("a narrowbreak b", ["narrowbreak"]), false);
});
