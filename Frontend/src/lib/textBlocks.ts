/**
 * Turns transcribed page text into paragraph and table blocks for display.
 *
 * The backend already strips `<br>` and stray `|` characters when text is
 * extracted (backend/app/services/text_cleanup.py). This is the same rule set
 * applied again at display time, so text stored before that change still reads
 * cleanly. A run of pipe lines counts as a table only when it has at least two
 * rows and either a dashed separator row or the same number of pipes on every
 * line; any other `|` is removed.
 */

export type TextBlock =
  | { type: "text"; text: string }
  | { type: "table"; columns: string[]; rows: string[][] };

const BR = /<\s*\/?\s*br\s*\/?\s*>/gi;
const NBSP = /&nbsp;| /gi;
const SEPARATOR_ROW = /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$/;

function pipeCount(line: string): number {
  return (line.match(/\|/g) ?? []).length;
}

function isTableLine(line: string): boolean {
  const trimmed = line.trim();
  return pipeCount(trimmed) >= 2 || (trimmed.length > 1 && trimmed.startsWith("|") && trimmed.endsWith("|"));
}

function isTableRun(lines: string[]): boolean {
  if (lines.length < 2) return false;
  if (lines.some((l) => SEPARATOR_ROW.test(l) && l.includes("-"))) return true;
  const counts = new Set(lines.map((l) => pipeCount(l.trim())));
  return counts.size === 1 && Math.min(...counts) >= 2;
}

function cleanProseLine(line: string): string {
  return line.replace(NBSP, " ").replace(/[ \t]*\|[ \t]*/g, " ").replace(/[ \t]{2,}/g, " ").trimEnd();
}

function cells(line: string): string[] {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => c.trim());
}

export function splitBlocks(input: string | null | undefined): TextBlock[] {
  if (!input) return [];

  // A <br> inside a table row splits it across lines; rejoin the pieces.
  const merged: string[] = [];
  for (const line of input.replace(BR, "\n").split("\n")) {
    const previous = merged[merged.length - 1];
    const previousOpen = previous !== undefined && previous.trim().startsWith("|") && !previous.trim().endsWith("|");
    if (previousOpen && !line.trim().startsWith("|")) {
      merged[merged.length - 1] = `${previous} ${line.trim()}`;
    } else {
      merged.push(line);
    }
  }

  const blocks: TextBlock[] = [];
  let prose: string[] = [];
  const flush = () => {
    const joined = prose.join("\n").replace(/\n[ \t]*\n[ \t]*\n+/g, "\n\n").replace(/^\n+|\n+$/g, "");
    if (joined.trim()) blocks.push({ type: "text", text: joined });
    prose = [];
  };

  let i = 0;
  while (i < merged.length) {
    if (!isTableLine(merged[i])) {
      prose.push(cleanProseLine(merged[i]));
      i++;
      continue;
    }
    let end = i;
    while (end < merged.length && isTableLine(merged[end])) end++;
    const run = merged.slice(i, end);
    if (isTableRun(run)) {
      flush();
      const rows = run.filter((l) => !SEPARATOR_ROW.test(l)).map((l) => cells(l.replace(NBSP, " ")));
      const width = Math.max(...rows.map((r) => r.length));
      const padded = rows.map((r) => [...r, ...Array(width - r.length).fill("")]);
      blocks.push({ type: "table", columns: padded[0], rows: padded.slice(1) });
    } else {
      prose.push(...run.map(cleanProseLine));
    }
    i = end;
  }
  flush();
  return blocks;
}

/** The text with tables flattened to one line per row, for places that can only show plain text. */
export function toPlainText(blocks: TextBlock[]): string {
  return blocks
    .map((b) =>
      b.type === "text" ? b.text : [b.columns, ...b.rows].map((row) => row.join("  ")).join("\n")
    )
    .join("\n\n");
}
