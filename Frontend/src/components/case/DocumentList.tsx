"use client";

import React, { useCallback, useEffect, useState } from "react";
import { FileText, Loader2, RefreshCw } from "lucide-react";
import { apiClient, type DocumentRecord } from "@/services/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

type BadgeVariant = "outline" | "secondary" | "destructive" | "default";

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
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(async () => {
    setIsLoading(true);
    const result = await apiClient.documents.listByCase(caseId);
    setDocuments(result.success && result.data ? result.data : []);
    setIsLoading(false);
  }, [caseId]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load, refreshKey]);

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
        <Button variant="ghost" size="sm" onClick={load} className="h-7 gap-1.5 text-xs">
          <RefreshCw size={12} />
          Refresh
        </Button>
      </div>

      {documents.length === 0 ? (
        <div className="py-8 text-center text-xs text-muted-foreground">
          No documents uploaded yet.
        </div>
      ) : (
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
              <Badge
                variant={STATUS_VARIANT[doc.status] || "outline"}
                className="shrink-0 text-[10px] font-bold uppercase"
              >
                {doc.status}
              </Badge>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
