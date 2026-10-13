"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowRight, CheckCircle2, FileText, Languages, ListChecks, Loader2, Lock, Search } from "lucide-react";
import { apiClient, type DocumentPageRecord, type SearchTerm } from "@/services/api/client";
import { useCaseById, useCaseProgress } from "@/services/api/hooks";
import { useToast } from "@/context/ToastContext";
import { Button } from "@/components/ui/button";
import { KeyboardInput } from "@/components/keyboard/KeyboardField";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CaseStepper } from "@/components/case/CaseStepper";
import { StepGuide } from "@/components/case/StepGuide";
import { PageHeader } from "@/components/case/PageHeader";
import { SelectableText } from "@/components/search/SelectableText";
import { cn } from "@/lib/utils";

const FIELDS = [
  { key: "survey", label: "Survey / Gat / CTS number", placeholder: "e.g. 12/3", primary: true },
  { key: "owner", label: "Owner name", placeholder: "e.g. Ramesh Patil", primary: true },
  { key: "village", label: "Village or location", placeholder: "e.g. Wagholi", primary: true },
  { key: "registration", label: "Registration number", placeholder: "e.g. 1234/2019", primary: false },
  { key: "keywords", label: "Other keywords", placeholder: "e.g. mortgage, encumbrance", primary: false },
] as const;

type FieldKey = (typeof FIELDS)[number]["key"];

interface ResultGroup {
  key: FieldKey;
  label: string;
  query: string;
  terms: SearchTerm[];
}

const normalize = (term: string) => term.normalize("NFC").toLowerCase();

export function CaseSearchPage() {
  const params = useParams();
  const caseId = (params?.id as string) || "";
  const toast = useToast();

  const { data: caseData } = useCaseById(caseId);
  const caseDetails = caseData?.data;
  const { documents, total, approved, isLoading: progressLoading } = useCaseProgress(caseId);
  const approvedDocs = useMemo(
    () => documents.filter((d) => d.status === "approved" || d.status === "completed"),
    [documents]
  );

  const [values, setValues] = useState<Record<FieldKey, string>>({
    survey: "", owner: "", village: "", registration: "", keywords: "",
  });
  const [isSearching, setIsSearching] = useState(false);
  const [groups, setGroups] = useState<ResultGroup[] | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [pages, setPages] = useState<Record<string, DocumentPageRecord[] | "loading" | "error">>({});
  const [selectedCount, setSelectedCount] = useState(0);
  const [isAdding, setIsAdding] = useState(false);
  const [showMore, setShowMore] = useState(false);
  const [untranslated, setUntranslated] = useState<string[]>([]);
  const [isTranslating, setIsTranslating] = useState(false);

  const refreshSelectedCount = useCallback(async () => {
    const result = await apiClient.reportBuilder.get(caseId);
    if (result.success && result.data) setSelectedCount(result.data.excerpts.length);
  }, [caseId]);

  useEffect(() => {
    if (caseId) void refreshSelectedCount();
  }, [caseId, refreshSelectedCount]);

  const pickedWords = useMemo(() => {
    const words = new Map<string, string>();
    for (const group of groups ?? []) {
      for (const term of group.terms) {
        if (picked.has(normalize(term.term))) words.set(normalize(term.term), term.term);
      }
    }
    return [...words.values()];
  }, [groups, picked]);

  // Where the picked words occur: document id -> page numbers.
  const hitPages = useMemo(() => {
    const hits = new Map<string, Set<number>>();
    for (const group of groups ?? []) {
      for (const term of group.terms) {
        if (!picked.has(normalize(term.term))) continue;
        for (const location of term.locations) {
          if (!hits.has(location.document_id)) hits.set(location.document_id, new Set());
          hits.get(location.document_id)!.add(location.page_number);
        }
      }
    }
    return hits;
  }, [groups, picked]);

  // Load each matching document's pages once, when first needed.
  useEffect(() => {
    for (const documentId of hitPages.keys()) {
      if (pages[documentId]) continue;
      setPages((prev) => ({ ...prev, [documentId]: "loading" }));
      void apiClient.documents.getPages(documentId).then((result) => {
        setPages((prev) => ({
          ...prev,
          [documentId]: result.success && result.data ? result.data.pages : "error",
        }));
      });
    }
  }, [hitPages, pages]);

  const filledFields = FIELDS.filter((f) => values[f.key].trim());

  async function handleSearch(e?: React.FormEvent) {
    e?.preventDefault();
    if (filledFields.length === 0) return;

    setIsSearching(true);
    const results = await Promise.all(
      filledFields.map(async (field) => ({
        field,
        result: await apiClient.search.findTerms(caseId, values[field.key].trim()),
      }))
    );
    setIsSearching(false);

    const failed = results.find((r) => !r.result.success);
    if (failed) {
      toast.error(failed.result.error || "Search failed", "Search Error");
      return;
    }

    const nextGroups: ResultGroup[] = results.map(({ field, result }) => ({
      key: field.key,
      label: field.label,
      query: values[field.key].trim(),
      terms: result.data?.terms ?? [],
    }));
    setUntranslated(results[0]?.result.data?.untranslatedDocumentIds ?? []);
    setPages({}); // translated text may have changed what the pages say
    setGroups(nextGroups);
    // Exact words start ticked; similar words are the lawyer's call.
    setPicked(new Set(nextGroups.flatMap((g) => g.terms.filter((t) => t.kind === "exact").map((t) => normalize(t.term)))));
  }

  async function handleTranslateAll() {
    setIsTranslating(true);
    const outcomes = await Promise.all(untranslated.map((id) => apiClient.documents.translate(id)));
    setIsTranslating(false);
    const failed = outcomes.filter((o) => !o.success).length;
    if (failed > 0) toast.error(`${failed} document${failed === 1 ? "" : "s"} could not be translated. Try again.`, "Translation Error");
    else toast.success("Translated. Searching again…", "Translation Complete");
    await handleSearch();
  }

  function toggle(term: string) {
    setPicked((prev) => {
      const next = new Set(prev);
      const key = normalize(term);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function setKind(group: ResultGroup, kind: "exact" | "similar", on: boolean) {
    setPicked((prev) => {
      const next = new Set(prev);
      for (const term of group.terms) {
        if (term.kind !== kind) continue;
        if (on) next.add(normalize(term.term));
        else next.delete(normalize(term.term));
      }
      return next;
    });
  }

  async function handleAddSelection(documentId: string, pageNumber: number, text: string | null) {
    if (!text) {
      toast.warning("Select some text on the page with your mouse first, then press the button.", "Nothing Selected");
      return;
    }
    setIsAdding(true);
    const result = await apiClient.reportBuilder.addExcerpt(caseId, {
      document_id: documentId,
      page_number: pageNumber,
      excerpt_text: text,
    });
    setIsAdding(false);
    if (result.success) {
      toast.success("Added to your selections.", "Selected");
      void refreshSelectedCount();
    } else {
      toast.error(result.error || "Failed to add the selection", "Error");
    }
  }

  const docName = (id: string) => documents.find((d) => d.id === id)?.file_name || "Document";

  // ---- locked: nothing approved yet ----
  if (!progressLoading && approved === 0) {
    return (
      <div className="min-h-screen bg-background px-4 py-8 md:px-6">
        <div className="mx-auto max-w-5xl">
          <PageHeader title={caseDetails?.title || caseDetails?.property_name || "Search"} />
          <CaseStepper caseId={caseId} current="search" />
          <Card>
            <CardContent className="flex flex-col items-center gap-3 py-14 text-center">
              <Lock size={28} className="text-muted-foreground" />
              <p className="text-lg font-semibold">Approve a document to start searching</p>
              <p className="max-w-md text-sm text-muted-foreground">
                Search works only on documents you have checked and approved.{" "}
                {total === 0 ? "Upload documents first." : `You have ${total} document${total === 1 ? "" : "s"} in this case.`}
              </p>
              <Button nativeButton={false} render={<Link href={total === 0 ? `/cases/${caseId}` : `/cases/${caseId}/review`} />}>
                {total === 0 ? "Go to upload" : "Review & approve documents"}
                <ArrowRight size={15} data-icon="inline-end" />
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background px-4 py-8 pb-28 md:px-6">
      <div className="mx-auto max-w-5xl">
        <PageHeader
          title={caseDetails?.title || caseDetails?.property_name || "Search"}
          subtitle={
            <>
              {approved} approved document{approved === 1 ? "" : "s"}
              {total > approved ? ` · ${total - approved} not approved yet` : ""}{" "}
              {total > approved && (
                <Link href={`/cases/${caseId}/review`} className="font-medium text-primary underline-offset-2 hover:underline">
                  Review the rest
                </Link>
              )}
            </>
          }
        />

        <CaseStepper caseId={caseId} current="search" />

        <StepGuide
          id="search"
          title="Step 3 of 4: find the text you want in the report"
          steps={[
            "Type a name, number or word in any box you need (the अ button types in Marathi), then press Find in documents.",
            "Tick the spellings you mean. Matches are highlighted in the document.",
            "Select the exact text you want to quote and add it to your report.",
          ]}
          note="Only approved documents are searched."
        />

        <Card>
          <CardHeader className="border-b">
            <CardTitle className="flex items-center gap-2 text-lg">
              <Search size={20} className="text-primary" /> What are you looking for?
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-6">
            <form onSubmit={handleSearch} className="flex flex-col gap-4">
              <div className="grid gap-4 sm:grid-cols-2">
                {FIELDS.filter((f) => showMore || f.primary).map((field) => (
                  <label key={field.key} className="flex flex-col gap-1.5">
                    <span className="text-sm font-medium">{field.label}</span>
                    <KeyboardInput
                      value={values[field.key]}
                      onChange={(e) => setValues((prev) => ({ ...prev, [field.key]: e.target.value }))}
                      placeholder={field.placeholder}
                    />
                  </label>
                ))}
              </div>
              <div className="flex items-center justify-between">
                <button type="button" className="text-sm text-muted-foreground underline-offset-4 hover:underline" onClick={() => setShowMore((v) => !v)}>
                  {showMore ? "Fewer fields" : "More fields"}
                </button>
                <Button type="submit" disabled={isSearching || filledFields.length === 0}>
                  {isSearching ? <Loader2 size={15} className="animate-spin" data-icon="inline-start" /> : <Search size={15} data-icon="inline-start" />}
                  {isSearching ? "Searching…" : "Find in documents"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        {groups && untranslated.length > 0 && (
          <div role="status" className="mt-6 flex flex-wrap items-center justify-between gap-3 rounded-lg bg-accent px-4 py-3 text-sm text-accent-foreground">
            <p>
              {untranslated.length} approved document{untranslated.length === 1 ? " is" : "s are"} not translated, so English
              words will not match {untranslated.length === 1 ? "it" : "them"}.
            </p>
            <Button variant="outline" size="sm" onClick={() => void handleTranslateAll()} disabled={isTranslating}>
              {isTranslating ? <Loader2 size={14} className="animate-spin" data-icon="inline-start" /> : <Languages size={14} data-icon="inline-start" />}
              {isTranslating ? "Translating…" : "Translate"}
            </Button>
          </div>
        )}

        {groups && (
          <>
            <Card className="mt-6">
              <CardHeader className="border-b">
                <CardTitle className="text-lg">Words found</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-5 pt-6">
                {groups.map((group) => {
                  const exact = group.terms.filter((t) => t.kind === "exact");
                  const similar = group.terms.filter((t) => t.kind === "similar");
                  return (
                    <div key={group.key} className="rounded-xl border border-border p-4">
                      <p className="text-sm font-semibold">
                        {group.label}: <span className="font-normal text-muted-foreground">&ldquo;{group.query}&rdquo;</span>
                      </p>
                      {group.terms.length === 0 ? (
                        <p className="mt-2 text-sm text-muted-foreground">
                          Not found in the approved documents.
                        </p>
                      ) : (
                        <div className="mt-3 flex flex-col gap-3">
                          <TermRow title="Exact" terms={exact} picked={picked} onToggle={toggle}
                            onAll={(on) => setKind(group, "exact", on)} />
                          <TermRow title="Similar words" terms={similar} picked={picked} onToggle={toggle}
                            onAll={(on) => setKind(group, "similar", on)} emptyText="No similar spellings found." />
                        </div>
                      )}
                    </div>
                  );
                })}
              </CardContent>
            </Card>

            <Card className="mt-6">
              <CardHeader className="border-b">
                <CardTitle className="text-lg">Pages</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-5 pt-6">
                {pickedWords.length === 0 && (
                  <p className="py-4 text-center text-sm text-muted-foreground">Tick a word to see where it appears.</p>
                )}
                {[...hitPages.entries()].map(([documentId, pageNumbers]) => {
                  const state = pages[documentId];
                  const shown = Array.isArray(state)
                    ? state.filter((p) => pageNumbers.has(p.page_number)).sort((a, b) => a.page_number - b.page_number)
                    : [];
                  return (
                    <div key={documentId} className="rounded-xl border border-border">
                      <div className="flex items-center gap-2 border-b bg-muted/30 px-4 py-2.5 text-sm font-semibold">
                        <FileText size={15} className="text-primary" />
                        <span className="truncate">{docName(documentId)}</span>
                        <Badge variant="outline" className="ml-auto shrink-0">
                          {pageNumbers.size} page{pageNumbers.size === 1 ? "" : "s"}
                        </Badge>
                      </div>
                      <div className="flex flex-col divide-y divide-border">
                        {state === "loading" || state === undefined ? (
                          <p className="flex items-center gap-2 px-4 py-4 text-sm text-muted-foreground">
                            <Loader2 size={14} className="animate-spin" /> Loading pages…
                          </p>
                        ) : state === "error" ? (
                          <p className="px-4 py-4 text-sm text-destructive">Could not load this document&apos;s pages.</p>
                        ) : (
                          shown.map((page) => (
                            <div key={page.page_number} className="grid gap-4 px-4 py-4 md:grid-cols-2">
                              <div>
                                <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                                  Page {page.page_number} · original
                                </p>
                                <SelectableText
                                  text={page.original_text || ""}
                                  query=""
                                  words={pickedWords}
                                  disabled={isAdding}
                                  addLabel="Add selected text to report"
                                  onAddSelection={(text) => void handleAddSelection(documentId, page.page_number, text)}
                                />
                              </div>
                              <div className="md:border-l md:border-border md:pl-4">
                                <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-muted-foreground">English</p>
                                {page.english_text ? (
                                  <SelectableText
                                    text={page.english_text}
                                    query=""
                                    words={pickedWords}
                                    disabled={isAdding}
                                    addLabel="Add selected text to report"
                                    onAddSelection={(text) => void handleAddSelection(documentId, page.page_number, text)}
                                  />
                                ) : (
                                  <p className="text-sm text-muted-foreground">Not translated.</p>
                                )}
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          </>
        )}
      </div>

      <div className="fixed inset-x-0 bottom-0 z-40 border-t bg-background/95 px-4 py-3 backdrop-blur md:px-6">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3">
          <p className="flex items-center gap-2 text-sm">
            {selectedCount > 0 ? <CheckCircle2 size={16} className="text-emerald-600" /> : <ListChecks size={16} className="text-muted-foreground" />}
            <span className="font-semibold">{selectedCount}</span> passage{selectedCount === 1 ? "" : "s"} selected for the report
          </p>
          <div className="flex gap-2">
            <Button variant="outline" nativeButton={false} render={<Link href={`/cases/${caseId}/report-builder`} />}>
              Manage selections
            </Button>
            <Button nativeButton={false} render={<Link href={`/cases/${caseId}/report`} />}>
              Continue to report
              <ArrowRight size={15} data-icon="inline-end" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function TermRow({
  title,
  terms,
  picked,
  onToggle,
  onAll,
  emptyText,
}: {
  title: string;
  terms: SearchTerm[];
  picked: Set<string>;
  onToggle: (term: string) => void;
  onAll: (on: boolean) => void;
  emptyText?: string;
}) {
  if (terms.length === 0 && !emptyText) return null;
  return (
    <div>
      <div className="mb-1.5 flex items-center gap-3">
        <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">{title}</span>
        {terms.length > 1 && (
          <span className="flex gap-2 text-xs">
            <button type="button" className="text-primary hover:underline" onClick={() => onAll(true)}>Tick all</button>
            <button type="button" className="text-muted-foreground hover:underline" onClick={() => onAll(false)}>Clear</button>
          </span>
        )}
      </div>
      {terms.length === 0 ? (
        <p className="text-sm text-muted-foreground">{emptyText}</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {terms.map((term) => {
            const on = picked.has(normalize(term.term));
            return (
              <button
                key={term.term}
                type="button"
                onClick={() => onToggle(term.term)}
                aria-pressed={on}
                className={cn(
                  "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm transition-colors",
                  on ? "border-primary bg-primary/10 font-semibold text-primary" : "border-border hover:bg-muted"
                )}
              >
                <span className={cn("flex size-4 items-center justify-center rounded border text-[10px]", on ? "border-primary bg-primary text-primary-foreground" : "border-muted-foreground/40")}>
                  {on && "✓"}
                </span>
                {term.term}
                <span className="text-xs font-normal text-muted-foreground">×{term.count}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
