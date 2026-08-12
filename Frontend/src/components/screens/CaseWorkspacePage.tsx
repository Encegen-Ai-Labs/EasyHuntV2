"use client";

import React, { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
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
  Building,
  MapPin,
  FileCode,
  RotateCcw,
  Play,
} from "lucide-react";
import { apiClient, CaseRecord } from "@/services/api/client";
import { useToast } from "@/context/ToastContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";

export function CaseWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const caseId = (params?.id as string) || "PV-2408";
  const toast = useToast();

  const [caseDetails, setCaseDetails] = useState<CaseRecord | null>(null);
  const [isLoadingCase, setIsLoadingCase] = useState<boolean>(true);

  // Document Upload State (Step 3)
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [documentId, setDocumentId] = useState<string | null>(`doc-${caseId}`);
  const [docStatus, setDocStatus] = useState<string>("PROCESSING");
  const [docProgress, setDocProgress] = useState<number>(45);
  const [isRetryingPipeline, setIsRetryingPipeline] = useState<boolean>(false);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Load Case Details
  useEffect(() => {
    async function loadCase() {
      setIsLoadingCase(true);
      try {
        const data = await apiClient.cases.getById(caseId);
        setCaseDetails(data);
      } catch (err: any) {
        toast.error(err.message || "Failed to load case details", "Error");
      } finally {
        setIsLoadingCase(false);
      }
    }
    loadCase();
  }, [caseId]);

  // Handle File Drop & Select
  function handleFileDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  }

  function validateAndSetFile(file: File) {
    const validTypes = ["application/pdf", "image/png", "image/jpeg", "image/jpg"];
    const maxSize = 10 * 1024 * 1024; // 10MB

    if (!validTypes.includes(file.type)) {
      toast.error("Invalid file type. Allowed: PDF, PNG, JPG", "Validation Error");
      return;
    }
    if (file.size > maxSize) {
      toast.error("File size exceeds 10MB limit", "Validation Error");
      return;
    }
    setSelectedFile(file);
  }

  // Upload handler
  async function handleUploadFile() {
    if (!selectedFile) return;

    setIsUploading(true);
    setUploadProgress(0);
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const result = await apiClient.documents.upload(caseId, selectedFile, {
        signal: controller.signal,
        onProgress: (percent) => setUploadProgress(percent),
      });

      if (result.success) {
        const newDocId = result.data?.id || `doc-${Math.floor(Math.random() * 10000)}`;
        setDocumentId(newDocId);
        setDocStatus("PROCESSING");
        setDocProgress(60);
        toast.success(`Document uploaded for case ${caseId}!`, "Upload Complete");
      }
    } catch (err: any) {
      if (err.name === "AbortError") {
        toast.info("Upload canceled by user", "Canceled");
      } else {
        toast.error(err.message || "Upload failed", "Error");
      }
    } finally {
      setIsUploading(false);
    }
  }

  // Retry Pipeline Action
  async function handleRetryPipeline() {
    if (!documentId) return;
    setIsRetryingPipeline(true);
    try {
      await apiClient.documents.process(documentId);
      setDocStatus("PROCESSING");
      setDocProgress(75);
      toast.success(`Processing pipeline re-triggered for document ${documentId}`, "Pipeline Initiated");
    } catch (err: any) {
      toast.error(err.message || "Failed to trigger pipeline retry", "Pipeline Error");
    } finally {
      setIsRetryingPipeline(false);
    }
  }

  return (
    <div className="min-h-screen bg-background px-4 py-8 md:px-6">
      <div className="mx-auto max-w-6xl">
        {/* Page header */}
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b pb-4">
          <div>
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="font-mono text-xs font-bold">
                {caseId}
              </Badge>
              <Badge variant="secondary">{caseDetails?.status || "Draft"}</Badge>
            </div>
            <h1 className="mt-1 text-3xl font-bold tracking-tight">
              {caseDetails?.title || caseDetails?.property_name || `Case Workspace ${caseId}`}
            </h1>
            <p className="mt-1 text-xs text-muted-foreground flex items-center gap-3">
              <span className="flex items-center gap-1"><MapPin size={13} /> {caseDetails?.address || caseDetails?.location || "Miami, FL"}</span>
              <span className="flex items-center gap-1"><FileCode size={13} /> Survey No: {caseDetails?.survey_number || "SV-9912"}</span>
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => router.push(`/review?caseId=${caseId}`)}
            >
              Open Review Workspace
              <ArrowRight size={14} data-icon="inline-end" />
            </Button>
          </div>
        </div>

        {/* Step 3: Document Upload Interface Reveal */}
        <div className="grid gap-6 md:grid-cols-[1fr_340px]">
          {/* Main Dropzone & Ingestion Interface */}
          <Card>
            <CardHeader className="border-b">
              <CardTitle className="text-lg flex items-center gap-2">
                <UploadCloud size={20} className="text-primary" />
                Step 3: Case Document Ingestion
              </CardTitle>
              <CardDescription>
                Upload legal deeds, title insurance policies, tax filings, or survey maps (under 10MB, PDF/PNG/JPG).
              </CardDescription>
            </CardHeader>

            <CardContent className="pt-6 flex flex-col gap-6">
              {/* Dropzone */}
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
                  id="workspace-file"
                  className="absolute inset-0 opacity-0 cursor-pointer"
                  onChange={handleFileSelect}
                  accept=".pdf,.png,.jpg,.jpeg"
                  disabled={isUploading}
                />

                <span className="flex size-14 items-center justify-center rounded-2xl bg-secondary text-secondary-foreground shadow-sm">
                  <UploadCloud size={28} />
                </span>

                <h3 className="mt-4 text-base font-semibold">
                  {selectedFile ? selectedFile.name : "Drag and drop document to attach to case"}
                </h3>
                <p className="mt-1 text-xs text-muted-foreground">
                  PDF, PNG, JPG up to 10MB
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

              {/* Upload Progress */}
              {isUploading && (
                <div className="rounded-xl border border-primary/20 bg-primary/5 p-4">
                  <div className="flex items-center justify-between text-xs font-semibold">
                    <span className="flex items-center gap-2 text-primary">
                      <Loader2 size={14} className="animate-spin" />
                      Uploading multipart payload… ({uploadProgress}%)
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => abortControllerRef.current?.abort()}
                      className="h-7 text-xs text-destructive hover:bg-destructive/10"
                    >
                      Cancel
                    </Button>
                  </div>
                  <Progress value={uploadProgress} className="mt-2.5 h-2" />
                </div>
              )}
            </CardContent>

            <CardFooter className="border-t flex justify-end gap-3 pt-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedFile(null)}
                disabled={isUploading || !selectedFile}
              >
                Clear
              </Button>
              <Button
                size="sm"
                onClick={handleUploadFile}
                disabled={isUploading || !selectedFile}
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
                    Submit Document Upload
                  </>
                )}
              </Button>
            </CardFooter>
          </Card>

          {/* Right Sidebar: Pipeline Actions & Retry Control */}
          <div className="flex flex-col gap-6">
            <Card>
              <CardHeader className="border-b">
                <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                  Extraction Pipeline Controls
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-4 flex flex-col gap-4">
                <div>
                  <div className="flex items-center justify-between text-xs font-medium">
                    <span className="text-muted-foreground">Attached Document</span>
                    <span className="font-mono font-bold text-foreground">{documentId}</span>
                  </div>

                  <div className="mt-3 flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">Status</span>
                    <Badge variant="outline" className="font-bold uppercase text-[10px]">
                      {docStatus}
                    </Badge>
                  </div>

                  <div className="mt-4">
                    <div className="flex items-center justify-between text-xs font-medium mb-1">
                      <span>OCR & LLM Execution</span>
                      <span>{docProgress}%</span>
                    </div>
                    <Progress value={docProgress} className="h-2" />
                  </div>
                </div>

                {/* Retry Pipeline Trigger Button */}
                <div className="mt-4 border-t pt-4">
                  <p className="text-xs text-muted-foreground mb-3">
                    If extraction flags an error or fails, re-trigger the automated processing pipeline.
                  </p>

                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleRetryPipeline}
                    disabled={isRetryingPipeline}
                    className="w-full gap-2 justify-center"
                  >
                    {isRetryingPipeline ? (
                      <>
                        <Loader2 size={14} className="animate-spin" />
                        Triggering Pipeline…
                      </>
                    ) : (
                      <>
                        <RotateCcw size={14} />
                        Retry Pipeline Trigger
                      </>
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
