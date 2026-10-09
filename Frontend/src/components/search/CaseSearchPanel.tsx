"use client";

import React, { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronUp, FileText, Loader2, Search, Sparkles } from "lucide-react";
import { apiClient, type DocumentPageRecord, type SearchResult } from "@/services/api/client";
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

type SearchMode = "exact" | "semantic";

/** Small bar + percentage so a weak similar match is visibly weak. */
function SimilarityIndicator({ similarity }: { similarity?: number }) {
  if (typeof similarity !== "number") {
    return <span className="text-muted-foreground">similar meaning</span>;
  }
  const percent = Math.max(0, Math.min(100, Math.round(similarity * 100)));
  return (
    <span className="flex items-center gap-1.5 text-muted-foreground" title="How close in meaning this page is to the search">
      <span
        role="meter"
        aria-label="Similarity"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        className="relative h-1.5 w-14 overflow-hidden rounded-full bg-muted"
      >
        <span className="absolute inset-y-0 left-0 rounded-full bg-violet-500" style={{ width: `${percent}%` }} />
      </span>
      <span className="tabular-nums">{percent}% similar</span>
    </span>
  );
}

export function CaseSearchPanel({ caseId, onExcerptAdded }: CaseSearchPanelProps) {
  const toast = useToast();
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  // Exact stays the default; Similar is an explicit opt-in per search.
  const [mode, setMode] = useState<SearchMode>("exact");
  const [submittedMode, setSubmittedMode] = useState<SearchMode>("exact");
  const [searchError, setSearchError] = useState<string | null>(null);
  const [similarUnavailable, setSimilarUnavailable] = useState(false);
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
    setSubmittedMode(mode);
    setSearchError(null);
    setSimilarUnavailable(false);
    setExpanded({});

    const result = await apiClient.search.searchCase(caseId, trimmed, mode);
    if (result.success && result.data) {
      setResults(result.data.results);
      setSimilarUnavailable(Boolean(result.data.similar_unavailable));
    } else {
      setResults([]);
      setSearchError(result.error || "Search failed.");
    }
    setIsSearching(false);
  }

  function selectMode(nextMode: SearchMode) {
    setMode(nextMode);
    setHasSearched(false);
    setResults([]);
    setExpanded({});
    setSearchError(null);
    setSimilarUnavailable(false);
  }

  async function toggleExpand(key: string, documentId: string, pageNumber: number) {
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

  // The backend lists exact matches first, then similar ones; the UI keeps them
  // in two separate, labelled sections rather than one mixed list.
  const exactResults = results.filter((r) => r.matched_in !== "semantic");
  const similarResults = results.filter((r) => r.matched_in === "semantic");
  const showSimilarSection = submittedMode === "semantic" && !similarUnavailable;

  const grouped = exactResults.reduce<Record<string, { documentName?: string; results: SearchResult[] }>>((acc, r) => {
    if (!acc[r.document_id]) acc[r.document_id] = { documentName: r.document_name, results: [] };
    acc[r.document_id].results.push(r);
    return acc;
  }, {});

  function renderExpanded(r: SearchResult, state: ExpandedPageState) {
    return (
      <div className="mt-2 rounded-lg border border-border bg-muted/20 p-3">
        {state.loading ? (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 size={12} className="animate-spin" />
            Loading full page…
          </div>
        ) : state.error ? (
          <p className="text-destructive">{state.error}</p>
        ) : (
          <div className="flex flex-col gap-4">
            <div>
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                Original language
              </p>
              <SelectableText
                text={state.page?.original_text || ""}
                query={submittedQuery}
                onAddSelection={(text) => handleAddExcerpt(r.document_id, r.page_number, text)}
              />
            </div>
            <div>
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                English
              </p>
              <SelectableText
                text={state.page?.english_text || ""}
                query={submittedQuery}
                onAddSelection={(text) => handleAddExcerpt(r.document_id, r.page_number, text)}
              />
            </div>
          </div>
        )}
      </div>
    );
  }

  function renderResult(r: SearchResult, index: number, section: "exact" | "similar") {
    const key = `${section}-${r.document_id}-${r.page_number}-${r.matched_in}-${index}`;
    const expandedState = expanded[key];
    return (
      <li key={key} className="px-3 py-2.5 text-xs">
        <button
          type="button"
          onClick={() => toggleExpand(key, r.document_id, r.page_number)}
          className="flex w-full items-center justify-between gap-2 text-left"
        >
          <span className="flex flex-wrap items-center gap-2">
            {section === "similar" && (
              <span className="flex items-center gap-1 font-medium">
                <FileText size={12} className="text-primary" />
                <span className="max-w-[16rem] truncate">{r.document_name || r.document_id}</span>
              </span>
            )}
            <Badge variant="outline" className="text-[10px] font-bold">
              Page {r.page_number}
            </Badge>
            {section === "similar" ? (
              <SimilarityIndicator similarity={r.similarity} />
            ) : (
              <span className="text-muted-foreground">
                {r.matched_in === "original" ? "original language" : "English"}
              </span>
            )}
          </span>
          {expandedState ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>

        <p className="mt-1.5 leading-relaxed text-foreground/90">
          <HighlightedText text={r.snippet} query={submittedQuery} highlightFallback={section === "similar"} />
        </p>

        {expandedState && renderExpanded(r, expandedState)}
      </li>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={handleSearch} className="flex flex-col gap-2 sm:flex-row">
        <div className="flex flex-1 gap-2">
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
        </div>
        <div className="flex gap-1 self-start rounded-lg border border-border p-1">
          <Button type="button" size="sm" variant={mode === "exact" ? "secondary" : "ghost"} onClick={() => selectMode("exact")}>
            Exact
          </Button>
          <Button type="button" size="sm" variant={mode === "semantic" ? "secondary" : "ghost"} onClick={() => selectMode("semantic")}>
            <Sparkles size={13} data-icon="inline-start" />
            Exact + similar
          </Button>
        </div>
      </form>
      {mode === "semantic" && (
        <p className="text-xs text-muted-foreground">
          Exact matches are listed first. Passages with a similar meaning follow in their own section, with a similarity score.
        </p>
      )}

      {isSearching && (
        <div className="flex items-center justify-center gap-2 py-8 text-xs text-muted-foreground">
          <Loader2 size={14} className="animate-spin" />
          Searching…
        </div>
      )}

      {!isSearching && searchError && (
        <p className="rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">{searchError}</p>
      )}

      {!isSearching && !searchError && similarUnavailable && (
        <p className="flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          Similar-meaning search is unavailable right now, so only exact matches are shown.
        </p>
      )}

      {!isSearching && !searchError && hasSearched && results.length === 0 && (
        <p className="py-6 text-center text-xs text-muted-foreground">
          No {submittedMode === "semantic" && !similarUnavailable ? "exact or similar matches" : "matches"} for &ldquo;{submittedQuery}&rdquo;.
        </p>
      )}

      {!isSearching && !searchError && hasSearched && results.length > 0 && (
        <div className="flex flex-col gap-6">
          {(exactResults.length > 0 || showSimilarSection) && (
            <section aria-label="Exact matches" className="flex flex-col gap-3">
              {submittedMode === "semantic" && (
                <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  Exact matches
                  <Badge variant="outline" className="text-[10px]">{exactResults.length}</Badge>
                </h3>
              )}
              {exactResults.length === 0 ? (
                <p className="text-xs text-muted-foreground">No exact matches for &ldquo;{submittedQuery}&rdquo;.</p>
              ) : (
                Object.entries(grouped).map(([documentId, group]) => (
                  <div key={documentId} className="rounded-xl border border-border">
                    <div className="flex items-center gap-2 border-b bg-muted/30 px-3 py-2 text-xs font-semibold">
                      <FileText size={14} className="text-primary" />
                      <span className="truncate">{group.documentName || documentId}</span>
                      <Badge variant="outline" className="ml-auto shrink-0 text-[10px]">
                        {group.results.length} match{group.results.length === 1 ? "" : "es"}
                      </Badge>
                    </div>
                    <ul className="divide-y divide-border">
                      {group.results.map((r, i) => renderResult(r, i, "exact"))}
                    </ul>
                  </div>
                ))
              )}
            </section>
          )}

          {showSimilarSection && (
            <section aria-label="Similar passages" className="flex flex-col gap-3">
              <div>
                <h3 className="flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-violet-700 dark:text-violet-300">
                  <Sparkles size={13} />
                  Similar passages
                  <Badge variant="outline" className="text-[10px]">{similarResults.length}</Badge>
                </h3>
                <p className="mt-1 text-xs text-muted-foreground">
                  Related in meaning, not necessarily the same words, ranked by similarity. Check each one against the page before relying on it.
                </p>
              </div>
              {similarResults.length === 0 ? (
                <p className="text-xs text-muted-foreground">No similar passages found.</p>
              ) : (
                <ul className="divide-y divide-border rounded-xl border border-violet-500/30">
                  {similarResults.map((r, i) => renderResult(r, i, "similar"))}
                </ul>
              )}
            </section>
          )}
        </div>
      )}
    </div>
  );
}
