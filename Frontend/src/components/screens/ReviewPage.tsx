"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { AlertTriangle, ArrowRight, CheckCircle2, Clock, Eye, FileWarning, Languages, Loader2, Pencil, Undo2 } from "lucide-react";
import {
  useCaseById,
  useDocumentPages,
  useEnhancedPageImageMutation,
  useReopenDocumentMutation,
  useReviewDocuments,
  useSubmitDocumentReviewMutation,
  useTranslateDocumentMutation,
  useUpdateDocumentPageMutation,
} from "@/services/api/hooks";
import type { DocumentRecord, ExtractionRecord } from "@/services/api/client";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";
import { Button } from "@/components/ui/button";
import { KeyboardInput, KeyboardTextarea } from "@/components/keyboard/KeyboardField";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FormattedText } from "@/components/text/FormattedText";
import { CaseStepper } from "@/components/case/CaseStepper";
import { StepGuide } from "@/components/case/StepGuide";
import { PageHeader } from "@/components/case/PageHeader";

// Keys the extraction prompt (backend/app/services/llm_extractor.py) returns
// alongside every field, e.g. "owner_name_confidence" — paired up with their
// base field below rather than shown as their own row.
const CONFIDENCE_SUFFIX = "_confidence";
// Written into extractions.validation_errors by the backend when a stored
// extraction of the same file was reused (backend/app/services/extraction_cache.py).
const CACHED_RESULT_PREFIX = "cached_result:";
// Rendered separately, not as a generic field row.
const SPECIAL_KEYS = new Set([
  "full_text",
  "chain",
  "has_handwritten_content",
  "overall_confidence",
  "unreadable_sections",
]);

function titleCase(key: string): string {
  return key
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function confidenceVariant(level?: string): "default" | "secondary" | "destructive" | "outline" {
  if (level === "high") return "secondary";
  if (level === "medium") return "outline";
  if (level === "low") return "destructive";
  return "outline";
}

function statusMeta(doc: DocumentRecord, extraction: ExtractionRecord | null) {
  if (extraction) {
    return null; // fields render below instead
  }
  switch (doc.status) {
    case "uploaded":
    case "processing":
      return { icon: Loader2, spin: true, text: "Extraction is still running for this document." };
    case "flagged":
      return { icon: FileWarning, spin: false, text: "Extraction failed for this document — no AI output was produced. Re-upload or retry processing." };
    default:
      return { icon: Clock, spin: false, text: "This document hasn't been processed yet." };
  }
}

function documentStatusLabel(doc: DocumentRecord, extraction: ExtractionRecord | null) {
  if (doc.status === "approved" || doc.status === "completed") {
    return { label: "Approved", variant: "secondary" as const };
  }
  if (doc.status === "rejected") return { label: "Flagged for correction", variant: "destructive" as const };
  if (!extraction) {
    return doc.status === "flagged"
      ? { label: "Needs attention", variant: "destructive" as const }
      : { label: "Reading…", variant: "outline" as const };
  }
  return { label: "Needs your review", variant: "outline" as const };
}

export function ReviewPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const toast = useToast();
  const { user } = useAuth();
  const isAdmin = user?.role === "Admin";

  const caseId =
    (params?.caseId as string) ||
    (params?.id as string) ||
    searchParams?.get("caseId") ||
    "";

  const { data: caseData } = useCaseById(caseId);
  const caseDetails = caseData?.data;

  const { data, isLoading, isError, error } = useReviewDocuments(caseId);
  const entries = useMemo(() => data?.data ?? [], [data]);
  const submitReview = useSubmitDocumentReviewMutation();
  const reopenDocument = useReopenDocumentMutation();

  const [activeDocId, setActiveDocId] = useState<string | null>(searchParams?.get("doc") ?? null);
  const [reviewNotes, setReviewNotes] = useState("");
  const [isEditingFields, setIsEditingFields] = useState(false);
  const [editedFields, setEditedFields] = useState<Record<string, any> | null>(null);

  // Which page's Original/English text (in the "Page Text" panel below) is
  // currently being edited, plus the in-progress values and what they
  // started as (so Save only sends the column(s) that actually changed —
  // editing English alone shouldn't also re-send an unchanged original_text
  // and trigger a needless re-embed, see
  // backend/app/api/v1/documents.py::update_document_page).
  const [editingPageNumber, setEditingPageNumber] = useState<number | null>(null);
  const [editedOriginalText, setEditedOriginalText] = useState("");
  const [editedEnglishText, setEditedEnglishText] = useState("");
  const [initialOriginalText, setInitialOriginalText] = useState("");
  const [initialEnglishText, setInitialEnglishText] = useState("");

  const approvedCount = entries.filter((e) => e.document.status === "approved" || e.document.status === "completed").length;
  const active = entries.find((e) => e.document.id === activeDocId) ?? entries[0] ?? null;

  // Discard any in-progress edits when switching documents — they were never
  // saved. Reset during render (React's recommended pattern for "adjusting
  // state when a prop/derived value changes") rather than an effect, so this
  // doesn't cause an extra render pass.
  const [lastActiveDocId, setLastActiveDocId] = useState(active?.document.id);
  if (active?.document.id !== lastActiveDocId) {
    setLastActiveDocId(active?.document.id);
    setIsEditingFields(false);
    setEditedFields(null);
    setEditingPageNumber(null);
  }

  const currentFields: Record<string, any> = editedFields ?? active?.extraction?.validated_json_output ?? {};
  const cachedNote = (active?.extraction?.validation_errors ?? []).find(
    (e): e is string => typeof e === "string" && e.startsWith(CACHED_RESULT_PREFIX)
  );

  // Optional "why was this changed" per edited field; saved with the correction.
  const [fieldReasons, setFieldReasons] = useState<Record<string, string>>({});

  function handleFieldChange(key: string, value: string) {
    setEditedFields({ ...currentFields, [key]: value });
  }

  // Only fields whose text actually differs from what is saved can have a reason.
  function reasonsForSave(): Record<string, string> | undefined {
    const saved = active?.extraction?.validated_json_output ?? {};
    const out: Record<string, string> = {};
    for (const [key, reason] of Object.entries(fieldReasons)) {
      if (reason && String(currentFields[key] ?? "") !== String(saved[key] ?? "")) out[key] = reason;
    }
    return Object.keys(out).length ? out : undefined;
  }

  const { data: pagesData, isLoading: pagesLoading } = useDocumentPages(active?.document.id ?? "");
  const pages = useMemo(() => pagesData?.data?.pages ?? [], [pagesData]);
  const translateDoc = useTranslateDocumentMutation();
  const updatePage = useUpdateDocumentPageMutation();
  const enhancedImage = useEnhancedPageImageMutation();

  // Admin-only diagnostic: opens the exact post-OpenCV-enhanced image
  // OCR/Gemini read for this page in a new tab — same "fetch a signed URL,
  // open it" pattern as the report builder's "Export PDF" button.
  async function handleViewEnhancedImage(pageNumber: number) {
    if (!active) return;
    const result = await enhancedImage.mutateAsync({ docId: active.document.id, pageNumber });
    if (result.success && result.data) {
      window.open(result.data.url, "_blank", "noopener,noreferrer");
    } else {
      toast.error(result.error || "Enhanced image not available for this page", "Error");
    }
  }

  function startEditingPage(pageNumber: number, originalText: string, englishText: string) {
    setEditingPageNumber(pageNumber);
    setEditedOriginalText(originalText);
    setEditedEnglishText(englishText);
    setInitialOriginalText(originalText);
    setInitialEnglishText(englishText);
  }

  function cancelEditingPage() {
    setEditingPageNumber(null);
  }

  async function saveEditingPage() {
    if (!active || editingPageNumber === null) return;
    const updates: { original_text?: string; english_text?: string } = {};
    if (editedOriginalText !== initialOriginalText) updates.original_text = editedOriginalText;
    if (editedEnglishText !== initialEnglishText) updates.english_text = editedEnglishText;
    if (Object.keys(updates).length === 0) {
      setEditingPageNumber(null);
      return;
    }
    const result = await updatePage.mutateAsync({
      docId: active.document.id,
      pageNumber: editingPageNumber,
      updates,
    });
    if (result.success) {
      toast.success("Page text updated.", "Saved");
      setEditingPageNumber(null);
    } else {
      toast.error(result.error || "Failed to save page edit", "Error");
    }
  }

  async function handleTranslate() {
    if (!active) return;
    const result = await translateDoc.mutateAsync(active.document.id);
    if (result.success) {
      toast.success("Document translated to English.", "Translation Complete");
    } else {
      toast.error(result.error || "Failed to translate document", "Error");
    }
  }

  async function handleDecision(decision: "approved" | "rejected") {
    if (!active?.extraction) return;
    const result = await submitReview.mutateAsync({
      documentId: active.document.id,
      caseId,
      payload: {
        validated_output: currentFields,
        review_notes: reviewNotes.trim() || undefined,
        decision,
        reasons: reasonsForSave(),
      },
    });
    if (result.success) {
      toast.success(decision === "approved" ? "Document approved." : "Document flagged for correction.", "Review Saved");
      setReviewNotes("");
      setFieldReasons({});
      setIsEditingFields(false);
      setEditedFields(null);
    } else {
      toast.error(result.error || "Failed to save review", "Error");
    }
  }

  async function handleUndoApproval() {
    if (!active) return;
    const result = await reopenDocument.mutateAsync({ documentId: active.document.id, caseId });
    if (result.success) {
      toast.success("Approval undone. You can edit this document again.", "Reopened");
    } else {
      toast.error(result.error || "Could not undo the approval", "Error");
    }
  }

  async function handleSaveFieldEdits() {
    if (!active?.extraction) return;
    // decision omitted — saves the edits without finalizing approve/reject.
    const result = await submitReview.mutateAsync({
      documentId: active.document.id,
      caseId,
      payload: { validated_output: currentFields, reasons: reasonsForSave() },
    });
    if (result.success) {
      setFieldReasons({});
      toast.success("Field edits saved.", "Saved");
      setIsEditingFields(false);
      setEditedFields(null);
    } else {
      toast.error(result.error || "Failed to save edits", "Error");
    }
  }

  if (!caseId) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <p className="text-sm text-muted-foreground">No case selected. Open a case from the Cases list.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background px-4 py-6">
      <div className="mx-auto max-w-[1800px]">
        <PageHeader
          title={caseDetails?.title || caseDetails?.property_name || "Case Review"}
          
        />

        <CaseStepper caseId={caseId} current="review" />

        <StepGuide
          id="review"
          title="Step 2 of 4: check each document, then approve it"
          steps={[
            "Pick a document on the left. The original is in the middle and the details we read from it are on the right.",
            "Compare each detail with the original. If one is wrong, press Edit and correct it (the अ button lets you type in Marathi).",
            "Press Approve when the document is right. Only approved documents can be searched and used in a report. You can undo an approval later.",
          ]}
          note="“Reading confidence” shows how sure the reader was. Low, or handwritten, means look closely."
        />

        <div className="mb-5 flex flex-wrap items-center justify-between gap-3 text-sm">
          <p className="text-muted-foreground">
            {approvedCount} of {entries.length} approved.
          </p>
          {approvedCount > 0 && (
            <Button nativeButton={false} render={<Link href={`/cases/${caseId}/search`} />}>
              Search {approvedCount} approved
              <ArrowRight size={15} data-icon="inline-end" />
            </Button>
          )}
        </div>

        {isLoading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 size={16} className="animate-spin" />
            Loading documents…
          </div>
        )}

        {isError && (
          <p className="text-sm font-medium text-destructive">
            {error instanceof Error ? error.message : "Unable to load review data."}
          </p>
        )}

        {!isLoading && !isError && entries.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No documents have been uploaded to this case yet. Go back to Upload and add some first.
          </p>
        )}

        {!isLoading && !isError && entries.length > 0 && (
          <div className="grid gap-4 lg:grid-cols-[240px_1fr_420px]">
            {/* Document selector */}
            <Card className="h-fit">
              <CardHeader className="border-b py-3">
                <CardTitle className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  Documents ({entries.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-1 p-2">
                {entries.map(({ document, extraction }) => (
                  <button
                    key={document.id}
                    onClick={() => setActiveDocId(document.id)}
                    className={`flex flex-col gap-1 rounded-lg px-3 py-2 text-left text-xs transition-colors ${
                      (active?.document.id ?? entries[0]?.document.id) === document.id
                        ? "bg-accent text-accent-foreground"
                        : "hover:bg-muted"
                    }`}
                  >
                    <span className="truncate font-medium">{document.file_name}</span>
                    <span className="flex items-center gap-1.5">
                      {(() => {
                        const status = documentStatusLabel(document, extraction);
                        return <Badge variant={status.variant} className="text-[10px]">{status.label}</Badge>;
                      })()}
                      {extraction?.has_handwritten_content && (
                        <span title="Contains handwritten content"><AlertTriangle size={11} className="text-amber-500" /></span>
                      )}
                    </span>
                  </button>
                ))}
              </CardContent>
            </Card>

            {/* Document preview */}
            <Card className="overflow-hidden">
              <CardHeader className="border-b py-2">
                <p className="truncate text-sm font-medium">{active?.document.file_name}</p>
              </CardHeader>
              <CardContent className="min-h-[600px] bg-muted/20 p-0">
                {active?.file_url ? (
                  active.document.mime_type?.startsWith("image/") ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={active.file_url} alt={active.document.file_name} className="mx-auto max-h-[900px] w-auto object-contain" />
                  ) : (
                    <iframe src={active.file_url} title={active.document.file_name} className="h-[900px] w-full border-0" />
                  )
                ) : (
                  <div className="flex min-h-[600px] items-center justify-center text-sm text-muted-foreground">
                    No preview available.
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Extracted fields */}
            <Card>
              <CardHeader className="border-b">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Check these against the original</p>
                    <CardTitle className="mt-1">Details read from this document</CardTitle>
                  </div>
                  {active?.extraction && !active.extraction.reviewed_at && (
                    <Button
                      variant={isEditingFields ? "secondary" : "outline"}
                      size="sm"
                      onClick={() => {
                        if (isEditingFields) {
                          setIsEditingFields(false);
                          setEditedFields(null);
                        } else {
                          setIsEditingFields(true);
                        }
                      }}
                    >
                      <Pencil size={13} data-icon="inline-start" />
                      {isEditingFields ? "Cancel" : "Edit"}
                    </Button>
                  )}
                </div>
              </CardHeader>
              <CardContent className="flex flex-col gap-4 pt-4">
                {active && !active.extraction && (() => {
                  const meta = statusMeta(active.document, active.extraction);
                  if (!meta) return null;
                  const Icon = meta.icon;
                  return (
                    <div className="flex items-start gap-2 rounded-lg border border-border bg-muted/30 p-3 text-sm text-muted-foreground">
                      <Icon size={16} className={meta.spin ? "animate-spin" : ""} />
                      <span>{meta.text}</span>
                    </div>
                  );
                })()}

                {active?.extraction && (
                  <>
                    <div className="flex flex-wrap items-center gap-2">
                      {currentFields.document_type && (
                        <Badge variant="outline">{titleCase(String(currentFields.document_type))}</Badge>
                      )}
                      {currentFields.overall_confidence && (
                        <Badge variant={confidenceVariant(currentFields.overall_confidence)}>
                          Reading confidence: {currentFields.overall_confidence}
                        </Badge>
                      )}
                      {active.extraction.has_handwritten_content && (
                        <Badge variant="destructive" title="Handwriting is harder to read. Check every value against the original.">Handwritten: check carefully</Badge>
                      )}
                      {active.extraction.needs_review && (
                        <Badge variant="destructive" title="Every document must be checked by you before it is used.">You must check this</Badge>
                      )}
                      {cachedNote && <Badge variant="outline" title="This exact file was read before, so that result was reused.">Reused earlier reading</Badge>}
                    </div>
                    {cachedNote && (
                      <p className="text-xs text-muted-foreground">
                        {cachedNote.replace(CACHED_RESULT_PREFIX, "").trim()}
                      </p>
                    )}

                    <div className="flex flex-col gap-2">
                      {Object.entries(currentFields)
                        .filter(([key]) => !key.endsWith(CONFIDENCE_SUFFIX) && !SPECIAL_KEYS.has(key) && key !== "document_type")
                        .map(([key, value]) => {
                          const confidence = currentFields[`${key}${CONFIDENCE_SUFFIX}`];
                          const displayValue = value === null || value === undefined ? "" : String(value);
                          return (
                            <div key={key} className="rounded-lg border border-border p-3">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-semibold">{titleCase(key)}</span>
                                {confidence && (
                                  <Badge variant={confidenceVariant(String(confidence))} className="text-[10px]">
                                    {String(confidence)}
                                  </Badge>
                                )}
                              </div>
                              {isEditingFields ? (
                                <>
                                <KeyboardInput
                                  value={displayValue}
                                  onChange={(e) => handleFieldChange(key, e.target.value)}
                                  className="mt-1.5 h-8 w-full rounded-md border border-input bg-transparent px-2 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
                                />
                                {String(value ?? "") !== String(active?.extraction?.validated_json_output?.[key] ?? "") && (
                                  <select
                                    aria-label={`Why was ${titleCase(key)} changed?`}
                                    value={fieldReasons[key] ?? ""}
                                    onChange={(e) => setFieldReasons({ ...fieldReasons, [key]: e.target.value })}
                                    className="mt-1.5 h-7 w-full rounded-md border border-input bg-transparent px-1.5 text-xs text-muted-foreground"
                                  >
                                    <option value="">Why changed? (optional)</option>
                                    <option value="misread">Misread the document</option>
                                    <option value="wrong_field">Right value, wrong field</option>
                                    <option value="hallucinated">Not in the document</option>
                                    <option value="format">Formatting</option>
                                    <option value="other">Other</option>
                                  </select>
                                )}
                                </>
                              ) : (
                                <p className="mt-1.5 text-sm">{displayValue || "—"}</p>
                              )}
                            </div>
                          );
                        })}
                      {isEditingFields && (
                        <Button size="sm" disabled={submitReview.isPending} onClick={handleSaveFieldEdits}>
                          {submitReview.isPending ? "Saving…" : "Save changes"}
                        </Button>
                      )}
                    </div>

                    {Array.isArray(currentFields.chain) && currentFields.chain.length > 0 && (
                      <div className="rounded-lg border border-border p-3">
                        <p className="mb-2 text-xs font-semibold">Ownership Chain</p>
                        <div className="flex flex-col gap-2">
                          {currentFields.chain.map((link: any, i: number) => (
                            <div key={i} className="text-xs text-muted-foreground">
                              {link.order ?? i + 1}. {link.owner || "Unknown"} — {link.type || "?"} ({link.date || "date unknown"}, survey {link.survey || "?"})
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {currentFields.full_text && (
                      <details className="rounded-lg border border-border p-3">
                        <summary className="cursor-pointer text-xs font-semibold">Full verbatim transcription</summary>
                        <FormattedText text={String(currentFields.full_text)} className="mt-2 text-xs text-muted-foreground" />
                      </details>
                    )}

                    <div className="flex flex-col gap-2 border-t border-border pt-3">
                      {active.extraction.reviewed_at ? (
                        <>
                          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                            <CheckCircle2 size={13} />
                            Reviewed {new Date(active.extraction.reviewed_at).toLocaleString()}
                            {active.extraction.status ? ` — ${active.extraction.status}` : ""}
                          </p>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={reopenDocument.isPending}
                            onClick={handleUndoApproval}
                          >
                            <Undo2 size={13} data-icon="inline-start" />
                            {reopenDocument.isPending ? "Undoing…" : "Undo and edit again"}
                          </Button>
                        </>
                      ) : (
                        <>
                          <KeyboardTextarea
                            placeholder="Review notes (optional)"
                            value={reviewNotes}
                            onChange={(e) => setReviewNotes(e.target.value)}
                            className="min-h-[60px] w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
                          />
                          <div className="flex gap-2">
                            <Button
                              size="sm"
                              className="flex-1"
                              disabled={submitReview.isPending}
                              onClick={() => handleDecision("approved")}
                            >
                              Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="flex-1"
                              disabled={submitReview.isPending}
                              onClick={() => handleDecision("rejected")}
                            >
                              Flag for correction
                            </Button>
                          </div>
                        </>
                      )}
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {!isLoading && !isError && active && (
          <Card className="mt-4">
            <CardHeader className="border-b">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Page Text</p>
                  <CardTitle className="mt-1">Original &amp; Translation</CardTitle>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={translateDoc.isPending || pagesLoading || pages.length === 0}
                  onClick={handleTranslate}
                >
                  <Languages size={14} data-icon="inline-start" />
                  {translateDoc.isPending ? "Translating…" : "Translate to English"}
                </Button>
              </div>
            </CardHeader>
            <CardContent className="flex flex-col gap-3 pt-4">
              {pagesLoading && <p className="text-sm text-muted-foreground">Loading page text…</p>}
              {!pagesLoading && pages.length === 0 && (
                <p className="text-sm text-muted-foreground">No page text available yet — this document may still be processing.</p>
              )}
              {pages.map((page) => {
                const isEditingThisPage = editingPageNumber === page.page_number;
                return (
                  <div key={page.page_number} className="rounded-lg border border-border p-3">
                    <div className="mb-2 flex items-center justify-between">
                      <p className="text-xs font-semibold text-muted-foreground">Page {page.page_number}</p>
                      {isEditingThisPage ? (
                        <div className="flex gap-1.5">
                          <Button size="sm" variant="outline" onClick={cancelEditingPage} disabled={updatePage.isPending}>
                            Cancel
                          </Button>
                          <Button size="sm" onClick={saveEditingPage} disabled={updatePage.isPending}>
                            {updatePage.isPending ? "Saving…" : "Save"}
                          </Button>
                        </div>
                      ) : (
                        <div className="flex gap-1.5">
                          {isAdmin && (
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={enhancedImage.isPending}
                              onClick={() => handleViewEnhancedImage(page.page_number)}
                              title="View the enhanced image OCR/Gemini actually read for this page"
                            >
                              <Eye size={13} data-icon="inline-start" />
                              {enhancedImage.isPending ? "Loading…" : "View enhanced image"}
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() =>
                              startEditingPage(page.page_number, page.original_text || "", page.english_text || "")
                            }
                          >
                            <Pencil size={13} data-icon="inline-start" />
                            Edit
                          </Button>
                        </div>
                      )}
                    </div>
                    <div className="grid gap-3 md:grid-cols-2">
                      <div>
                        <p className="mb-1 text-xs font-semibold text-muted-foreground">Original</p>
                        {isEditingThisPage ? (
                          <KeyboardTextarea
                            value={editedOriginalText}
                            onChange={(e) => setEditedOriginalText(e.target.value)}
                            className="min-h-[120px] w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
                          />
                        ) : (
                          page.original_text ? (
                            <FormattedText text={page.original_text} className="text-sm" />
                          ) : (
                            <p className="text-sm text-muted-foreground">—</p>
                          )
                        )}
                      </div>
                      <div className="border-t border-border pt-3 md:border-t-0 md:border-l md:pt-0 md:pl-3">
                        <p className="mb-1 text-xs font-semibold text-muted-foreground">English</p>
                        {isEditingThisPage ? (
                          <textarea
                            value={editedEnglishText}
                            onChange={(e) => setEditedEnglishText(e.target.value)}
                            placeholder="Not translated yet."
                            className="min-h-[120px] w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
                          />
                        ) : page.english_text ? (
                          <FormattedText text={page.english_text} className="text-sm" />
                        ) : (
                          <p className="text-sm text-muted-foreground">Not translated yet.</p>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
