import React from "react";
import { highlightSegments } from "@/lib/highlight";

interface HighlightedTextProps {
  text: string;
  query: string;
  /** Similar-meaning result: when no query word occurs literally, mark the
   * whole passage instead of implying a specific word matched. */
  highlightFallback?: boolean;
}

/** Highlights where `query` occurs in `text`: the whole phrase when present,
 * otherwise each query word (see lib/highlight.ts, which also handles
 * Devanagari and other Indic scripts). */
export function HighlightedText({ text, query, highlightFallback = false }: HighlightedTextProps) {
  const { segments, mode } = highlightSegments(text, query, highlightFallback);

  if (mode === "none") return <>{segments[0]?.text ?? text}</>;

  if (mode === "passage") {
    return (
      <mark className="rounded bg-violet-300/60 px-0.5 text-foreground dark:bg-violet-500/30">
        {segments[0].text}
      </mark>
    );
  }

  return (
    <>
      {segments.map((segment, i) =>
        segment.match ? (
          <mark key={i} className="rounded bg-yellow-300/70 px-0.5 text-foreground dark:bg-yellow-500/40">
            {segment.text}
          </mark>
        ) : (
          <React.Fragment key={i}>{segment.text}</React.Fragment>
        )
      )}
    </>
  );
}
