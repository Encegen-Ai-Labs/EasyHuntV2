"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowRight, CheckCircle2, FileText, Loader2, RefreshCw, Trash2 } from "lucide-react";
import { DOCUMENT_APPROVED, DOCUMENT_IN_PROGRESS, useCaseDocuments } from "@/services/api/hooks";
import { apiClient } from "@/services/api/client";
import { Button } from "@/components/ui/button";
import { useToast } from "@/context/ToastContext";
import { cn } from "@/lib/utils";

type Tone = "reading" | "ready" | "approved" | "attention";

function describe(status: string): { label: string; tone: Tone } {
  if (DOCUMENT_IN_PROGRESS.has(status)) return { label: "Reading…", tone: "reading" };
  if (DOCUMENT_APPROVED.has(status)) return { label: "Approved", tone: "approved" };
  if (status === "rejected") return { label: "Flagged for correction", tone: "attention" };
  if (status === "flagged") return { label: "Needs attention", tone: "attention" };
  return { label: "Ready to review", tone: "ready" };
}

const TONE_CLASS: Record<Tone, string> = {
  reading: "bg-muted text-muted-foreground",
  ready: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  approved: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  attention: "bg-destructive/10 text-destructive",
};

export function DocumentList({ caseId }: { caseId: string }) {
  const toast = useToast();
  const [deletingDocumentId, setDeletingDocumentId] = useState<string | null>(null);
  const { data: documents = [], isLoading, isError, error, refetch } = useCaseDocuments(caseId);

  async function handleDelete(documentId: string, fileName: string) {
    if (!window.confirm(`Delete "${fileName}"? This removes the document and everything read from it.`)) return;
    setDeletingDocumentId(documentId);
    const result = await apiClient.documents.delete(documentId);
    setDeletingDocumentId(null);

    if (!result.success) {
      toast.error(result.error || "Failed to delete document", "Delete Error");
      return;
    }
    toast.success("Document deleted.", "Deleted");
    await refetch();
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
        <Loader2 size={14} className="animate-spin" />
        Loading documents…
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          {documents.length} document{documents.length === 1 ? "" : "s"}
        </span>
        <Button variant="ghost" size="sm" onClick={() => void refetch()} className="h-7 gap-1.5 text-xs">
          <RefreshCw size={12} />
          Refresh
        </Button>
      </div>

      {isError && (
        <p className="flex items-center gap-2 rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <AlertCircle size={14} />
          {error instanceof Error ? error.message : "Unable to load documents."}
        </p>
      )}

      {documents.length === 0 && !isError ? (
        <div className="py-8 text-center text-sm text-muted-foreground">No documents uploaded yet.</div>
      ) : (
        <ul className="flex flex-col gap-2">
          {documents.map((doc) => {
            const { label, tone } = describe(doc.status);
            return (
              <li
                key={doc.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-background px-3 py-2.5 text-sm"
              >
                <span className="flex min-w-0 items-center gap-2">
                  <FileText size={15} className="shrink-0 text-primary" />
                  <span className="truncate font-medium">{doc.file_name}</span>
                </span>
                <span className="flex shrink-0 items-center gap-2">
                  <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold", TONE_CLASS[tone])}>
                    {tone === "reading" && <Loader2 size={11} className="animate-spin" />}
                    {tone === "approved" && <CheckCircle2 size={11} />}
                    {label}
                  </span>
                  {tone !== "reading" && (
                    <Button
                      variant="outline"
                      size="sm"
                      nativeButton={false}
                      render={<Link href={`/cases/${caseId}/review?doc=${doc.id}`} />}
                    >
                      {tone === "approved" ? "View" : "Review"}
                      <ArrowRight size={13} data-icon="inline-end" />
                    </Button>
                  )}
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    title={`Delete ${doc.file_name}`}
                    aria-label={`Delete ${doc.file_name}`}
                    disabled={deletingDocumentId === doc.id}
                    onClick={() => void handleDelete(doc.id, doc.file_name)}
                  >
                    {deletingDocumentId === doc.id ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
                  </Button>
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
