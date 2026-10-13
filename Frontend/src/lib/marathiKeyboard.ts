/**
 * The Marathi (Devanagari InScript) keyboard layout, the one built into Windows,
 * Android and iOS as "Marathi". Keys are named by their physical position
 * (KeyboardEvent.code), so it types the same whatever layout the computer is set to.
 */

export interface KeyDef {
  /** KeyboardEvent.code of the physical key, e.g. "KeyQ". */
  code: string;
  /** What the key types, without and with Shift. */
  normal: string;
  shift: string;
}

const k = (code: string, normal: string, shift: string): KeyDef => ({ code, normal, shift });

export const MARATHI_ROWS: KeyDef[][] = [
  [
    k("Digit1", "१", "ऍ"), k("Digit2", "२", "ॅ"), k("Digit3", "३", "्र"), k("Digit4", "४", "र्"),
    k("Digit5", "५", "ज्ञ"), k("Digit6", "६", "त्र"), k("Digit7", "७", "क्ष"), k("Digit8", "८", "श्र"),
    k("Digit9", "९", "("), k("Digit0", "०", ")"), k("Minus", "-", "ः"), k("Equal", "ृ", "ऋ"),
  ],
  [
    k("KeyQ", "ौ", "औ"), k("KeyW", "ै", "ऐ"), k("KeyE", "ा", "आ"), k("KeyR", "ी", "ई"),
    k("KeyT", "ू", "ऊ"), k("KeyY", "ब", "भ"), k("KeyU", "ह", "ङ"), k("KeyI", "ग", "घ"),
    k("KeyO", "द", "ध"), k("KeyP", "ज", "झ"), k("BracketLeft", "ड", "ढ"), k("BracketRight", "़", "ञ"),
  ],
  [
    k("KeyA", "ो", "ओ"), k("KeyS", "े", "ए"), k("KeyD", "्", "अ"), k("KeyF", "ि", "इ"),
    k("KeyG", "ु", "उ"), k("KeyH", "प", "फ"), k("KeyJ", "र", "ऱ"), k("KeyK", "क", "ख"),
    k("KeyL", "त", "थ"), k("Semicolon", "च", "छ"), k("Quote", "ट", "ठ"), k("Backslash", "ॉ", "ऑ"),
  ],
  [
    k("KeyZ", "ॆ", "ऎ"), k("KeyX", "ं", "ँ"), k("KeyC", "म", "ण"), k("KeyV", "न", "ऩ"),
    k("KeyB", "व", "ऴ"), k("KeyN", "ल", "ळ"), k("KeyM", "स", "श"), k("Comma", ",", "ष"),
    k("Period", ".", "।"), k("Slash", "य", "य़"),
  ],
];

const BY_CODE = new Map<string, KeyDef>(MARATHI_ROWS.flat().map((key) => [key.code, key]));

/** The character a physical key types in Marathi mode, or null if it is not a Marathi key. */
export function marathiCharFor(code: string, shift: boolean): string | null {
  const key = BY_CODE.get(code);
  if (!key) return null;
  return shift ? key.shift : key.normal;
}

/** Characters the keyboard offers on top of the layout: the joiner lets a conjunct be broken or formed by hand. */
export const EXTRA_CHARACTERS = ["ॐ", "॥", "‍", "‌"];

/** Inserts `text` over the current selection of an input or textarea. Pure, so it is testable. */
export function insertAt(
  value: string,
  selectionStart: number,
  selectionEnd: number,
  text: string
): { value: string; caret: number } {
  const start = Math.max(0, Math.min(selectionStart, value.length));
  const end = Math.max(start, Math.min(selectionEnd, value.length));
  return { value: value.slice(0, start) + text + value.slice(end), caret: start + text.length };
}

/** Removes the selection, or the character before the caret when nothing is selected. */
export function deleteBack(
  value: string,
  selectionStart: number,
  selectionEnd: number
): { value: string; caret: number } {
  if (selectionEnd > selectionStart) return insertAt(value, selectionStart, selectionEnd, "");
  if (selectionStart === 0) return { value, caret: 0 };
  // Step back over a whole code point (Devanagari letters are single code points,
  // but a joiner or an emoji-like pair must not be cut in half).
  const before = Array.from(value.slice(0, selectionStart));
  before.pop();
  const kept = before.join("");
  return { value: kept + value.slice(selectionStart), caret: kept.length };
}
