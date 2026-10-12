"use client";

import React, { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, ArrowRight, UploadCloud, FileText, X, Loader2, Ban } from "lucide-react";
import { apiClient } from "@/services/api/client";
import { useToast } from "@/context/ToastContext";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

const ALLOWED_TYPES = ["application/pdf", "image/png", "image/jpeg", "image/jpg"];
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const MAX_BATCH_SIZE = 20;
interface BatchUploadPanelProps {
  caseId: string;
  /** Called once per successful upload batch, after results are known (not after processing finishes). */
  onUploaded?: () => void;
}

export function BatchUploadPanel({ caseId, onUploaded }: BatchUploadPanelProps) {
  const router = useRouter();
  const toast = useToast();

  const [queuedFiles, setQueuedFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  // How many files the last upload accepted; drives the "check the extracted
  // fields" notice, which stays until the lawyer dismisses it.
  const [uploadedCount, setUploadedCount] = useState(0);
  // Files the server refused or could not store, with the reason, until retried or dismissed.
  const [failedFiles, setFailedFiles] = useState<{ file: File; error: string }[]>([]);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [queueWarning, setQueueWarning] = useState<string | null>(null);
  // When the same file was extracted before, its saved result is reused. A
  // lawyer who re-uploads because that read looked wrong ticks this to get a
  // fresh extraction instead.
  const [forceRefresh, setForceRefresh] = useState(false);

  const abortControllerRef = useRef<AbortController | null>(null);

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

  async function handleUpload() {
    if (queuedFiles.length === 0) return;

    setIsUploading(true);
    setUploadProgress(0);
    setFailedFiles([]);
    setRequestError(null);
    const submitted = queuedFiles;
    const controller = new AbortController();
    abortControllerRef.current = controller;

    const result = await apiClient.documents.upload(caseId, queuedFiles, {
      signal: controller.signal,
      onProgress: setUploadProgress,
      forceRefresh,
    });

    setIsUploading(false);
    setForceRefresh(false);
    abortControllerRef.current = null;

    if (!result.success || !result.data) {
      setRequestError(result.error || "The upload could not be completed.");
      toast.error(result.error || "Batch upload failed", "Upload Error");
      return;
    }

    const succeeded = result.data.results.filter((r) => r.success).length;
    const failed = result.data.results.length - succeeded;

    setQueuedFiles([]);
    // Results come back in the order the files were sent.
    setFailedFiles(
      result.data.results
        .map((r, index) => ({ r, file: submitted[index] }))
        .filter(({ r, file }) => !r.success && file)
        .map(({ r, file }) => ({ file, error: r.error || "The file could not be uploaded." }))
    );

    if (succeeded > 0) {
      setUploadedCount(succeeded);
      toast.success(
        `${succeeded} document${succeeded === 1 ? "" : "s"} uploaded. Reading has started.`,
        "Upload Complete"
      );
      onUploaded?.();
    }
    if (failed > 0) {
      toast.error(`${failed} file${failed === 1 ? "" : "s"} failed to upload`, "Some Files Failed");
    }
    setQueueWarning(result.data.warning ?? null);
    if (result.data.warning) {
      toast.warning(result.data.warning, "Processing Queue Unavailable");
    }
    for (const fileResult of result.data.results) {
      if (fileResult.error) {
        toast.error(`${fileResult.file_name}: ${fileResult.error}`, "Processing Queue Error");
      }
    }
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

      {queuedFiles.length > 0 && (
        <label className="flex items-start gap-2 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={forceRefresh}
            onChange={(e) => setForceRefresh(e.target.checked)}
            disabled={isUploading}
            className="mt-0.5"
          />
          <span>
            <span className="font-medium text-foreground">Ignore saved results</span> — if one of these files was
            extracted before, read it again from scratch instead of reusing that result.
          </span>
        </label>
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

      {queueWarning && (
        <p className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          {queueWarning}
        </p>
      )}

      {requestError && (
        <div role="alert" className="rounded-lg bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <p className="font-medium">Nothing was uploaded.</p>
          <p className="mt-0.5">{requestError}</p>
        </div>
      )}

      {failedFiles.length > 0 && (
        <div role="alert" className="rounded-lg bg-destructive/10 px-4 py-3 text-sm">
          <p className="font-medium text-destructive">
            {failedFiles.length} file{failedFiles.length === 1 ? " was" : "s were"} not uploaded
          </p>
          <ul className="mt-1.5 flex flex-col gap-1">
            {failedFiles.map(({ file, error }) => (
              <li key={file.name} className="text-destructive">
                <span className="font-medium">{file.name}</span>
                <span className="text-destructive/80">: {error}</span>
              </li>
            ))}
          </ul>
          <div className="mt-3 flex gap-2">
            <Button
              size="sm"
              onClick={() => {
                setQueuedFiles(failedFiles.map((f) => f.file));
                setFailedFiles([]);
              }}
            >
              Retry {failedFiles.length === 1 ? "this file" : "these files"}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setFailedFiles([])}>Dismiss</Button>
          </div>
        </div>
      )}

      {uploadedCount > 0 && (
        <div role="status" className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-accent px-4 py-3 text-sm text-accent-foreground">
          <p>
            <span className="font-semibold">{uploadedCount} uploaded.</span> Check names, numbers and dates against the
            original before you approve.
          </p>
          <div className="flex shrink-0 gap-2">
            <Button variant="ghost" size="sm" onClick={() => setUploadedCount(0)}>Dismiss</Button>
            <Button size="sm" onClick={() => router.push(`/cases/${caseId}/review`)}>
              Review
              <ArrowRight size={14} data-icon="inline-end" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
