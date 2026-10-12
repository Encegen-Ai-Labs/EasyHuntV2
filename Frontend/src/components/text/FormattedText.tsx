import React from "react";
import { splitBlocks } from "@/lib/textBlocks";
import { HighlightedText } from "@/components/search/HighlightedText";
import { cn } from "@/lib/utils";

interface FormattedTextProps {
  text: string;
  /** A search phrase to highlight (phrase first, then its words). */
  query?: string;
  /** Exact words to highlight, e.g. the ones the lawyer picked on the search screen. */
  words?: string[];
  className?: string;
}

/** Shows transcribed text the way the document reads: paragraphs as paragraphs
 * and tables as real tables, with no `|` or `<br>` leaking through. Highlights
 * apply inside table cells too. */
export function FormattedText({ text, query = "", words, className }: FormattedTextProps) {
  const blocks = splitBlocks(text);
  if (blocks.length === 0) return null;

  const mark = (value: string) => <HighlightedText text={value} query={query} words={words} />;

  return (
    <div className={cn("flex flex-col gap-3 leading-relaxed", className)}>
      {blocks.map((block, index) =>
        block.type === "text" ? (
          <p key={index} className="whitespace-pre-wrap">{mark(block.text)}</p>
        ) : (
          <div key={index} className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full border-collapse text-left text-sm">
              <thead className="bg-muted/50">
                <tr>
                  {block.columns.map((cell, i) => (
                    <th key={i} className="border-b border-border px-3 py-1.5 font-semibold">{mark(cell)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {block.rows.map((row, r) => (
                  <tr key={r} className="odd:bg-background even:bg-muted/20">
                    {row.map((cell, c) => (
                      <td key={c} className="border-t border-border px-3 py-1.5 align-top">{mark(cell)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
    </div>
  );
}
