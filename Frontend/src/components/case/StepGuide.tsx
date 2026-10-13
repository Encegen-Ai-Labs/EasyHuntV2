"use client";

import { useSyncExternalStore } from "react";
import { ChevronDown, ChevronUp, Info } from "lucide-react";

const STORAGE_KEY = "easyhunt.hiddenGuides";
const listeners = new Set<() => void>();

// The saved list as a string, so React can compare snapshots by value.
function readSaved(): string {
  try {
    return window.localStorage.getItem(STORAGE_KEY) || "[]";
  } catch {
    return "[]";
  }
}

function parseHidden(saved: string): string[] {
  try {
    const parsed = JSON.parse(saved);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

// Used when storage is blocked: the choice then lasts until the page is closed.
let memoryOnly: string | null = null;

function snapshot(): string {
  return memoryOnly ?? readSaved();
}

function save(ids: string[]) {
  const value = JSON.stringify(ids);
  try {
    window.localStorage.setItem(STORAGE_KEY, value);
    memoryOnly = null;
  } catch {
    memoryOnly = value;
  }
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

interface StepGuideProps {
  /** Which page this is for; the lawyer's "hide" choice is remembered per page. */
  id: string;
  title: string;
  steps: string[];
  /** Something to be careful about, shown last. */
  note?: string;
}

/** A short "what to do on this page" panel for someone who has never used the app.
 * Open until hidden; once hidden it stays a one-line link, so it never gets in the way. */
export function StepGuide({ id, title, steps, note }: StepGuideProps) {
  // The server and the first browser render both see "[]" (guide open); the saved choice follows.
  const saved = useSyncExternalStore(subscribe, snapshot, () => "[]");
  const hidden = parseHidden(saved).includes(id);

  function toggle() {
    const others = parseHidden(snapshot()).filter((value) => value !== id);
    save(hidden ? others : [...others, id]);
  }

  if (hidden) {
    return (
      <button
        type="button"
        onClick={toggle}
        className="mb-5 inline-flex items-center gap-1.5 text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
      >
        <Info size={14} /> Show help for this page <ChevronDown size={14} />
      </button>
    );
  }

  return (
    <aside aria-label="Help for this page" className="mb-6 rounded-xl border border-primary/20 bg-primary/5 px-4 py-3.5">
      <div className="flex items-start justify-between gap-3">
        <p className="flex items-center gap-2 text-sm font-semibold">
          <Info size={15} className="text-primary" /> {title}
        </p>
        <button
          type="button"
          onClick={toggle}
          className="inline-flex shrink-0 items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          Hide <ChevronUp size={13} />
        </button>
      </div>
      <ol className="mt-2 list-decimal space-y-1 pl-9 text-sm leading-relaxed text-foreground/90 marker:text-primary">
        {steps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
      {note && <p className="mt-2 pl-6 text-sm text-muted-foreground">{note}</p>}
    </aside>
  );
}
