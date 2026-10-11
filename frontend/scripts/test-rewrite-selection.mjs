import assert from "node:assert/strict";
import { test } from "node:test";
import { fromUtf16, wholeParagraph } from "../src/features/rewriting/selection.ts";

test("selection after an emoji uses code-point offsets", () => {
  const text = "Mira 🕯️ entered the library.";
  const start = text.indexOf("entered");
  assert.deepEqual(fromUtf16(text, start, start + 7), {start: 8, end: 15, original_text: "entered"});
});
test("emoji selection preserves the full surrogate pair", () => {
  assert.deepEqual(fromUtf16("a😀b", 1, 3), {start: 1, end: 2, original_text: "😀"});
  assert.equal(fromUtf16("a😀b", 1, 2), null);
  assert.equal(fromUtf16("a😀b", 2, 3), null);
});
test("combining marks and whole paragraphs preserve exact text", () => {
  const text = "e\u0301 😀\nnext";
  assert.deepEqual(wholeParagraph(text), {start: 0, end: 9, original_text: text});
  assert.deepEqual(fromUtf16(text, 0, 2), {start: 0, end: 2, original_text: "e\u0301"});
});
test("empty, reversed, fractional and outside ranges are rejected", () => {
  for (const [start,end] of [[0,0],[2,1],[-1,2],[0,9],[0.2,1]]) assert.equal(fromUtf16("abc", start,end),null);
});
