"use client";

import React, { useRef } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { HighlightedText } from "@/components/search/HighlightedText";

interface SelectableTextProps {
  text: string;
  query: string;
  /** Called with the selected substring, or null if nothing valid was selected. */
  onAddSelection: (selectedText: string | null) => void;
  addLabel?: string;
  disabled?: boolean;
}

// Characters that end a word — a selection boundary landing mid-word expands
// outward until it hits one of these (or the start/end of the text node).
const WORD_BOUNDARY = /[\s.,;:!?"'()[\]{}]/;

/** Widens a Range's start/end so a boundary that landed mid-word snaps out to
 * the whole word, instead of requiring the reviewer to drag pixel-perfectly
 * onto word edges. Only walks within the start/end text node itself (not
 * across sibling nodes) — the common case of a mouse-drag selection within
 * one paragraph/snippet, which is what this is for. */
function expandRangeToWordBoundaries(range: Range): Range {
  const expanded = range.cloneRange();
  const { startContainer, endContainer } = range;
  let { startOffset, endOffset } = range;

  if (startContainer.nodeType === Node.TEXT_NODE) {
    const text = startContainer.textContent || "";
    while (startOffset > 0 && !WORD_BOUNDARY.test(text[startOffset - 1])) {
      startOffset--;
    }
    expanded.setStart(startContainer, startOffset);
  }

  if (endContainer.nodeType === Node.TEXT_NODE) {
    const text = endContainer.textContent || "";
    while (endOffset < text.length && !WORD_BOUNDARY.test(text[endOffset])) {
      endOffset++;
    }
    expanded.setEnd(endContainer, endOffset);
  }

  return expanded;
}

/** Renders highlighted text plus an "add selection" button. The lawyer selects a
 * span with the mouse (browser text selection) — a boundary landing mid-word
 * snaps out to the whole word on each end — then clicks the button to send
 * that (widened) span to the report builder, not the whole block. */
export function SelectableText({ text, query, onAddSelection, addLabel = "Add selection to report", disabled }: SelectableTextProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  function handleAddClick() {
    const selection = window.getSelection();
    const anchorNode = selection?.anchorNode;

    // Only accept a selection that's actually inside this block, and not
    // just a collapsed cursor position — otherwise clicking "Add selection"
    // after selecting text elsewhere on the page (or not selecting at all)
    // would silently attach the wrong text, or an unintended nearby word.
    if (
      !selection ||
      selection.rangeCount === 0 ||
      selection.isCollapsed ||
      !anchorNode ||
      !containerRef.current ||
      !containerRef.current.contains(anchorNode)
    ) {
      onAddSelection(null);
      return;
    }

    const expandedRange = expandRangeToWordBoundaries(selection.getRangeAt(0));
    const selectedText = expandedRange.toString().trim();
    onAddSelection(selectedText || null);
  }

  return (
    <div className="flex flex-col gap-2">
      <div ref={containerRef} className="whitespace-pre-wrap leading-relaxed">
        <HighlightedText text={text} query={query} />
      </div>
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={handleAddClick}
        disabled={disabled}
        className="w-fit gap-1.5 text-xs"
      >
        <Plus size={12} />
        {addLabel}
      </Button>
    </div>
  );
}
