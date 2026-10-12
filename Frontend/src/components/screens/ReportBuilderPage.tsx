"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowDown, ArrowRight, ArrowUp, FileText, Loader2, Pencil, Trash2 } from "lucide-react";
import { apiClient, type CaseRecord, type ReportExcerpt } from "@/services/api/client";
import { useToast } from "@/context/ToastContext";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { CaseStepper } from "@/components/case/CaseStepper";
import { PageHeader } from "@/components/case/PageHeader";
import { FormattedText } from "@/components/text/FormattedText";

export function ReportBuilderPage() {
  const params = useParams();
  const caseId = (params?.id as string) || "";
  const toast = useToast();

  const [excerpts, setExcerpts] = useState<ReportExcerpt[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [editingExcerptId, setEditingExcerptId] = useState<string | null>(null);
  const [draftText, setDraftText] = useState("");
  const [isSavingText, setIsSavingText] = useState(false);
  const [caseDetails, setCaseDetails] = useState<CaseRecord | null>(null);

  useEffect(() => {
    if (!caseId) return;
    apiClient.cases.getById(caseId).then(
      (result) => setCaseDetails(result.data),
      () => setCaseDetails(null),
    );
  }, [caseId]);

  const load = useCallback(async () => {
    setIsLoading(true);
    const result = await apiClient.reportBuilder.get(caseId);
    setExcerpts(result.success && result.data ? result.data.excerpts : []);
    setIsLoading(false);
  }, [caseId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleRemove(excerptId: string) {
    const result = await apiClient.reportBuilder.removeExcerpt(caseId, excerptId);
    if (result.success) {
      setExcerpts((prev) => prev.filter((e) => e.id !== excerptId));
      toast.success("Excerpt removed", "Report Updated");
    } else {
      toast.error(result.error || "Failed to remove excerpt", "Error");
    }
  }

  async function handleMove(index: number, direction: -1 | 1) {
    const newIndex = index + direction;
    if (newIndex < 0 || newIndex >= excerpts.length) return;

    const reordered = [...excerpts];
    [reordered[index], reordered[newIndex]] = [reordered[newIndex], reordered[index]];
    setExcerpts(reordered); // optimistic

    const result = await apiClient.reportBuilder.reorder(caseId, reordered.map((e) => e.id));
    if (result.success && result.data) {
      setExcerpts(result.data);
    } else {
      toast.error(result.error || "Failed to reorder excerpts", "Error");
      load(); // revert to server state
    }
  }

  function handleNoteChange(excerptId: string, note: string) {
    setExcerpts((prev) => prev.map((e) => (e.id === excerptId ? { ...e, note } : e)));
  }

  async function handleNoteBlur(excerptId: string, note: string) {
    const result = await apiClient.reportBuilder.updateExcerptNote(caseId, excerptId, note);
    if (!result.success) {
      toast.error(result.error || "Failed to save note", "Error");
    }
  }

  function startEditingText(excerpt: ReportExcerpt) {
    setEditingExcerptId(excerpt.id);
    setDraftText(excerpt.excerpt_text);
  }

  function cancelEditingText() {
    setEditingExcerptId(null);
    setDraftText("");
  }

  async function handleSaveText(excerpt: ReportExcerpt) {
    const trimmed = draftText.trim();
    if (!trimmed) {
      toast.error("Excerpt text can't be empty", "Error");
      return;
    }
    setIsSavingText(true);
    const result = await apiClient.reportBuilder.updateExcerptNote(caseId, excerpt.id, excerpt.note || "", trimmed);
    setIsSavingText(false);
    if (result.success) {
      setExcerpts((prev) => prev.map((e) => (e.id === excerpt.id ? { ...e, excerpt_text: trimmed } : e)));
      setEditingExcerptId(null);
      setDraftText("");
      toast.success("Excerpt text updated.", "Saved");
    } else {
      toast.error(result.error || "Failed to save excerpt text", "Error");
    }
  }

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 size={24} className="animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background px-4 py-8 md:px-6">
      <div className="mx-auto max-w-4xl">
        <PageHeader
          title={caseDetails?.title || caseDetails?.property_name || "Untitled Case"}
          subtitle="In the order they appear in the report."
          actions={
            <>
              <Button variant="outline" nativeButton={false} render={<Link href={`/cases/${caseId}/search`} />}>
                Back to search
              </Button>
              <Button nativeButton={false} render={<Link href={`/cases/${caseId}/report`} />}>
                Continue to report
                <ArrowRight size={15} data-icon="inline-end" />
              </Button>
            </>
          }
        />

        <CaseStepper caseId={caseId} current="search" />

        {excerpts.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center text-sm text-muted-foreground">
              Nothing selected yet. Go back to Search, pick your words, select text on a page and add it. You can
              also continue without selections; the report will still list the documents and the chain of title.
            </CardContent>
          </Card>
        ) : (
          <div className="flex flex-col gap-3">
            {excerpts.map((excerpt, index) => (
              <Card key={excerpt.id}>
                <CardContent className="flex flex-col gap-3 pt-6">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <FileText size={14} className="text-primary" />
                      <Badge variant="outline" className="font-mono text-[10px]">
                        Excerpt {index + 1}
                      </Badge>
                      <span>
                        {excerpt.document_name || excerpt.document_id} &middot; Page {excerpt.page_number}
                      </span>
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="size-7 p-0"
                        onClick={() => handleMove(index, -1)}
                        disabled={index === 0}
                        title="Move up"
                      >
                        <ArrowUp size={13} />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="size-7 p-0"
                        onClick={() => handleMove(index, 1)}
                        disabled={index === excerpts.length - 1}
                        title="Move down"
                      >
                        <ArrowDown size={13} />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="size-7 p-0"
                        onClick={() => startEditingText(excerpt)}
                        disabled={editingExcerptId === excerpt.id}
                        title="Edit excerpt text"
                      >
                        <Pencil size={13} />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="size-7 p-0 text-destructive hover:bg-destructive/10"
                        onClick={() => handleRemove(excerpt.id)}
                        title="Remove"
                      >
                        <Trash2 size={13} />
                      </Button>
                    </div>
                  </div>

                  {editingExcerptId === excerpt.id ? (
                    <div className="flex flex-col gap-2">
                      <textarea
                        value={draftText}
                        onChange={(e) => setDraftText(e.target.value)}
                        className="min-h-[80px] w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm leading-relaxed outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
                        autoFocus
                      />
                      <div className="flex gap-2">
                        <Button size="sm" disabled={isSavingText} onClick={() => handleSaveText(excerpt)}>
                          {isSavingText ? "Saving…" : "Save"}
                        </Button>
                        <Button size="sm" variant="outline" disabled={isSavingText} onClick={cancelEditingText}>
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="border-l-2 border-primary/40 pl-3 text-sm text-foreground/90">
                      <FormattedText text={excerpt.excerpt_text} />
                    </div>
                  )}

                  <Input
                    placeholder="Add a note about this excerpt (optional)"
                    value={excerpt.note || ""}
                    onChange={(e) => handleNoteChange(excerpt.id, e.target.value)}
                    onBlur={(e) => handleNoteBlur(excerpt.id, e.target.value)}
                    className="text-xs"
                  />
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
