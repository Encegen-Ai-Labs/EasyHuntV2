import { describe, expect, it } from "vitest";
import { splitBlocks, toPlainText } from "./textBlocks";

describe("splitBlocks", () => {
  it("keeps a real table and turns <br> inside a cell into a space", () => {
    const blocks = splitBlocks("Intro\n| Survey | Owner |\n| --- | --- |\n| 12/3 | Ramesh<br>Patil |\nOutro");
    expect(blocks).toEqual([
      { type: "text", text: "Intro" },
      { type: "table", columns: ["Survey", "Owner"], rows: [["12/3", "Ramesh Patil"]] },
      { type: "text", text: "Outro" },
    ]);
  });

  it("rejoins a row that a <br> split across lines", () => {
    const blocks = splitBlocks("| A | B |\n| - | - |\n| 1 | two<br> three |");
    expect(blocks[0]).toMatchObject({ type: "table", rows: [["1", "two three"]] });
  });

  it("removes stray pipes and turns <br> outside a table into a line break", () => {
    expect(splitBlocks("Owner | Ramesh<br>Plot 12")).toEqual([{ type: "text", text: "Owner Ramesh\nPlot 12" }]);
  });

  it("does not treat two unrelated pipe lines as a table", () => {
    expect(splitBlocks("a | b | c\nonly | one").every((b) => b.type === "text")).toBe(true);
  });

  it("handles empty input and keeps the Devanagari danda", () => {
    expect(splitBlocks(null)).toEqual([]);
    expect(splitBlocks("हे खरे आहे ।")).toEqual([{ type: "text", text: "हे खरे आहे ।" }]);
  });

  it("flattens to plain text", () => {
    expect(toPlainText(splitBlocks("x\n| A | B |\n| - | - |\n| 1 | 2 |"))).toBe("x\n\nA  B\n1  2");
  });
});
