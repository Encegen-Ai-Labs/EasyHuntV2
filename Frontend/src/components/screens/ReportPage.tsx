"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Download,
  FileText,
  FileOutput,
  Loader2,
  Lock,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { apiClient, type ReportDraft, type ReportFormat } from "@/services/api/client";
import { useCaseById, useCaseProgress } from "@/services/api/hooks";
import { useToast } from "@/context/ToastContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CaseStepper } from "@/components/case/CaseStepper";
import { StepGuide } from "@/components/case/StepGuide";
import { PageHeader } from "@/components/case/PageHeader";
import { BankFormEditor, TitleSearchEditor } from "@/components/report/DraftEditors";

// Drafts are kept in this browser only. They are not sent to the server until
// the lawyer downloads, so they do not follow the lawyer to another computer.
const storageKey = (caseId: string, formatId: string) => `easyhunt:report-draft:v2:${caseId}:${formatId}`;

interface SavedDraft {
  draft: ReportDraft;
  approved: boolean;
  savedAt: string;
}

function loadSaved(caseId: string, formatId: string): SavedDraft | null {
  try {
    const raw = localStorage.getItem(storageKey(caseId, formatId));
    return raw ? (JSON.parse(raw) as SavedDraft) : null;
  } catch {
    return null;
  }
}

function saveDraft(caseId: string, formatId: string, value: SavedDraft) {
  try {
    localStorage.setItem(storageKey(caseId, formatId), JSON.stringify(value));
  } catch {
    // Private windows or full storage: the report still works, it just is not remembered.
  }
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

const UPLOAD_OPTION = "__upload__";

export function ReportPage() {
  const params = useParams();
  const caseId = (params?.id as string) || "";
  const toast = useToast();

  const { data: caseData } = useCaseById(caseId);
  const caseDetails = caseData?.data;
  const { approved, total, isLoading: progressLoading } = useCaseProgress(caseId);

  const [formats, setFormats] = useState<ReportFormat[]>([]);
  const [formatsError, setFormatsError] = useState<string | null>(null);
  const [formatId, setFormatId] = useState("");
  const [draft, setDraft] = useState<ReportDraft | null>(null);
  const [reportApproved, setReportApproved] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [creatingError, setCreatingError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<"docx" | "pdf" | null>(null);
  const [confirmRebuild, setConfirmRebuild] = useState(false);

  useEffect(() => {
    if (!caseId) return;
    void apiClient.reportGenerator.formats(caseId).then((result) => {
      if (result.success && result.data) setFormats(result.data);
      else setFormatsError(result.error || "Could not load the report formats.");
    });
  }, [caseId]);

  const banks = useMemo(() => formats.filter((f) => f.kind === "bank"), [formats]);
  const titleSearch = formats.find((f) => f.kind === "title_search");

  const createDraft = useCallback(
    async (id: string) => {
      setIsCreating(true);
      setCreatingError(null);
      const result = await apiClient.reportGenerator.createDraft(caseId, id);
      setIsCreating(false);
      if (result.success && result.data) {
        setDraft(result.data);
        setReportApproved(false);
        setSavedAt(null);
        // Replace any older saved draft, so reopening this page shows this one.
        saveDraft(caseId, id, { draft: result.data, approved: false, savedAt: new Date().toISOString() });
      } else {
        setDraft(null);
        setCreatingError(result.error || "Could not create the report.");
      }
    },
    [caseId]
  );

  function handleChooseFormat(id: string) {
    setConfirmRebuild(false);
    setCreatingError(null);
    if (id === UPLOAD_OPTION) return; // shown as "coming soon"; not selectable
    setFormatId(id);
    setDraft(null);
    setReportApproved(false);
    if (!id) return;
    const saved = loadSaved(caseId, id);
    if (saved) {
      setDraft(saved.draft);
      setReportApproved(saved.approved);
      setSavedAt(saved.savedAt);
    } else {
      void createDraft(id);
    }
  }

  function handleEdit(next: ReportDraft) {
    setDraft(next);
    setReportApproved(false); // any change needs approving again
    const stamp = new Date().toISOString();
    setSavedAt(stamp);
    saveDraft(caseId, next.format_id, { draft: next, approved: false, savedAt: stamp });
  }

  function handleApproveToggle() {
    if (!draft) return;
    const next = !reportApproved;
    setReportApproved(next);
    const stamp = new Date().toISOString();
    setSavedAt(stamp);
    saveDraft(caseId, draft.format_id, { draft, approved: next, savedAt: stamp });
  }

  async function handleDownload(fileType: "docx" | "pdf") {
    if (!draft) return;
    setDownloading(fileType);
    const result = await apiClient.reportGenerator.exportDraft(caseId, draft, fileType);
    setDownloading(null);
    if (result.success && result.data) {
      triggerDownload(result.data.blob, result.data.filename);
      toast.success(`${result.data.filename} downloaded.`, "Report Ready");
    } else {
      toast.error(result.error || "Could not create the file", "Download Error");
    }
  }

  const emptyRequired = draft ? draft.fields.filter((f) => f.required && !f.value.trim()).length : 0;
  const header = (
    <PageHeader
      title={caseDetails?.title || caseDetails?.property_name || "Report"}
    />
  );

  // ---- locked: nothing approved yet ----
  if (!progressLoading && approved === 0) {
    return (
      <div className="min-h-screen bg-background px-4 py-8 md:px-6">
        <div className="mx-auto max-w-5xl">
          {header}
          <CaseStepper caseId={caseId} current="report" />
          <Card>
            <CardContent className="flex flex-col items-center gap-3 py-14 text-center">
              <Lock size={28} className="text-muted-foreground" />
              <p className="text-lg font-semibold">Approve a document to create a report</p>
              <p className="max-w-md text-sm text-muted-foreground">
                Reports are built only from documents you have checked and approved.
              </p>
              <Button nativeButton={false} render={<Link href={total === 0 ? `/cases/${caseId}` : `/cases/${caseId}/review`} />}>
                {total === 0 ? "Go to upload" : "Review & approve documents"}
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background px-4 py-8 pb-28 md:px-6">
      <div className="mx-auto max-w-5xl">
        {header}
        <CaseStepper caseId={caseId} current="report" />

        <StepGuide
          id="report"
          title="Step 4 of 4: make the report"
          steps={[
            "Choose the kind of report: a Title Search Report, or one of the bank formats.",
            "The report is filled in from your approved documents and the text you selected. Read every part and edit what needs changing.",
            "Download it as Word or PDF when you are happy with it.",
          ]}
          note="Opinions and remarks are never written for you. Those parts are left for you to complete."
        />

        <Card>
          <CardHeader className="border-b">
            <CardTitle className="flex items-center gap-2 text-lg">
              <FileText size={20} className="text-primary" /> Report
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-6">
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium">Report type</span>
              <select
                value={formatId}
                onChange={(e) => handleChooseFormat(e.target.value)}
                disabled={formats.length === 0 || isCreating}
                className="h-10 w-full rounded-lg border border-input bg-background px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 md:max-w-xl"
              >
                <option value="">{formats.length === 0 && !formatsError ? "Loading…" : "Choose a report…"}</option>
                {titleSearch && <option value={titleSearch.id}>{titleSearch.label}</option>}
                {banks.length > 0 && (
                  <optgroup label="Bank format reports">
                    {banks.map((bank) => (
                      <option key={bank.id} value={bank.id}>{bank.label}</option>
                    ))}
                  </optgroup>
                )}
                <optgroup label="Coming soon">
                  <option value={UPLOAD_OPTION} disabled>Upload a bank format to copy its layout (coming soon)</option>
                </optgroup>
              </select>
            </label>
            {formatsError && <p className="mt-2 text-sm text-destructive">{formatsError}</p>}
          </CardContent>
        </Card>

        {isCreating && (
          <p className="mt-6 flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
            <Loader2 size={16} className="animate-spin" /> Reading your documents…
          </p>
        )}

        {creatingError && (
          <p className="mt-6 flex items-start gap-2 rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            <AlertTriangle size={16} className="mt-0.5 shrink-0" /> {creatingError}
          </p>
        )}

        {draft && (
          <div className="mt-6 flex flex-col gap-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm text-muted-foreground">
                {savedAt ? `Saved on this computer at ${new Date(savedAt).toLocaleTimeString()}` : "Check each part, then approve."}
              </p>
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" size="sm" nativeButton={false} render={<Link href={`/cases/${caseId}/search`} />}>
                  <ArrowLeft size={14} data-icon="inline-start" />
                  Selections
                </Button>
                {confirmRebuild ? (
                  <>
                    <Button size="sm" variant="destructive" onClick={() => { setConfirmRebuild(false); void createDraft(draft.format_id); }}>
                      Yes, discard my edits and rebuild
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setConfirmRebuild(false)}>Keep my edits</Button>
                  </>
                ) : (
                  <Button variant="outline" size="sm" onClick={() => setConfirmRebuild(true)} title="Rebuild from the current documents and selections">
                    <RefreshCw size={14} data-icon="inline-start" />
                    Rebuild
                  </Button>
                )}
              </div>
            </div>

            {draft.warnings.map((warning) => (
              <p key={warning} className="flex items-start gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm text-accent-foreground">
                {warning}
              </p>
            ))}
            {draft.kind === "bank" && emptyRequired > 0 && (
              <p className="text-sm text-muted-foreground">
                {emptyRequired} required field{emptyRequired === 1 ? " is" : "s are"} still empty. Opinion fields are left
                for you on purpose.
              </p>
            )}

            {draft.kind === "title_search" ? (
              <TitleSearchEditor draft={draft} onChange={handleEdit} />
            ) : (
              <BankFormEditor draft={draft} onChange={handleEdit} />
            )}
          </div>
        )}
      </div>

      {draft && (
        <div className="fixed inset-x-0 bottom-0 z-40 border-t bg-background/95 px-4 py-3 backdrop-blur md:px-6">
          <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3">
            <Button variant={reportApproved ? "secondary" : "default"} onClick={handleApproveToggle}>
              {reportApproved ? <CheckCircle2 size={16} data-icon="inline-start" /> : <ShieldCheck size={16} data-icon="inline-start" />}
              {reportApproved ? "Approved. Edit again" : "Approve report"}
            </Button>
            <div className="flex items-center gap-2">
              {!reportApproved && <span className="hidden text-xs text-muted-foreground sm:inline">Approve to download</span>}
              <Button variant="outline" disabled={!reportApproved || downloading !== null} onClick={() => void handleDownload("docx")}>
                {downloading === "docx" ? <Loader2 size={15} className="animate-spin" data-icon="inline-start" /> : <Download size={15} data-icon="inline-start" />}
                Word
              </Button>
              <Button disabled={!reportApproved || downloading !== null} onClick={() => void handleDownload("pdf")}>
                {downloading === "pdf" ? <Loader2 size={15} className="animate-spin" data-icon="inline-start" /> : <Download size={15} data-icon="inline-start" />}
                PDF
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
