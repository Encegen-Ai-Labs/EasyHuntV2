"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
  Calendar,
  CheckCircle2,
  Clock,
  Download,
  FileText,
  ShieldCheck,
  Loader2,
  RefreshCw,
  AlertTriangle,
} from "lucide-react";
import { apiClient } from "@/services/api/client";
import { useToast } from "@/context/ToastContext";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

function ReportContent() {
  const searchParams = useSearchParams();
  const caseIdParam = searchParams.get("caseId") || "PV-2408";
  const toast = useToast();

  const [caseId, setCaseId] = useState<string>(caseIdParam);
  const [reportData, setReportData] = useState<any>(null);
  const [isLoadingSummary, setIsLoadingSummary] = useState<boolean>(false);
  const [isDownloadingPdf, setIsDownloadingPdf] = useState<boolean>(false);

  // Load summary on mount
  async function fetchSummary() {
    setIsLoadingSummary(true);
    try {
      const summary = await apiClient.reports.getSummary(caseId);
      setReportData(summary);
      toast.success(`Executive report generated for case ${caseId}`, "Report Loaded");
    } catch (err: any) {
      toast.error(err.message || "Failed to load report summary", "Report Error");
    } finally {
      setIsLoadingSummary(false);
    }
  }

  useEffect(() => {
    fetchSummary();
  }, [caseId]);

  // Download PDF Blob Handler
  async function handleDownloadPdf() {
    setIsDownloadingPdf(true);
    try {
      await apiClient.reports.downloadPdf(caseId);
      toast.success(`Report-${caseId}.pdf downloaded successfully!`, "Export Complete");
    } catch (err: any) {
      toast.error(err.message || "Failed to compile PDF report", "Download Failed");
    } finally {
      setIsDownloadingPdf(false);
    }
  }

  return (
    <div className="min-h-screen bg-background px-4 py-10">
      <div className="mx-auto max-w-6xl">
        {/* Header */}
        <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Executive Report Hub</p>
            <h1 className="mt-1 text-3xl font-bold tracking-tight">{caseId} / Meridian Avenue</h1>
          </div>

          <div className="flex items-center gap-3">
            {/* Generate Report Summary Button */}
            <Button
              variant="outline"
              size="sm"
              onClick={fetchSummary}
              disabled={isLoadingSummary}
            >
              <RefreshCw size={14} className={isLoadingSummary ? "animate-spin" : ""} data-icon="inline-start" />
              {isLoadingSummary ? "Compiling…" : "Generate Report Summary"}
            </Button>

            {/* Download PDF Report Button */}
            <Button
              size="sm"
              onClick={handleDownloadPdf}
              disabled={isDownloadingPdf}
              className="bg-primary text-primary-foreground font-semibold gap-2"
            >
              {isDownloadingPdf ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Compiling PDF…
                </>
              ) : (
                <>
                  <Download size={16} />
                  Download PDF Report
                </>
              )}
            </Button>
          </div>
        </header>

        {/* Stats strip */}
        <section className="grid gap-4 md:grid-cols-4">
          {[
            {
              title: "Property Specs",
              value: reportData?.property_specs?.type || "Residential",
              detail: reportData?.property_specs?.size || "2,140 SF",
              icon: <FileText size={16} />,
            },
            {
              title: "Cleared Items",
              value: String(reportData?.cleared_items ?? "07"),
              detail: "No open issues",
              icon: <CheckCircle2 size={16} />,
            },
            {
              title: "Resolved Risks",
              value: String(reportData?.resolved_risks ?? "02"),
              detail: "Low confidence fields",
              icon: <ShieldCheck size={16} />,
            },
            {
              title: "Audit Trail",
              value: String(reportData?.audit_trail_events ?? "14"),
              detail: "Events logged",
              icon: <Clock size={16} />,
            },
          ].map(({ title, value, detail, icon }) => (
            <Card key={title} size="sm">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <span className="flex size-8 items-center justify-center rounded-md bg-secondary text-secondary-foreground">
                    {icon}
                  </span>
                  <Badge variant="secondary" className="text-[10px]">Verified</Badge>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">{title}</p>
                <div className="mt-1 text-2xl font-bold tracking-tight">{value}</div>
                <div className="text-xs text-muted-foreground">{detail}</div>
              </CardContent>
            </Card>
          ))}
        </section>

        {/* Detail cards */}
        <section className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <Card>
            <CardHeader className="border-b">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Executive Summary</p>
                  <CardTitle className="mt-1">Property Risk Assessment</CardTitle>
                </div>
                <Badge variant="secondary">Cleared</Badge>
              </div>
            </CardHeader>
            <CardContent className="flex flex-col gap-3 pt-4">
              <RiskLine label="Title Ownership" value={reportData?.summary?.title_ownership || "Clear"} warning={false} />
              <RiskLine label="Financial Exposure" value={reportData?.summary?.financial_exposure || "Low"} warning={false} />
              <RiskLine label="Open Encumbrances" value={reportData?.summary?.open_encumbrances || "01 warning"} warning />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="border-b">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Audit Trail</p>
                  <CardTitle className="mt-1">Reviewer Activity Log</CardTitle>
                </div>
                <Button variant="secondary" size="sm">Today</Button>
              </div>
            </CardHeader>
            <CardContent className="flex flex-col gap-4 pt-4">
              {(reportData?.audit_trail || [
                { time: "08:14 AM", action: "OCR extraction completed", user: "AI Pipeline" },
                { time: "09:02 AM", action: "Title fields reviewed", user: "Avery Johnson" },
                { time: "09:46 AM", action: "Risk flag resolved", user: "Mia Rivera" },
              ]).map((item: any, idx: number) => (
                <AuditRow key={idx} time={item.time} action={item.action} user={item.user} />
              ))}
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
}

function RiskLine({ label, value, warning }: { label: string; value: string; warning: boolean }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-border px-4 py-3">
      <div>
        <div className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">{label}</div>
        <div className="mt-1 text-sm font-medium">{value}</div>
      </div>
      <Badge variant={warning ? "outline" : "secondary"}>{warning ? "Warning" : "Clear"}</Badge>
    </div>
  );
}

function AuditRow({ time, action, user }: { time: string; action: string; user: string }) {
  return (
    <div className="flex items-start gap-3">
      <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
        <Calendar size={13} />
      </span>
      <div>
        <div className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">{time}</div>
        <div className="mt-0.5 text-sm font-medium">{action}</div>
        <div className="text-xs text-muted-foreground">{user}</div>
      </div>
    </div>
  );
}

export function ReportPage() {
  return (
    <Suspense fallback={<div className="p-10 text-center"><Loader2 size={28} className="animate-spin mx-auto text-primary" /></div>}>
      <ReportContent />
    </Suspense>
  );
}
