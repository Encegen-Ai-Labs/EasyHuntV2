"use client";

import React, { useEffect, useRef, useState } from "react";
import { UploadCloud, FileText, X, Loader2, CheckCircle2, AlertTriangle, Ban, Trash2 } from "lucide-react";
import { apiClient } from "@/services/api/client";
import { useToast } from "@/context/ToastContext";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";

const ALLOWED_TYPES = ["application/pdf", "image/png", "image/jpeg", "image/jpg"];
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const MAX_BATCH_SIZE = 20;
const TERMINAL_STATUSES = ["llm_done", "under_review", "approved", "flagged", "rejected", "completed", "failed"];

interface TrackedDocument {
  fileName: string;
  documentId?: string;
  status: string; // "failed" (upload-time) or a backend DocStatusEnum value
  error?: string;
}

interface BatchUploadPanelProps {
  caseId: string;
  /** Called once per successful upload batch, after results are known (not after processing finishes). */
  onUploaded?: () => void;
}

export function BatchUploadPanel({ caseId, onUploaded }: BatchUploadPanelProps) {
  const toast = useToast();

  const [queuedFiles, setQueuedFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [tracked, setTracked] = useState<TrackedDocument[]>([]);
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());

  const abortControllerRef = useRef<AbortController | null>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const trackedRef = useRef<TrackedDocument[]>([]);

  useEffect(() => {
    trackedRef.current = tracked;
  }, [tracked]);

  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, []);

  function addFiles(fileList: FileList | null) {
    if (!fileList) return;
    const incoming = Array.from(fileList);
    const accepted: File[] = [];

    for (const file of incoming) {
      if (!ALLOWED_TYPES.includes(file.type)) {
        toast.error(`${file.name}: unsupported file type`, "Validation Error");
        continue;
      }
      if (file.size > MAX_FILE_SIZE) {
        toast.error(`${file.name}: exceeds 10MB limit`, "Validation Error");
        continue;
      }
      accepted.push(file);
    }

    setQueuedFiles((prev) => {
      const next = [...prev, ...accepted];
      if (next.length > MAX_BATCH_SIZE) {
        toast.error(`Only ${MAX_BATCH_SIZE} files can be uploaded in one batch`, "Batch Limit");
        return next.slice(0, MAX_BATCH_SIZE);
      }
      return next;
    });
  }

  function removeQueuedFile(index: number) {
    setQueuedFiles((prev) => prev.filter((_, i) => i !== index));
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    addFiles(e.dataTransfer.files);
  }

  function handleCancelUpload() {
    abortControllerRef.current?.abort();
  }

  function startPolling() {
    if (pollIntervalRef.current) return;

    pollIntervalRef.current = setInterval(async () => {
      const pending = trackedRef.current.filter(
        (t) => t.documentId && !TERMINAL_STATUSES.includes(t.status)
      );

      if (pending.length === 0) {
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
        return;
      }

      const updates = await Promise.all(
        pending.map(async (t) => {
          const res = await apiClient.documents.getStatus(t.documentId!);
          return { documentId: t.documentId!, status: res.success ? res.data?.status : undefined };
        })
      );

      setTracked((prev) =>
        prev.map((t) => {
          const update = updates.find((u) => u.documentId === t.documentId);
          return update?.status ? { ...t, status: update.status } : t;
        })
      );
    }, 4000);
  }

  async function handleUpload() {
    if (queuedFiles.length === 0) return;

    setIsUploading(true);
    setUploadProgress(0);
    const controller = new AbortController();
    abortControllerRef.current = controller;

    const result = await apiClient.documents.upload(caseId, queuedFiles, {
      signal: controller.signal,
      onProgress: setUploadProgress,
    });

    setIsUploading(false);
    abortControllerRef.current = null;

    if (!result.success || !result.data) {
      toast.error(result.error || "Batch upload failed", "Upload Error");
      return;
    }

    const newTracked: TrackedDocument[] = result.data.results.map((r) => ({
      fileName: r.file_name,
      documentId: r.document?.id,
      status: r.success ? r.document?.status || "processing" : "failed",
      error: r.error,
    }));

    const succeeded = newTracked.filter((t) => t.status !== "failed").length;
    const failed = newTracked.length - succeeded;

    setTracked((prev) => [...prev, ...newTracked]);
    setQueuedFiles([]);

    if (succeeded > 0) {
      toast.success(
        `${succeeded} document${succeeded === 1 ? "" : "s"} uploaded. Processing started.`,
        "Upload Complete"
      );
      onUploaded?.();
    }
    if (failed > 0) {
      toast.error(`${failed} file${failed === 1 ? "" : "s"} failed to upload`, "Some Files Failed");
    }

    startPolling();
  }

  // Deletes a document that's still uploading/processing (or already done) —
  // this is a soft-discard, not a request to actually interrupt whatever
  // OCR/VLM work might be in flight for it server-side (see
  // backend/app/services/doc_service.py::DocumentService.delete_document):
  // the row and its storage file are gone right away, so it disappears from
  // this list and stops being polled immediately, even if the backend
  // pipeline for it is still mid-run.
  async function handleDeleteTracked(documentId: string) {
    setDeletingIds((prev) => new Set(prev).add(documentId));

    const result = await apiClient.documents.delete(documentId);

    setDeletingIds((prev) => {
      const next = new Set(prev);
      next.delete(documentId);
      return next;
    });

    if (!result.success) {
      toast.error(result.error || "Failed to delete document", "Delete Error");
      return;
    }

    setTracked((prev) => prev.filter((t) => t.documentId !== documentId));
    toast.success("Document deleted", "Deleted");
    onUploaded?.();
  }

  return (
    <div className="flex flex-col gap-6">
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        className={`relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center transition-all ${
          queuedFiles.length > 0
            ? "border-primary/50 bg-primary/5"
            : "border-border bg-muted/20 hover:border-primary/40 hover:bg-muted/40"
        }`}
      >
        <input
          type="file"
          id="batch-file-upload"
          multiple
          className="absolute inset-0 opacity-0 cursor-pointer"
          onChange={(e) => addFiles(e.target.files)}
          accept=".pdf,.jpg,.jpeg,.png"
          disabled={isUploading}
        />

        <span className="flex size-14 items-center justify-center rounded-2xl bg-secondary text-secondary-foreground shadow-sm">
          <UploadCloud size={28} />
        </span>

        <h3 className="mt-4 text-base font-semibold">
          {queuedFiles.length > 0
            ? `${queuedFiles.length} file${queuedFiles.length === 1 ? "" : "s"} queued`
            : "Drag and drop documents here"}
        </h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Up to {MAX_BATCH_SIZE} files per batch · PDF, PNG, JPG · 10MB each
        </p>
      </div>

      {queuedFiles.length > 0 && (
        <ul className="flex flex-col gap-2">
          {queuedFiles.map((file, index) => (
            <li
              key={`${file.name}-${index}`}
              className="flex items-center justify-between gap-2 rounded-lg border border-border bg-background px-3 py-2 text-xs"
            >
              <span className="flex items-center gap-2 truncate">
                <FileText size={14} className="shrink-0 text-primary" />
                <span className="truncate font-medium">{file.name}</span>
                <span className="shrink-0 text-muted-foreground">
                  ({(file.size / (1024 * 1024)).toFixed(2)} MB)
                </span>
              </span>
              <button
                onClick={() => removeQueuedFile(index)}
                disabled={isUploading}
                className="shrink-0 text-muted-foreground hover:text-destructive"
              >
                <X size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}

      {isUploading && (
        <div className="rounded-xl border border-primary/20 bg-primary/5 p-4">
          <div className="flex items-center justify-between text-xs font-semibold">
            <span className="flex items-center gap-2 text-primary">
              <Loader2 size={14} className="animate-spin" />
              Uploading batch… ({uploadProgress}%)
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleCancelUpload}
              className="h-7 text-xs text-destructive hover:bg-destructive/10"
            >
              <Ban size={13} data-icon="inline-start" />
              Cancel
            </Button>
          </div>
          <Progress value={uploadProgress} className="mt-2.5 h-2" />
        </div>
      )}

      <div className="flex justify-end gap-3">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setQueuedFiles([])}
          disabled={isUploading || queuedFiles.length === 0}
        >
          Clear
        </Button>
        <Button
          size="sm"
          onClick={handleUpload}
          disabled={isUploading || queuedFiles.length === 0}
          className="gap-2"
        >
          {isUploading ? (
            <>
              <Loader2 size={14} className="animate-spin" />
              Uploading…
            </>
          ) : (
            <>
              <UploadCloud size={14} />
              Upload {queuedFiles.length > 0 ? `${queuedFiles.length} file${queuedFiles.length === 1 ? "" : "s"}` : "files"}
            </>
          )}
        </Button>
      </div>

      {tracked.length > 0 && (
        <div className="flex flex-col gap-2 border-t pt-4">
          <h4 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Uploaded this session
          </h4>
          <ul className="flex flex-col gap-2">
            {tracked.map((t, index) => (
              <li
                key={`${t.fileName}-${index}`}
                className="flex items-center justify-between gap-2 rounded-lg border border-border bg-background px-3 py-2 text-xs"
              >
                <span className="flex items-center gap-2 truncate">
                  {t.status === "failed" ? (
                    <AlertTriangle size={14} className="shrink-0 text-destructive" />
                  ) : TERMINAL_STATUSES.includes(t.status) ? (
                    <CheckCircle2 size={14} className="shrink-0 text-emerald-500" />
                  ) : (
                    <Loader2 size={14} className="shrink-0 animate-spin text-primary" />
                  )}
                  <span className="truncate font-medium">{t.fileName}</span>
                </span>
                <span className="flex shrink-0 items-center gap-2">
                  <Badge
                    variant={t.status === "failed" ? "destructive" : "outline"}
                    className="shrink-0 text-[10px] font-bold uppercase"
                    title={t.error}
                  >
                    {t.status}
                  </Badge>
                  {t.documentId && (
                    <button
                      onClick={() => handleDeleteTracked(t.documentId!)}
                      disabled={deletingIds.has(t.documentId)}
                      title="Delete this document"
                      className="text-muted-foreground hover:text-destructive disabled:opacity-50"
                    >
                      {deletingIds.has(t.documentId) ? (
                        <Loader2 size={13} className="animate-spin" />
                      ) : (
                        <Trash2 size={13} />
                      )}
                    </button>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
