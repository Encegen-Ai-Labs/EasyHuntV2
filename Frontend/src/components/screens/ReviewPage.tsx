"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
  Eye,
  FileSearch,
  Minus,
  Plus,
  ZoomIn,
  Loader2,
  CheckCircle2,
  XCircle,
  Save,
  RefreshCw,
  FileText,
  AlertTriangle,
  Flag,
  CheckCheck,
  Download,
  Play,
  ShieldAlert,
  Send,
  ExternalLink,
} from "lucide-react";
import { apiClient, CaseRecord, FlagItem } from "@/services/api/client";
import { useToast } from "@/context/ToastContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/Input";

function severityVariant(severity: string): "default" | "secondary" | "destructive" | "outline" {
  const s = severity.toLowerCase();
  if (s === "critical") return "destructive";
  if (s === "high") return "destructive";
  if (s === "medium") return "outline";
  return "secondary";
}

function ReviewContent() {
  const searchParams = useSearchParams();
  const caseIdParam = searchParams.get("caseId") || "PV-2408";
  const toast = useToast();

  const [pendingQueue, setPendingQueue] = useState<CaseRecord[]>([]);
  const [isQueueLoading, setIsQueueLoading] = useState<boolean>(true);

  const [selectedCaseId, setSelectedCaseId] = useState<string>(caseIdParam);
  const [documentId, setDocumentId] = useState<string>(`doc-${caseIdParam}`);

  // Editable Extraction State (validated_output, review_notes)
  const [jsonText, setJsonText] = useState<string>(
    JSON.stringify(
      {
        owner: "Meridian Holdings LLC",
        title_status: "Clear",
        deed_type: "Warranty Deed",
        fair_market_value: "$845,000",
        tax_assessment: "$736,180",
        mortgage_balance: "$417,500",
        tax_lien: "None",
        open_judgment: "Monroe County",
      },
      null,
      2
    )
  );
  const [reviewNotes, setReviewNotes] = useState<string>("Validated against county deeds registry.");
  const [isSubmittingDecision, setIsSubmittingDecision] = useState<boolean>(false);

  // Risk Flags State
  const [flags, setFlags] = useState<FlagItem[]>([]);
  const [isLoadingFlags, setIsLoadingFlags] = useState<boolean>(false);
  const [isRaiseModalOpen, setIsRaiseModalOpen] = useState<boolean>(false);
  const [flagType, setFlagType] = useState<string>("Title Discrepancy");
  const [flagSeverity, setFlagSeverity] = useState<"low" | "medium" | "high" | "critical">("high");
  const [flagDesc, setFlagDesc] = useState<string>("");
  const [isSubmittingFlag, setIsSubmittingFlag] = useState<boolean>(false);
  const [resolvingFlagId, setResolvingFlagId] = useState<string | null>(null);

  // Finalization & Report State
  const [isFinalizingChain, setIsFinalizingChain] = useState<boolean>(false);
  const [isFinalizingDecision, setIsFinalizingDecision] = useState<boolean>(false);
  const [isGeneratingReport, setIsGeneratingReport] = useState<boolean>(false);
  const [pdfDownloadUrl, setPdfDownloadUrl] = useState<string | null>(null);

  // Load Pending Queue (GET /api/v1/review/pending)
  async function loadPendingQueue() {
    setIsQueueLoading(true);
    try {
      const pending = await apiClient.review.getPending();
      setPendingQueue(pending || []);
    } catch (err: any) {
      toast.error(err.message || "Failed to load pending queue", "Error");
    } finally {
      setIsQueueLoading(false);
    }
  }

  // Load Case Flags (GET /api/v1/flags?case_id={id})
  async function loadFlags(cId: string) {
    setIsLoadingFlags(true);
    try {
      const data = await apiClient.flags.list(cId);
      setFlags(data || []);
    } catch (err: any) {
      toast.error(err.message || "Failed to load risk flags", "Error");
    } finally {
      setIsLoadingFlags(false);
    }
  }

  useEffect(() => {
    loadPendingQueue();
  }, []);

  useEffect(() => {
    if (selectedCaseId) {
      setDocumentId(`doc-${selectedCaseId}`);
      loadFlags(selectedCaseId);
      setPdfDownloadUrl(null);
    }
  }, [selectedCaseId]);

  // Document Decision Actions (PATCH /api/v1/review/documents/{document_id})
  async function handleDocumentDecision(decision: "approved" | "rejected") {
    let parsedJson: Record<string, any> = {};
    try {
      parsedJson = JSON.parse(jsonText);
    } catch (e) {
      toast.error("Invalid JSON in validated_output field", "Syntax Error");
      return;
    }

    setIsSubmittingDecision(true);
    try {
      await apiClient.review.submitDocumentDecision(documentId, {
        validated_output: parsedJson,
        review_notes: reviewNotes,
        decision: decision,
      });

      if (decision === "approved") {
        toast.success(`Document ${documentId} saved & approved!`, "Document Approved");
      } else {
        toast.error(`Document ${documentId} marked as rejected.`, "Document Rejected");
      }
      loadPendingQueue();
    } catch (err: any) {
      toast.error(err.message || "Failed to submit document decision", "Error");
    } finally {
      setIsSubmittingDecision(false);
    }
  }

  // Raise Risk Flag (POST /api/v1/flags/{case_id})
  async function handleRaiseFlag(e: React.FormEvent) {
    e.preventDefault();
    if (!flagDesc.trim()) {
      toast.error("Please enter a flag description", "Validation Error");
      return;
    }

    setIsSubmittingFlag(true);
    try {
      const newFlag = await apiClient.flags.raise(selectedCaseId, {
        flag_type: flagType,
        severity: flagSeverity,
        description: flagDesc,
      });

      toast.warning(`Raised ${flagSeverity.toUpperCase()} risk flag on case ${selectedCaseId}`, "Flag Raised");
      setIsRaiseModalOpen(false);
      setFlagDesc("");
      loadFlags(selectedCaseId);
    } catch (err: any) {
      toast.error(err.message || "Failed to raise risk flag", "Error");
    } finally {
      setIsSubmittingFlag(false);
    }
  }

  // Resolve Risk Flag (POST /api/v1/review/flag/{flag_id}/resolve)
  async function handleResolveFlag(flagId: string) {
    setResolvingFlagId(flagId);
    try {
      await apiClient.flags.resolve(flagId, "Verified against source document by reviewer", "resolved");
      toast.success(`Flag ${flagId} resolved cleanly`, "Flag Resolved");
      loadFlags(selectedCaseId);
    } catch (err: any) {
      toast.error(err.message || "Failed to resolve flag", "Error");
    } finally {
      setResolvingFlagId(null);
    }
  }

  // Chain Reconstruction Trigger (POST /api/v1/cases/{case_id}/finalize)
  async function handleFinalizeChain() {
    setIsFinalizingChain(true);
    try {
      await apiClient.cases.finalize(selectedCaseId);
      toast.success(`Chain reconstruction finalized for case ${selectedCaseId}!`, "Chain Executed");
    } catch (err: any) {
      toast.error(err.message || "Chain finalization failed", "Error");
    } finally {
      setIsFinalizingChain(false);
    }
  }

  // Final Case Decision (POST /api/v1/review/{case_id}/decision?decision=approve|reject)
  async function handleFinalCaseDecision(decision: "approve" | "reject") {
    setIsFinalizingDecision(true);
    try {
      await apiClient.review.finalizeCaseDecision(selectedCaseId, decision);
      if (decision === "approve") {
        toast.success(`Case ${selectedCaseId} officially APPROVED & completed!`, "Case Approved");
      } else {
        toast.error(`Case ${selectedCaseId} REJECTED.`, "Case Rejected");
      }
      loadPendingQueue();
    } catch (err: any) {
      toast.error(err.message || "Failed to submit final case decision", "Error");
    } finally {
      setIsFinalizingDecision(false);
    }
  }

  // Report Generation & Download (POST /api/v1/reports/generate/{case_id} & GET /api/v1/reports/download/{case_id})
  async function handleGeneratePdfReport() {
    setIsGeneratingReport(true);
    try {
      await apiClient.reports.generate(selectedCaseId);
      const downloadRes = await apiClient.reports.getDownloadUrl(selectedCaseId);
      if (downloadRes.download_url) {
        setPdfDownloadUrl(downloadRes.download_url);
        toast.success("PDF report generated successfully! Ready for download.", "Report Ready");
      }
    } catch (err: any) {
      toast.error(err.message || "Failed to generate PDF report", "Report Error");
    } finally {
      setIsGeneratingReport(false);
    }
  }

  function handleTriggerDownload() {
    if (pdfDownloadUrl) {
      window.open(pdfDownloadUrl, "_blank");
    } else {
      // Fallback direct endpoint download stream
      window.open(`${apiClient.baseUrl}/reports/cases/${selectedCaseId}/report/pdf`, "_blank");
    }
  }

  return (
    <div className="min-h-screen bg-background px-4 py-6">
      <div className="mx-auto max-w-[1800px]">
        {/* Workspace Header */}
        <header className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b pb-4">
          <div>
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="font-mono text-xs font-bold">{selectedCaseId}</Badge>
              <Badge variant="secondary">Review Workspace</Badge>
            </div>
            <h1 className="mt-1 text-2xl font-bold tracking-tight">
              Review Workspace // {selectedCaseId}
            </h1>
          </div>

          {/* Case Finalization & PDF Report Controls */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Chain Reconstruction Trigger */}
            <Button
              variant="outline"
              size="sm"
              onClick={handleFinalizeChain}
              disabled={isFinalizingChain}
              className="gap-1.5"
            >
              {isFinalizingChain ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Play size={14} className="text-primary" />
              )}
              Finalize & Run Chain
            </Button>

            {/* Final Case Decisions */}
            <Button
              size="sm"
              onClick={() => handleFinalCaseDecision("approve")}
              disabled={isFinalizingDecision}
              className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold gap-1.5"
            >
              <CheckCheck size={14} />
              Approve Case
            </Button>

            <Button
              variant="destructive"
              size="sm"
              onClick={() => handleFinalCaseDecision("reject")}
              disabled={isFinalizingDecision}
              className="font-semibold gap-1.5"
            >
              <XCircle size={14} />
              Reject Case
            </Button>

            {/* Report Generation & Signed URL Download */}
            {!pdfDownloadUrl ? (
              <Button
                variant="secondary"
                size="sm"
                onClick={handleGeneratePdfReport}
                disabled={isGeneratingReport}
                className="gap-1.5"
              >
                {isGeneratingReport ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <FileText size={14} />
                )}
                Generate PDF
              </Button>
            ) : (
              <Button
                size="sm"
                onClick={handleTriggerDownload}
                className="bg-primary text-primary-foreground font-bold gap-1.5 animate-in fade-in"
              >
                <Download size={14} />
                Download PDF
              </Button>
            )}
          </div>
        </header>

        {/* 3-Column Review Workspace */}
        <div className="grid gap-4 lg:grid-cols-[280px_1fr_440px]">
          {/* Column 1: Pending Queue (/review/pending) */}
          <Card className="h-full">
            <CardHeader className="border-b py-3 flex flex-row items-center justify-between">
              <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                Pending Queue (/review/pending)
              </CardTitle>
              <Button variant="ghost" size="sm" className="h-6 w-6 p-0" onClick={loadPendingQueue}>
                <RefreshCw size={12} className={isQueueLoading ? "animate-spin" : ""} />
              </Button>
            </CardHeader>
            <CardContent className="p-2 flex flex-col gap-2 overflow-y-auto max-h-[720px]">
              {isQueueLoading && (
                <div className="p-6 text-center text-xs text-muted-foreground">
                  <Loader2 size={18} className="animate-spin mx-auto mb-2" />
                  Loading pending queue…
                </div>
              )}
              {!isQueueLoading && pendingQueue.map((item) => (
                <div
                  key={item.id}
                  onClick={() => setSelectedCaseId(item.id)}
                  className={`cursor-pointer rounded-lg border p-3 transition-all ${
                    selectedCaseId === item.id
                      ? "border-primary bg-primary/10 shadow-sm"
                      : "border-border bg-card hover:bg-accent/50"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold font-mono">{item.id}</span>
                    <Badge variant="outline" className="text-[10px] font-semibold">
                      {item.status}
                    </Badge>
                  </div>
                  <div className="mt-1 text-sm font-semibold truncate">{item.title}</div>
                  <div className="mt-0.5 text-xs text-muted-foreground truncate">{item.address}</div>
                </div>
              ))}
            </CardContent>
          </Card>

          {/* Column 2: Split-View Inspector - Document Viewer */}
          <Card className="overflow-hidden">
            <CardHeader className="border-b py-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1">
                  <Button variant="ghost" size="sm"><Minus size={13} /></Button>
                  <Button variant="ghost" size="sm"><Plus size={13} /></Button>
                  <Button variant="ghost" size="sm"><ZoomIn size={13} /></Button>
                </div>
                <div className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5">
                  <FileText size={14} className="text-primary" />
                  <span>Document Inspector // {documentId}.pdf</span>
                </div>
              </div>
            </CardHeader>
            <CardContent className="min-h-[620px] bg-muted/20 p-6 flex items-center justify-center">
              <div
                className="relative w-full max-w-lg overflow-hidden rounded-xl border border-border bg-background shadow-lg p-8"
                style={{ minHeight: 540 }}
              >
                <div
                  className="absolute inset-0 opacity-25"
                  style={{
                    backgroundImage:
                      "repeating-linear-gradient(180deg, transparent 0px, transparent 24px, hsl(var(--border)) 25px)",
                  }}
                />
                <div className="relative">
                  <div className="flex items-center justify-between border-b pb-3">
                    <h3 className="text-2xl font-bold">{selectedCaseId} / Property Diligence</h3>
                    <Badge variant="secondary">PDF View</Badge>
                  </div>
                  <div className="mt-6 h-10 rounded-md border-2 border-ring/50 bg-ring/10" />
                  <div className="mt-24 h-16 rounded-md border-2 border-muted-foreground/30 bg-muted/30" />
                  <div className="mt-8 flex flex-col gap-3">
                    {["Owner Name & Grantee", "Title Warranty Classification", "County Encumbrance Index"].map((item) => (
                      <div key={item} className="border-b border-border pb-2 text-sm font-medium text-muted-foreground">
                        {item}
                      </div>
                    ))}
                  </div>
                </div>
                <div className="absolute bottom-4 right-4 flex items-center gap-2 rounded-full border border-border bg-background px-3 py-1 text-xs font-medium shadow-sm">
                  <span>Page 01 / 04</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Column 3: Editable AI Extraction JSON & Risk Flag Panel */}
          <div className="flex flex-col gap-4">
            {/* Split-View Inspector Right: Editable AI Extraction JSON */}
            <Card>
              <CardHeader className="border-b py-3 flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
                    Editable Extraction JSON (validated_output)
                  </CardTitle>
                </div>
              </CardHeader>
              <CardContent className="pt-3 flex flex-col gap-3">
                <div className="flex flex-col gap-1">
                  <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                    validated_output Payload
                  </label>
                  <textarea
                    className="w-full font-mono text-xs bg-muted/40 border rounded-lg p-3 outline-none focus:ring-2 focus:ring-ring"
                    rows={8}
                    value={jsonText}
                    onChange={(e) => setJsonText(e.target.value)}
                  />
                </div>

                <div className="flex flex-col gap-1">
                  <label className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                    review_notes
                  </label>
                  <Input
                    className="text-xs"
                    value={reviewNotes}
                    onChange={(e) => setReviewNotes(e.target.value)}
                    placeholder="Enter manual review notes..."
                  />
                </div>

                {/* Document Decision Actions */}
                <div className="mt-2 flex items-center gap-2">
                  <Button
                    size="sm"
                    onClick={() => handleDocumentDecision("approved")}
                    disabled={isSubmittingDecision}
                    className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white font-bold gap-1 text-xs"
                  >
                    {isSubmittingDecision ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
                    Save & Approve
                  </Button>

                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => handleDocumentDecision("rejected")}
                    disabled={isSubmittingDecision}
                    className="flex-1 font-bold gap-1 text-xs"
                  >
                    {isSubmittingDecision ? <Loader2 size={13} className="animate-spin" /> : <XCircle size={13} />}
                    Reject Document
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Risk Flag Panel */}
            <Card>
              <CardHeader className="border-b py-3 flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
                    <ShieldAlert size={14} className="text-amber-500" />
                    Risk Flag Panel
                  </CardTitle>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 text-xs gap-1"
                  onClick={() => setIsRaiseModalOpen(true)}
                >
                  <Flag size={13} />
                  Raise Flag
                </Button>
              </CardHeader>
              <CardContent className="pt-3 flex flex-col gap-2 max-h-[300px] overflow-y-auto">
                {isLoadingFlags && (
                  <div className="p-4 text-center text-xs text-muted-foreground">
                    <Loader2 size={16} className="animate-spin mx-auto mb-1" />
                    Loading flags…
                  </div>
                )}
                {!isLoadingFlags && flags.length === 0 && (
                  <div className="py-4 text-center text-xs text-muted-foreground">
                    No risk flags recorded for case {selectedCaseId}.
                  </div>
                )}
                {!isLoadingFlags && flags.map((flag) => (
                  <div key={flag.id} className="rounded-lg border border-border bg-card p-2.5 flex flex-col gap-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold">{flag.flag_type}</span>
                      <Badge variant={severityVariant(flag.severity)} className="text-[9px] font-bold uppercase">
                        {flag.severity}
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">{flag.description}</p>
                    <div className="mt-1 flex items-center justify-between">
                      <span className="text-[10px] text-muted-foreground uppercase font-mono">
                        Status: {flag.status}
                      </span>
                      {flag.status !== "resolved" && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleResolveFlag(flag.id)}
                          disabled={resolvingFlagId === flag.id}
                          className="h-6 text-[10px] text-emerald-500 hover:text-emerald-600 p-1"
                        >
                          {resolvingFlagId === flag.id ? (
                            <Loader2 size={11} className="animate-spin" />
                          ) : (
                            <CheckCircle2 size={11} className="mr-1" />
                          )}
                          Resolve Flag
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Raise Flag Modal */}
        {isRaiseModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-200">
            <div className="w-full max-w-md rounded-xl border border-border bg-background p-6 shadow-2xl">
              <div className="flex items-center gap-3">
                <span className="flex size-10 items-center justify-center rounded-lg bg-amber-500/10 text-amber-500">
                  <Flag size={20} />
                </span>
                <div>
                  <h3 className="text-lg font-bold">Raise Risk Flag</h3>
                  <p className="text-xs text-muted-foreground">POST /api/v1/flags/{selectedCaseId}</p>
                </div>
              </div>

              <form onSubmit={handleRaiseFlag} className="mt-5 flex flex-col gap-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                    Flag Type
                  </label>
                  <Input
                    placeholder="e.g. Title Discrepancy"
                    value={flagType}
                    onChange={(e) => setFlagType(e.target.value)}
                    required
                  />
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                    Severity Level
                  </label>
                  <select
                    className="h-9 rounded-lg border border-input bg-background px-3 text-xs font-semibold uppercase outline-none focus:border-ring cursor-pointer"
                    value={flagSeverity}
                    onChange={(e) => setFlagSeverity(e.target.value as any)}
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                    Description
                  </label>
                  <textarea
                    className="w-full rounded-lg border border-input bg-background p-3 text-xs text-foreground outline-none focus:ring-2 focus:ring-ring"
                    rows={3}
                    placeholder="Describe the discrepancy or risk flag..."
                    value={flagDesc}
                    onChange={(e) => setFlagDesc(e.target.value)}
                    required
                  />
                </div>

                <div className="mt-4 flex justify-end gap-3">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setIsRaiseModalOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" size="sm" disabled={isSubmittingFlag}>
                    {isSubmittingFlag ? (
                      <>
                        <Loader2 size={14} className="animate-spin" data-icon="inline-start" />
                        Submitting Flag…
                      </>
                    ) : (
                      "Raise Risk Flag"
                    )}
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function ReviewPage() {
  return (
    <Suspense fallback={<div className="p-10 text-center"><Loader2 size={28} className="animate-spin mx-auto text-primary" /></div>}>
      <ReviewContent />
    </Suspense>
  );
}
