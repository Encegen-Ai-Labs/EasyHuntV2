import { describe, expect, it } from "vitest";
import { MARATHI_ROWS, deleteBack, insertAt, marathiCharFor } from "./marathiKeyboard";

describe("Marathi keyboard layout", () => {
  it("types common letters from their InScript positions", () => {
    expect(marathiCharFor("KeyK", false)).toBe("क");
    expect(marathiCharFor("KeyK", true)).toBe("ख");
    expect(marathiCharFor("KeyE", false)).toBe("ा");
    expect(marathiCharFor("KeyN", true)).toBe("ळ"); // used in Marathi place names
    expect(marathiCharFor("KeyD", false)).toBe("्"); // halant, to join letters
  });

  it("types Devanagari digits", () => {
    expect(marathiCharFor("Digit1", false)).toBe("१");
    expect(marathiCharFor("Digit0", false)).toBe("०");
  });

  it("ignores keys that are not part of the layout", () => {
    expect(marathiCharFor("Enter", false)).toBeNull();
    expect(marathiCharFor("Space", false)).toBeNull();
    expect(marathiCharFor("ArrowLeft", false)).toBeNull();
  });

  it("has no two keys with the same position", () => {
    const codes = MARATHI_ROWS.flat().map((key) => key.code);
    expect(new Set(codes).size).toBe(codes.length);
  });

  it("builds the word 'दिनांक' from keys", () => {
    const keys: [string, boolean][] = [["KeyO", false], ["KeyF", false], ["KeyV", false], ["KeyE", false], ["KeyX", false], ["KeyK", false]];
    expect(keys.map(([code, shift]) => marathiCharFor(code, shift)).join("")).toBe("दिनांक");
  });
});

describe("inserting and deleting", () => {
  it("inserts at the caret", () => {
    expect(insertAt("ab", 1, 1, "X")).toEqual({ value: "aXb", caret: 2 });
  });
  it("replaces a selection", () => {
    expect(insertAt("abcd", 1, 3, "X")).toEqual({ value: "aXd", caret: 2 });
  });
  it("clamps a caret past the end", () => {
    expect(insertAt("ab", 9, 9, "X")).toEqual({ value: "abX", caret: 3 });
  });
  it("backspaces one character", () => {
    expect(deleteBack("कख", 2, 2)).toEqual({ value: "क", caret: 1 });
  });
  it("backspaces a selection", () => {
    expect(deleteBack("abcd", 1, 3)).toEqual({ value: "ad", caret: 1 });
  });
  it("does nothing at the start", () => {
    expect(deleteBack("ab", 0, 0)).toEqual({ value: "ab", caret: 0 });
  });
});
