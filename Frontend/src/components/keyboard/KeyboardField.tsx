"use client";

import * as React from "react";
import { Keyboard, X, Delete, ArrowBigUp } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { EXTRA_CHARACTERS, MARATHI_ROWS, deleteBack, insertAt, marathiCharFor } from "@/lib/marathiKeyboard";

type Field = HTMLInputElement | HTMLTextAreaElement;

/** Puts new text into a field the way typing would, so React's onChange (and react-hook-form) still fire. */
function writeToField(el: Field, value: string, caret: number) {
  const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, "value")?.set?.call(el, value);
  el.dispatchEvent(new Event("input", { bubbles: true }));
  el.setSelectionRange(caret, caret);
}

function insertText(el: Field | null, text: string) {
  if (!el) return;
  el.focus();
  const result = insertAt(el.value, el.selectionStart ?? el.value.length, el.selectionEnd ?? el.value.length, text);
  writeToField(el, result.value, result.caret);
}

function backspace(el: Field | null) {
  if (!el) return;
  el.focus();
  const result = deleteBack(el.value, el.selectionStart ?? el.value.length, el.selectionEnd ?? el.value.length);
  writeToField(el, result.value, result.caret);
}

/** The small Latin letter printed on each key, so someone typing on a real keyboard can find the key. */
function keyHint(code: string): string {
  if (code.startsWith("Key")) return code.slice(3);
  if (code.startsWith("Digit")) return code.slice(5);
  const punctuation: Record<string, string> = {
    Minus: "-", Equal: "=", BracketLeft: "[", BracketRight: "]", Semicolon: ";",
    Quote: "'", Backslash: "\\", Comma: ",", Period: ".", Slash: "/",
  };
  return punctuation[code] ?? "";
}

function KeyboardPanel({
  target,
  physical,
  onPhysicalChange,
  onClose,
}: {
  target: Field | null;
  physical: boolean;
  onPhysicalChange: (value: boolean) => void;
  onClose: () => void;
}) {
  const [shift, setShift] = React.useState(false);

  // Keeps the cursor in the field: a button press must not steal focus or drop the selection.
  const keep = (e: React.MouseEvent) => e.preventDefault();
  const keyClass =
    "relative flex h-9 min-w-8 flex-1 items-center justify-center rounded-md border border-border bg-background text-base font-medium shadow-xs transition-colors hover:bg-accent active:bg-primary active:text-primary-foreground";

  function type(text: string) {
    insertText(target, text);
    setShift(false);
  }

  return (
    <div
      role="group"
      aria-label="Marathi keyboard"
      className="mt-2 flex flex-col gap-1.5 rounded-lg border border-border bg-muted/40 p-2"
      onMouseDown={keep}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 px-0.5 text-xs text-muted-foreground">
        <span className="font-medium text-foreground">मराठी keyboard</span>
        <label className="flex cursor-pointer items-center gap-1.5">
          <input
            type="checkbox"
            checked={physical}
            onChange={(e) => onPhysicalChange(e.target.checked)}
            className="size-3.5"
          />
          Type Marathi with my keyboard too
        </label>
        <button
          type="button"
          onClick={onClose}
          className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-medium hover:bg-accent hover:text-foreground"
        >
          <X size={12} /> Close
        </button>
      </div>

      {MARATHI_ROWS.map((row, rowIndex) => (
        <div key={rowIndex} className="flex gap-1" style={{ paddingLeft: `${rowIndex * 0.6}rem` }}>
          {row.map((key) => (
            <button
              key={key.code}
              type="button"
              className={keyClass}
              onClick={() => type(shift ? key.shift : key.normal)}
              aria-label={`${shift ? key.shift : key.normal} (key ${keyHint(key.code)})`}
            >
              <span className="pointer-events-none absolute left-1 top-0.5 text-[9px] font-normal uppercase leading-none text-muted-foreground/70">
                {keyHint(key.code)}
              </span>
              {/* The dotted circle keeps a lone vowel sign (a matra) visible instead of vanishing. */}
              {(() => {
                const ch = shift ? key.shift : key.normal;
                return /^[ऺ-ॏ॑-ॗऀ-ः़]/.test(ch) ? `◌${ch}` : ch;
              })()}
            </button>
          ))}
        </div>
      ))}

      <div className="flex gap-1">
        <button
          type="button"
          onClick={() => setShift((s) => !s)}
          aria-pressed={shift}
          className={cn(keyClass, "flex-none gap-1 px-3 text-xs", shift && "border-primary bg-primary/10 text-primary")}
        >
          <ArrowBigUp size={14} /> Shift
        </button>
        {EXTRA_CHARACTERS.slice(0, 2).map((ch) => (
          <button key={ch} type="button" className={cn(keyClass, "flex-none px-3")} onClick={() => type(ch)}>
            {ch}
          </button>
        ))}
        <button type="button" className={cn(keyClass, "flex-[4]")} onClick={() => type(" ")} aria-label="Space">
          <span className="text-xs text-muted-foreground">space</span>
        </button>
        <button
          type="button"
          className={cn(keyClass, "flex-none px-3")}
          onClick={() => type("‍")}
          title="Zero-width joiner: keeps or breaks a joined letter"
          aria-label="Zero-width joiner"
        >
          <span className="text-[10px]">ZWJ</span>
        </button>
        <button type="button" className={cn(keyClass, "flex-none px-4")} onClick={() => backspace(target)} aria-label="Backspace">
          <Delete size={15} />
        </button>
      </div>
    </div>
  );
}

/** Shared behaviour for KeyboardInput and KeyboardTextarea. */
function useKeyboardField<T extends Field>(externalKeyDown: React.KeyboardEventHandler<T> | undefined) {
  // The element is kept in state (not a ref) so the keyboard panel can be handed it while rendering.
  const [element, setElement] = React.useState<T | null>(null);
  const [open, setOpen] = React.useState(false);
  const [physical, setPhysical] = React.useState(true);

  const onKeyDown = (e: React.KeyboardEvent<T>) => {
    externalKeyDown?.(e);
    if (e.defaultPrevented || !open || !physical) return;
    if (e.ctrlKey || e.altKey || e.metaKey || e.nativeEvent.isComposing) return;
    const ch = marathiCharFor(e.code, e.shiftKey);
    if (!ch) return;
    e.preventDefault();
    insertText(element, ch);
  };

  const toggleButton = (
    <button
      type="button"
      onClick={() => {
        setOpen((value) => !value);
        element?.focus();
      }}
      aria-pressed={open}
      aria-label={open ? "Close Marathi keyboard" : "Open Marathi keyboard"}
      title={open ? "Close Marathi keyboard" : "Type in Marathi (मराठी)"}
      className={cn(
        "inline-flex size-7 items-center justify-center rounded-md text-xs font-semibold transition-colors",
        open ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground"
      )}
    >
      {open ? <Keyboard size={14} /> : <span aria-hidden="true">अ</span>}
    </button>
  );

  const panel = open ? (
    <KeyboardPanel target={element} physical={physical} onPhysicalChange={setPhysical} onClose={() => setOpen(false)} />
  ) : null;

  return { setElement, onKeyDown, toggleButton, panel, open };
}

type KeyboardInputProps = Omit<React.ComponentProps<"input">, "ref"> & {
  wrapperClassName?: string;
  /** An icon drawn inside the left edge of the field (the field needs its own left padding, e.g. pl-8). */
  leadingIcon?: React.ReactNode;
};

/** A text input with a Marathi keyboard button. Drop-in for <Input>. */
export function KeyboardInput({ onKeyDown, className, wrapperClassName, leadingIcon, ...props }: KeyboardInputProps) {
  const { setElement, onKeyDown: handleKeyDown, toggleButton, panel, open } = useKeyboardField<HTMLInputElement>(onKeyDown);
  return (
    <div className={cn("w-full", wrapperClassName)}>
      <div className="relative">
        {leadingIcon}
        <Input {...props} ref={setElement} onKeyDown={handleKeyDown} lang={open ? "mr" : props.lang} className={cn("pr-10", className)} />
        <span className="absolute right-1 top-1/2 -translate-y-1/2">{toggleButton}</span>
      </div>
      {panel}
    </div>
  );
}

type KeyboardTextareaProps = Omit<React.ComponentProps<"textarea">, "ref"> & { wrapperClassName?: string };

/** A textarea with a Marathi keyboard button. Drop-in for <textarea>. */
export function KeyboardTextarea({ onKeyDown, className, wrapperClassName, ...props }: KeyboardTextareaProps) {
  const { setElement, onKeyDown: handleKeyDown, toggleButton, panel, open } = useKeyboardField<HTMLTextAreaElement>(onKeyDown);
  return (
    <div className={cn("w-full", wrapperClassName)}>
      <div className="relative">
        <textarea {...props} ref={setElement} onKeyDown={handleKeyDown} lang={open ? "mr" : props.lang} className={cn("pr-10", className)} />
        <span className="absolute right-1 top-1 ">{toggleButton}</span>
      </div>
      {panel}
    </div>
  );
}
