import assert from "node:assert/strict";
import { test } from "node:test";
import { BAR_THEMES, DEFAULT_BAR_THEME, isBarTheme, resolveBarTheme } from "./barthemes.ts";

test("the three top bar themes, in the settings' order, with Deep field the default (David, 9 Nov 2026)", () => {
  assert.deepEqual(BAR_THEMES.map((t) => t.id), ["deep-field", "line-clear", "ground-drift"]);
  assert.deepEqual(BAR_THEMES.map((t) => t.name), ["Deep field", "Line clear", "Ground drift"]);
  assert.equal(DEFAULT_BAR_THEME, "deep-field");
  for (const t of BAR_THEMES) assert.ok(t.description.endsWith("."));
});

test("no saved theme, an empty one or an unknown one is the default, so a theme can be retired without a migration", () => {
  for (const value of [null, undefined, "", "neon-rain", 3]) assert.equal(resolveBarTheme(value), "deep-field");
  assert.equal(resolveBarTheme("line-clear"), "line-clear");
  assert.equal(isBarTheme("ground-drift"), true);
  assert.equal(isBarTheme("Ground drift"), false);
});
