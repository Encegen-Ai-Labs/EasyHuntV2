"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronUp, FileText, Loader2, Search, Sparkles } from "lucide-react";
import { apiClient, type DocumentPageRecord, type SearchMode, type SearchResult } from "@/services/api/client";
import { useToast } from "@/context/ToastContext";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { HighlightedText } from "@/components/search/HighlightedText";
import { SelectableText } from "@/components/search/SelectableText";

interface CaseSearchPanelProps {
  caseId: string;
  /** Called after an excerpt is successfully added, so the host page can nudge
   * the lawyer toward the report builder. */
  onExcerptAdded?: () => void;
}

interface ExpandedPageState {
  loading: boolean;
  page?: DocumentPageRecord;
  error?: string;
}

export function CaseSearchPanel({ caseId, onExcerptAdded }: CaseSearchPanelProps) {
  const toast = useToast();
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>("exact");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [expanded, setExpanded] = useState<Record<string, ExpandedPageState>>({});

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;

    setIsSearching(true);
    setHasSearched(true);
    setSubmittedQuery(trimmed);
    setExpanded({});

    const result = await apiClient.search.searchCase(caseId, trimmed, mode);
    setResults(result.success && result.data ? result.data.results : []);
    setIsSearching(false);
  }

  async function toggleExpand(documentId: string, pageNumber: number) {
    const key = `${documentId}-${pageNumber}`;
    const wasOpen = Boolean(expanded[key]);

    setExpanded((prev) => {
      if (prev[key]) {
        const next = { ...prev };
        delete next[key];
        return next;
      }
      return { ...prev, [key]: { loading: true } };
    });

    if (wasOpen) return;

    const result = await apiClient.documents.getPages(documentId);
    const page = result.success ? result.data?.pages.find((p) => p.page_number === pageNumber) : undefined;

    setExpanded((prev) =>
      prev[key]
        ? { ...prev, [key]: { loading: false, page, error: result.success ? undefined : result.error } }
        : prev
    );
  }

  async function handleAddExcerpt(documentId: string, pageNumber: number, selectedText: string | null) {
    if (!selectedText) {
      toast.warning("Select some text in the page first, then click “Add selection”.", "Nothing Selected");
      return;
    }

    const result = await apiClient.reportBuilder.addExcerpt(caseId, {
      document_id: documentId,
      page_number: pageNumber,
      excerpt_text: selectedText,
    });

    if (result.success) {
      toast.success("Excerpt added to the report.", "Added");
      onExcerptAdded?.();
    } else {
      toast.error(result.error || "Failed to add excerpt", "Error");
    }
  }

  const grouped = results.reduce<Record<string, { documentName?: string; results: SearchResult[] }>>((acc, r) => {
    if (!acc[r.document_id]) acc[r.document_id] = { documentName: r.document_name, results: [] };
    acc[r.document_id].results.push(r);
    return acc;
  }, {});

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={handleSearch} className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-8"
            placeholder="Search across this case's documents…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <Button type="submit" disabled={isSearching || !query.trim()}>
          {isSearching ? <Loader2 size={16} className="animate-spin" /> : "Search"}
        </Button>
      </form>

      <div className="flex items-center gap-1 text-xs">
        <span className="text-muted-foreground">Match:</span>
        <Button
          type="button"
          size="sm"
          variant={mode === "exact" ? "secondary" : "ghost"}
          className="h-7 px-2.5 text-xs"
          onClick={() => setMode("exact")}
        >
          Exact
        </Button>
        <Button
          type="button"
          size="sm"
          variant={mode === "semantic" ? "secondary" : "ghost"}
          className="h-7 px-2.5 text-xs"
          onClick={() => setMode("semantic")}
        >
          <Sparkles size={12} data-icon="inline-start" />
          Similar meaning
        </Button>
      </div>

      {isSearching && (
        <div className="flex items-center justify-center gap-2 py-8 text-xs text-muted-foreground">
          <Loader2 size={14} className="animate-spin" />
          Searching…
        </div>
      )}

      {!isSearching && hasSearched && results.length === 0 && (
        <p className="py-6 text-center text-xs text-muted-foreground">
          No matches for &ldquo;{submittedQuery}&rdquo;.
        </p>
      )}

      {!isSearching && results.length > 0 && (
        <div className="flex flex-col gap-4">
          {Object.entries(grouped).map(([documentId, group]) => (
            <div key={documentId} className="rounded-xl border border-border">
              <div className="flex items-center gap-2 border-b bg-muted/30 px-3 py-2 text-xs font-semibold">
                <FileText size={14} className="text-primary" />
                <span className="truncate">{group.documentName || documentId}</span>
                <Badge variant="outline" className="ml-auto shrink-0 text-[10px]">
                  {group.results.length} match{group.results.length === 1 ? "" : "es"}
                </Badge>
              </div>
              <ul className="divide-y divide-border">
                {group.results.map((r, i) => {
                  const key = `${r.document_id}-${r.page_number}`;
                  const expandedState = expanded[key];
                  return (
                    <li key={`${key}-${r.matched_in}-${i}`} className="px-3 py-2.5 text-xs">
                      <button
                        type="button"
                        onClick={() => toggleExpand(r.document_id, r.page_number)}
                        className="flex w-full items-center justify-between gap-2 text-left"
                      >
                        <span className="flex items-center gap-2">
                          <Badge variant="outline" className="text-[10px] font-bold">
                            Page {r.page_number}
                          </Badge>
                          {r.matched_in === "semantic" ? (
                            <span className="flex items-center gap-1 text-muted-foreground">
                              <Sparkles size={11} />
                              {typeof r.similarity === "number" ? `${Math.round(r.similarity * 100)}% match` : "similar meaning"}
                            </span>
                          ) : (
                            <span className="text-muted-foreground">
                              {r.matched_in === "original" ? "original language" : "English"}
                            </span>
                          )}
                        </span>
                        {expandedState ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      </button>

                      <p className="mt-1.5 leading-relaxed text-foreground/90">
                        <HighlightedText text={r.snippet} query={submittedQuery} />
                      </p>

                      {expandedState && (
                        <div className="mt-2 rounded-lg border border-border bg-muted/20 p-3">
                          {expandedState.loading ? (
                            <div className="flex items-center gap-2 text-muted-foreground">
                              <Loader2 size={12} className="animate-spin" />
                              Loading full page…
                            </div>
                          ) : expandedState.error ? (
                            <p className="text-destructive">{expandedState.error}</p>
                          ) : (
                            <div className="flex flex-col gap-4">
                              <div>
                                <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                                  Original language
                                </p>
                                <SelectableText
                                  text={expandedState.page?.original_text || ""}
                                  query={submittedQuery}
                                  onAddSelection={(text) => handleAddExcerpt(r.document_id, r.page_number, text)}
                                />
                              </div>
                              <div>
                                <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                                  English
                                </p>
                                <SelectableText
                                  text={expandedState.page?.english_text || ""}
                                  query={submittedQuery}
                                  onAddSelection={(text) => handleAddExcerpt(r.document_id, r.page_number, text)}
                                />
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
