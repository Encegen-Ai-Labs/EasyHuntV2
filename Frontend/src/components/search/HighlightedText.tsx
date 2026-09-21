import React from "react";

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

interface HighlightedTextProps {
  text: string;
  query: string;
}

/** Wraps every case-insensitive occurrence of `query` in `text` with <mark>. */
export function HighlightedText({ text, query }: HighlightedTextProps) {
  const trimmedQuery = query.trim();
  if (!trimmedQuery) return <>{text}</>;

  const parts = text.split(new RegExp(`(${escapeRegExp(trimmedQuery)})`, "gi"));

  return (
    <>
      {parts.map((part, i) =>
        part.toLowerCase() === trimmedQuery.toLowerCase() ? (
          <mark key={i} className="rounded bg-yellow-300/70 px-0.5 text-foreground dark:bg-yellow-500/40">
            {part}
          </mark>
        ) : (
          <React.Fragment key={i}>{part}</React.Fragment>
        )
      )}
    </>
  );
}
