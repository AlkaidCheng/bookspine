/* Tests for the colour scheme button of book.js, which need no browser. */
"use strict";

const assert = require("node:assert/strict");
const { test } = require("node:test");
const theme = require("../src/bookspine/static/book.js");

test("the first click from the system's scheme changes the colours", () => {
  assert.equal(theme.nextThemeChoice("system", false), "dark");
  assert.equal(theme.nextThemeChoice("system", true), "light");
});

test("the button keeps the system's scheme second and follows the system third", () => {
  for (const systemIsDark of [false, true]) {
    const seen = ["system"];
    for (let step = 0; step < 3; step += 1) {
      seen.push(theme.nextThemeChoice(seen[seen.length - 1], systemIsDark));
    }
    const systemScheme = systemIsDark ? "dark" : "light";
    const otherScheme = systemIsDark ? "light" : "dark";
    assert.deepEqual(seen, ["system", otherScheme, systemScheme, "system"]);
  }
});

test("a kept scheme the system has since moved away from leads back to the system", () => {
  assert.equal(theme.nextThemeChoice("dark", false), "light");
  assert.equal(theme.nextThemeChoice("light", false), "system");
});

test("the system choice takes the system's scheme and a kept one stays", () => {
  assert.equal(theme.themeScheme("system", true), "dark");
  assert.equal(theme.themeScheme("system", false), "light");
  assert.equal(theme.themeScheme("light", true), "light");
  assert.equal(theme.themeScheme("dark", false), "dark");
});

test("the label names the choice and what the next click does", () => {
  assert.equal(
    theme.themeLabel("system", true),
    "Following the system's colour scheme. Switch to light.",
  );
  assert.equal(theme.themeLabel("dark", true), "Dark colour scheme. Follow the system.");
});
