import { describe, expect, it } from "vitest";
import { highlightSegments, queryTerms } from "./highlight";

const marked = (text: string, query: string, fallback = false) =>
  highlightSegments(text, query, fallback).segments.filter((s) => s.match).map((s) => s.text);

describe("highlightSegments", () => {
  it("highlights the whole phrase when it occurs, case-insensitively", () => {
    const result = highlightSegments("The Sale Deed was signed. A deed of gift followed.", "sale deed");
    expect(result.mode).toBe("phrase");
    expect(marked("The Sale Deed was signed. A deed of gift followed.", "sale deed")).toEqual(["Sale Deed"]);
  });

  it("falls back to individual words when the phrase is not contiguous", () => {
    const text = "Deed executed for sale of plot";
    expect(highlightSegments(text, "sale deed").mode).toBe("terms");
    expect(marked(text, "sale deed")).toEqual(["Deed", "sale"]);
  });

  it("treats regex characters in the query literally", () => {
    expect(marked("Survey No. (45) and 45+", "(45)")).toEqual(["(45)"]);
    expect(() => highlightSegments("a", "[")).not.toThrow();
  });

  it("returns the text unmarked for an empty or non-matching query", () => {
    expect(highlightSegments("abc", "   ").mode).toBe("none");
    expect(highlightSegments("abc", "xyz").mode).toBe("none");
  });

  it("skips single-letter words when other words are present", () => {
    expect(queryTerms("a deed")).toEqual(["deed"]);
    expect(queryTerms("a")).toEqual(["a"]);
    expect(marked("a plot and the deed", "a deed")).toEqual(["deed"]);
  });

  it("marks the whole passage for a similar result with no literal match", () => {
    const text = "Ownership of the property was conveyed.";
    const result = highlightSegments(text, "sale deed", true);
    expect(result.mode).toBe("passage");
    expect(result.segments).toEqual([{ text, match: true }]);
    // ...but only when asked: exact results never shade a passage.
    expect(highlightSegments(text, "sale deed", false).mode).toBe("none");
  });

  it("prefers literal word matches over passage shading for similar results", () => {
    expect(highlightSegments("Sale of the plot", "sale deed", true).mode).toBe("terms");
  });
});

describe("highlightSegments with Marathi and Hindi", () => {
  it("highlights a whole Marathi phrase", () => {
    const text = "दस्त नोंदणी दिनांक १२/०३/२०१० रोजी झाला.";
    expect(marked(text, "नोंदणी दिनांक")).toEqual(["नोंदणी दिनांक"]);
  });

  it("highlights each Marathi word whole, never cutting a word at a vowel sign", () => {
    const text = "तारीख आणि नोंदणी क्रमांक";
    const result = highlightSegments(text, "नोंदणी तारीख");
    expect(result.mode).toBe("terms");
    expect(marked(text, "नोंदणी तारीख")).toEqual(["तारीख", "नोंदणी"]);
  });

  it("highlights Hindi words", () => {
    const text = "विक्रय पत्र के अनुसार भूमि का स्वामित्व हस्तांतरित हुआ";
    expect(marked(text, "स्वामित्व हस्तांतरित")).toEqual(["स्वामित्व हस्तांतरित"]);
    expect(marked(text, "भूमि स्वामित्व")).toEqual(["भूमि", "स्वामित्व"]);
  });

  it("matches words that differ only in Unicode normalization (nukta)", () => {
    // U+0958 (precomposed QA) vs U+0915 U+093C (KA + NUKTA): visually identical.
    const composedInText = "कीमत क़बर";
    const decomposedQuery = "क़";
    expect(marked(composedInText, decomposedQuery)).toHaveLength(1);
  });

  it("keeps a word containing a zero-width joiner in one piece", () => {
    const word = "कर्‍मा";
    expect(queryTerms(`${word} दस्त`)).toContain(word);
  });

  it("shades the passage when an English query matches a Marathi similar result", () => {
    const text = "सदर मिळकत विक्री करारानुसार हस्तांतरित झाली.";
    const result = highlightSegments(text, "sale deed", true);
    expect(result.mode).toBe("passage");
  });

  it("does not match across scripts for exact results", () => {
    expect(highlightSegments("नोंदणी", "registration").mode).toBe("none");
  });
});
