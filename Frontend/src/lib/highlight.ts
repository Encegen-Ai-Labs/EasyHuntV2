/**
 * Splits `text` into segments to highlight for a search `query`.
 *
 * Pure (no React) so it can be unit-tested, including Marathi/Hindi text.
 *
 * Strategy, most precise first:
 *  1. "phrase": the whole query occurs in the text -> highlight only that phrase.
 *  2. "terms": otherwise highlight each query word on its own. Words are runs of
 *     letters, combining marks (Devanagari vowel signs, virama, nukta, anusvara)
 *     and digits, plus ZWJ/ZWNJ, so an Indic word is never cut in the middle.
 *  3. "passage": nothing literal matched but the caller says this is a
 *     similar-meaning result -> mark the whole passage rather than imply that a
 *     particular word matched.
 *
 * Text and query are both normalized to NFC first. Indic text from OCR and from
 * typed queries often differs only in how a letter+nukta or vowel sign is
 * encoded, which would otherwise make visually identical words not match. The
 * returned segments contain the NFC form, which renders identically.
 */

export type HighlightMode = "none" | "phrase" | "terms" | "passage";

export interface HighlightSegment {
  text: string;
  match: boolean;
}

export interface HighlightResult {
  segments: HighlightSegment[];
  mode: HighlightMode;
}

const TOKEN = /[\p{L}\p{M}\p{N}‌‍]+/gu;

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function segmentsFor(text: string, matcher: RegExp): HighlightSegment[] | null {
  const segments: HighlightSegment[] = [];
  let cursor = 0;
  let found = false;
  for (const m of text.matchAll(matcher)) {
    if (m.index === undefined || m[0].length === 0) continue;
    found = true;
    if (m.index > cursor) segments.push({ text: text.slice(cursor, m.index), match: false });
    segments.push({ text: m[0], match: true });
    cursor = m.index + m[0].length;
  }
  if (!found) return null;
  if (cursor < text.length) segments.push({ text: text.slice(cursor), match: false });
  return segments;
}

export function queryTerms(query: string): string[] {
  const unique = [...new Set(query.normalize("NFC").match(TOKEN) ?? [])];
  // Single-character words ("a", Marathi "व" = "and") would light up half the
  // page, so skip them when there are other words to go on.
  const meaningful = unique.filter((term) => [...term].length > 1);
  return unique.length > 1 && meaningful.length > 0 ? meaningful : unique;
}

export function highlightSegments(text: string, query: string, passageFallback = false): HighlightResult {
  const normalizedText = text.normalize("NFC");
  const normalizedQuery = query.trim().normalize("NFC");
  if (!normalizedQuery) return { segments: [{ text: normalizedText, match: false }], mode: "none" };

  const phrase = segmentsFor(normalizedText, new RegExp(escapeRegExp(normalizedQuery), "giu"));
  if (phrase) return { segments: phrase, mode: "phrase" };

  const terms = queryTerms(normalizedQuery);
  if (terms.length > 0) {
    const alternation = [...terms].sort((a, b) => b.length - a.length).map(escapeRegExp).join("|");
    const byTerm = segmentsFor(normalizedText, new RegExp(alternation, "giu"));
    if (byTerm) return { segments: byTerm, mode: "terms" };
  }

  if (passageFallback && normalizedText.length > 0) {
    return { segments: [{ text: normalizedText, match: true }], mode: "passage" };
  }
  return { segments: [{ text: normalizedText, match: false }], mode: "none" };
}

/**
 * Splits `text` into segments, marking every whole-word occurrence of any of
 * `words` (the exact and similar words the lawyer picked on the search screen).
 * Matching is case-insensitive and NFC-normalized like highlightSegments, and a
 * word only matches as a whole word, so picking "Patil" does not mark the start
 * of "Patilwadi" (pick that word too if it is wanted).
 */
export function highlightWords(text: string, words: string[]): HighlightSegment[] {
  const normalizedText = text.normalize("NFC");
  const unique = [...new Set(words.map((w) => w.normalize("NFC").trim()).filter(Boolean))];
  if (unique.length === 0) return [{ text: normalizedText, match: false }];

  const alternation = unique.sort((a, b) => b.length - a.length).map(escapeRegExp).join("|");
  // Word edges are "not a letter, mark or digit", so Devanagari words are not cut mid-letter.
  const matcher = new RegExp(String.raw`(?<![\p{L}\p{M}\p{N}])(?:${alternation})(?![\p{L}\p{M}\p{N}])`, "giu");
  return segmentsFor(normalizedText, matcher) ?? [{ text: normalizedText, match: false }];
}
