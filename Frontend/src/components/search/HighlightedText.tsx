import React from "react";

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

interface HighlightedTextProps {
  text: string;
  query: string;
  highlightFallback?: boolean;
}

/** Wraps every case-insensitive occurrence of `query` in `text` with <mark>. */
export function HighlightedText({ text, query, highlightFallback = false }: HighlightedTextProps) {
  const trimmedQuery = query.trim();
  if (!trimmedQuery) return <>{text}</>;

  const terms = [...new Set(trimmedQuery.match(/[\p{L}\p{M}\p{N}]+/gu) ?? [trimmedQuery])];
  if (terms.length === 0) return <>{text}</>;
  const termSet = new Set(terms.map((term) => term.toLocaleLowerCase()));
  const matcher = new RegExp(`(${terms.sort((a, b) => b.length - a.length).map(escapeRegExp).join("|")})`, "giu");
  const parts = text.split(matcher);
  const hasLiteralMatch = parts.some((part) => termSet.has(part.toLocaleLowerCase()));

  if (highlightFallback && !hasLiteralMatch) {
    return (
      <mark className="rounded bg-violet-300/60 px-0.5 text-foreground dark:bg-violet-500/30">
        {text}
      </mark>
    );
  }

  return (
    <>
      {parts.map((part, i) =>
        termSet.has(part.toLocaleLowerCase()) ? (
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
