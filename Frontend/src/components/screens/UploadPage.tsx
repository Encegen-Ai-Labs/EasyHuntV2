"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  UploadCloud,
  FileText,
  X,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Ban,
  ArrowRight,
  ShieldCheck,
} from "lucide-react";
import { apiClient } from "@/services/api/client";
import { useToast } from "@/context/ToastContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/Input";

export function UploadPage() {
  const router = useRouter();
  const toast = useToast();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [caseId, setCaseId] = useState<string>("PV-2408");
  const [propertyName, setPropertyName] = useState<string>("1800 Meridian Avenue");
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [docStatus, setDocStatus] = useState<string | null>(null);
  const [docProgress, setDocProgress] = useState<number>(0);
  const [isCheckingStatus, setIsCheckingStatus] = useState<boolean>(false);

  const abortControllerRef = useRef<AbortController | null>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // File selection dropzone handlers
  function handleFileDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      setSelectedFile(file);
    }
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  }

  // Upload handler with FormData, progress tracking, and AbortController
  async function handleUploadFile() {
    if (!selectedFile) {
      toast.error("Please select a file to upload", "Validation Error");
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const result = await apiClient.documents.upload(caseId, selectedFile, {
        signal: controller.signal,
        onProgress: (percent) => setUploadProgress(percent),
      });

      if (result.success && result.data) {
        const uploadedDocId = result.data.id || `doc-${Math.floor(Math.random() * 10000)}`;
        setDocumentId(uploadedDocId);
        setDocStatus("PROCESSING");
        setDocProgress(30);
        toast.success("Document uploaded successfully. Processing pipeline started.", "Upload Complete");
        startStatusPolling(uploadedDocId);
      } else {
        toast.error(result.error || "Document upload failed", "Upload Error");
      }
    } catch (err: any) {
      if (err.name === "AbortError" || err.message?.includes("canceled")) {
        toast.info("Upload operation canceled by user.", "Canceled");
      } else {
        toast.error(err.message || "Failed to upload document", "Upload Error");
      }
    } finally {
      setIsUploading(false);
      abortControllerRef.current = null;
    }
  }

  function handleCancelUpload() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setIsUploading(false);
      setUploadProgress(0);
    }
  }

  // Polling logic: 3-5 seconds interval
  function startStatusPolling(id: string) {
    stopStatusPolling();

    pollIntervalRef.current = setInterval(() => {
      checkDocumentStatus(id, true);
    }, 4000);
  }

  function stopStatusPolling() {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }

  async function checkDocumentStatus(id: string, isAutomatic = false) {
    if (!isAutomatic) setIsCheckingStatus(true);

    try {
      const statusRes = await apiClient.documents.getStatus(id);
      const currentStatus = (statusRes.status || "COMPLETED").toUpperCase();
      const currentProgress = statusRes.progress ?? (currentStatus === "COMPLETED" ? 100 : 75);

      setDocStatus(currentStatus);
      setDocProgress(currentProgress);

      if (!isAutomatic) {
        toast.info(`Current Status: ${currentStatus} (${currentProgress}%)`, "Status Checked");
      }

      // Stop polling automatically if completed, flagged, or failed
      if (["COMPLETED", "FLAGGED", "FAILED", "APPROVED", "REJECTED"].includes(currentStatus)) {
        stopStatusPolling();
        if (isAutomatic && currentStatus === "COMPLETED") {
          toast.success("Document processing finished! Extraction ready for review.", "Processing Complete");
        }
      }
    } catch (err: any) {
      console.warn("Status check failed:", err.message);
    } finally {
      if (!isAutomatic) setIsCheckingStatus(false);
    }
  }

  useEffect(() => {
    return () => {
      stopStatusPolling();
    };
  }, []);

  return (
    <div className="min-h-screen bg-background px-4 py-10">
      <div className="mx-auto max-w-4xl">
        {/* Page header */}
        <div className="mb-7 flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Document Infrastructure</p>
            <h1 className="mt-1 text-3xl font-bold tracking-tight">Upload Property Document</h1>
          </div>
          <Badge variant="secondary" className="gap-1">
            <ShieldCheck size={14} />
            Vendor Ingestion Mode
          </Badge>
        </div>

        <div className="grid gap-6 md:grid-cols-[1fr_320px]">
          {/* Main Dropzone Card */}
          <Card>
            <CardHeader className="border-b">
              <CardTitle>Case & File Specifications</CardTitle>
              <CardDescription>Upload deeds, title reports, tax disclosures, or mortgage filings for automated OCR extractions.</CardDescription>
            </CardHeader>

            <CardContent className="pt-6 flex flex-col gap-6">
              {/* Target Case Context */}
              <div className="grid gap-4 md:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                    Target Case ID
                  </label>
                  <Input value={caseId} onChange={(e) => setCaseId(e.target.value)} placeholder="PV-2408" />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                    Property Name
                  </label>
                  <Input value={propertyName} onChange={(e) => setPropertyName(e.target.value)} placeholder="Property Name" />
                </div>
              </div>

              {/* Drag and Drop Zone */}
              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleFileDrop}
                className={`relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center transition-all ${
                  selectedFile
                    ? "border-primary/50 bg-primary/5"
                    : "border-border bg-muted/20 hover:border-primary/40 hover:bg-muted/40"
                }`}
              >
                <input
                  type="file"
                  id="file-upload"
                  className="absolute inset-0 opacity-0 cursor-pointer"
                  onChange={handleFileSelect}
                  accept=".pdf,.jpg,.jpeg,.png,.tiff"
                  disabled={isUploading}
                />

                <span className="flex size-14 items-center justify-center rounded-2xl bg-secondary text-secondary-foreground shadow-sm">
                  <UploadCloud size={28} />
                </span>

                <h3 className="mt-4 text-base font-semibold">
                  {selectedFile ? selectedFile.name : "Drag and drop your document here"}
                </h3>
                <p className="mt-1 text-xs text-muted-foreground">
                  Supports PDF, PNG, JPG, and TIFF files up to 10MB
                </p>

                {selectedFile && (
                  <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-border bg-background px-3 py-1 text-xs font-semibold text-foreground">
                    <FileText size={14} className="text-primary" />
                    <span>{(selectedFile.size / (1024 * 1024)).toFixed(2)} MB</span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedFile(null);
                      }}
                      className="ml-1 text-muted-foreground hover:text-destructive"
                    >
                      <X size={14} />
                    </button>
                  </div>
                )}
              </div>

              {/* Upload Progress Bar */}
              {isUploading && (
                <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 animate-in fade-in duration-200">
                  <div className="flex items-center justify-between text-xs font-semibold">
                    <span className="flex items-center gap-2 text-primary">
                      <Loader2 size={14} className="animate-spin" />
                      Uploading file to secure storage… ({uploadProgress}%)
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleCancelUpload}
                      className="h-7 text-xs text-destructive hover:bg-destructive/10"
                    >
                      <Ban size={13} data-icon="inline-start" />
                      Cancel Upload
                    </Button>
                  </div>
                  <Progress value={uploadProgress} className="mt-2.5 h-2" />
                </div>
              )}
            </CardContent>

            <CardFooter className="border-t flex justify-end gap-3 pt-4">
              <Button
                variant="outline"
                onClick={() => setSelectedFile(null)}
                disabled={isUploading || !selectedFile}
              >
                Clear
              </Button>
              <Button
                onClick={handleUploadFile}
                disabled={isUploading || !selectedFile}
                className="gap-2"
              >
                {isUploading ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Uploading…
                  </>
                ) : (
                  <>
                    <UploadCloud size={16} />
                    Upload File
                  </>
                )}
              </Button>
            </CardFooter>
          </Card>

          {/* Sidebar Status Polling Card */}
          <div className="flex flex-col gap-6">
            <Card>
              <CardHeader className="border-b">
                <CardTitle className="text-sm font-bold uppercase tracking-wider text-muted-foreground">
                  Processing & Polling Status
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-4 flex flex-col gap-4">
                {documentId ? (
                  <div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-muted-foreground">Document ID</span>
                      <span className="text-xs font-mono font-bold">{documentId}</span>
                    </div>

                    <div className="mt-3 flex items-center justify-between">
                      <span className="text-xs text-muted-foreground">Current State</span>
                      <Badge
                        variant={
                          docStatus === "COMPLETED" || docStatus === "APPROVED"
                            ? "secondary"
                            : docStatus === "FAILED" || docStatus === "REJECTED"
                            ? "destructive"
                            : "outline"
                        }
                        className="text-xs font-bold uppercase"
                      >
                        {docStatus || "PENDING"}
                      </Badge>
                    </div>

                    <div className="mt-4">
                      <div className="flex items-center justify-between text-xs font-medium mb-1">
                        <span>Pipeline Progress</span>
                        <span>{docProgress}%</span>
                      </div>
                      <Progress value={docProgress} className="h-2" />
                    </div>

                    {["PROCESSING", "PENDING", "llm_running"].includes(docStatus || "") && (
                      <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground animate-pulse">
                        <Loader2 size={13} className="animate-spin text-primary" />
                        <span>Auto-polling status every 4 seconds…</span>
                      </div>
                    )}

                    <div className="mt-6 flex flex-col gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => checkDocumentStatus(documentId, false)}
                        disabled={isCheckingStatus}
                        className="w-full justify-center"
                      >
                        <RefreshCw size={14} className={isCheckingStatus ? "animate-spin" : ""} data-icon="inline-start" />
                        {isCheckingStatus ? "Checking…" : "Check Processing Status"}
                      </Button>

                      {["COMPLETED", "APPROVED", "under_review"].includes(docStatus || "") && (
                        <Button
                          size="sm"
                          onClick={() => router.push(`/review?caseId=${caseId}`)}
                          className="w-full justify-center gap-1 mt-1"
                        >
                          Proceed to Review
                          <ArrowRight size={14} />
                        </Button>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="py-8 text-center text-xs text-muted-foreground">
                    <p>No active upload session.</p>
                    <p className="mt-1">Upload a file to initiate automatic background status polling.</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
