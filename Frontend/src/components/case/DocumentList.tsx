"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, FileText, Loader2, RefreshCw, Trash2 } from "lucide-react";
import { apiClient, type DocumentRecord } from "@/services/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/context/ToastContext";

type BadgeVariant = "outline" | "secondary" | "destructive" | "default";
const IN_PROGRESS_STATUSES = new Set(["uploaded", "processing", "ocr_done"]);

const STATUS_VARIANT: Record<string, BadgeVariant> = {
  uploaded: "outline",
  processing: "outline",
  ocr_done: "outline",
  llm_done: "secondary",
  under_review: "outline",
  approved: "secondary",
  flagged: "destructive",
  rejected: "destructive",
  completed: "secondary",
};

interface DocumentListProps {
  caseId: string;
  /** Bump this (e.g. after an upload) to force a re-fetch. */
  refreshKey?: number;
}

export function DocumentList({ caseId, refreshKey }: DocumentListProps) {
  const toast = useToast();
  const [deletingDocumentId, setDeletingDocumentId] = useState<string | null>(null);
  const {
    data: documents = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["documents", caseId, "list", refreshKey ?? 0],
    queryFn: async (): Promise<DocumentRecord[]> => {
      const result = await apiClient.documents.listByCase(caseId);
      if (!result.success) throw new Error(result.error || "Failed to load documents");
      return result.data || [];
    },
    enabled: Boolean(caseId),
    staleTime: 0,
    refetchInterval: (query) =>
      query.state.data?.some((doc) => IN_PROGRESS_STATUSES.has(doc.status)) ? 3000 : false,
  });

  async function handleDelete(documentId: string) {
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
      <div className="flex items-center justify-center gap-2 py-8 text-xs text-muted-foreground">
        <Loader2 size={14} className="animate-spin" />
        Loading documents…
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">
          {documents.length} document{documents.length === 1 ? "" : "s"}
        </span>
        <Button variant="ghost" size="sm" onClick={() => void refetch()} className="h-7 gap-1.5 text-xs">
          <RefreshCw size={12} />
          Refresh
        </Button>
      </div>

      {isError && (
        <p className="flex items-center gap-2 rounded-md bg-destructive/10 px-3 py-2 text-xs text-destructive">
          <AlertCircle size={14} />
          {error instanceof Error ? error.message : "Unable to load documents."}
        </p>
      )}

      {documents.length === 0 && !isError ? (
        <div className="py-8 text-center text-xs text-muted-foreground">
          No documents uploaded yet.
        </div>
      ) : documents.length > 0 ? (
        <ul className="flex flex-col gap-2">
          {documents.map((doc) => (
            <li
              key={doc.id}
              className="flex items-center justify-between gap-2 rounded-lg border border-border bg-background px-3 py-2 text-xs"
            >
              <span className="flex items-center gap-2 truncate">
                <FileText size={14} className="shrink-0 text-primary" />
                <span className="truncate font-medium">{doc.file_name}</span>
              </span>
              <span className="flex shrink-0 items-center gap-2">
                <Badge
                  variant={STATUS_VARIANT[doc.status] || "outline"}
                  className="text-[10px] font-bold uppercase"
                >
                  {doc.status}
                </Badge>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  title={`Delete ${doc.file_name}`}
                  aria-label={`Delete ${doc.file_name}`}
                  disabled={deletingDocumentId === doc.id}
                  onClick={() => void handleDelete(doc.id)}
                >
                  {deletingDocumentId === doc.id ? (
                    <Loader2 size={13} className="animate-spin" />
                  ) : (
                    <Trash2 size={13} />
                  )}
                </Button>
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
