"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowRight, FileCode, MapPin, Search as SearchIcon, UploadCloud } from "lucide-react";
import { apiClient, type CaseRecord } from "@/services/api/client";
import { useToast } from "@/context/ToastContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { BatchUploadPanel } from "@/components/upload/BatchUploadPanel";
import { DocumentList } from "@/components/case/DocumentList";
import { CaseSearchPanel } from "@/components/search/CaseSearchPanel";

export function CaseWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const caseId = (params?.id as string) || "PV-2408";
  const toast = useToast();

  const [caseDetails, setCaseDetails] = useState<CaseRecord | null>(null);
  const [isLoadingCase, setIsLoadingCase] = useState<boolean>(true);
  const [documentListKey, setDocumentListKey] = useState(0);

  // Load Case Details
  useEffect(() => {
    async function loadCase() {
      setIsLoadingCase(true);
      try {
        const result = await apiClient.cases.getById(caseId);
        setCaseDetails(result.data);
      } catch (err: any) {
        toast.error(err.message || "Failed to load case details", "Error");
      } finally {
        setIsLoadingCase(false);
      }
    }
    loadCase();
  }, [caseId]);

  return (
    <div className="min-h-screen bg-background px-4 py-8 md:px-6">
      <div className="mx-auto max-w-6xl">
        {/* Page header */}
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4 border-b pb-4">
          <div>
            <div className="flex items-center gap-2">
              <Badge variant="secondary">{caseDetails?.status || "Draft"}</Badge>
            </div>
            <h1 className="mt-1 text-3xl font-bold tracking-tight">
              {caseDetails?.title || caseDetails?.property_name || "Case Workspace"}
            </h1>
            <p className="mt-1 text-xs text-muted-foreground flex items-center gap-3">
              <span className="flex items-center gap-1"><MapPin size={13} /> {caseDetails?.address || caseDetails?.location || "Miami, FL"}</span>
              <span className="flex items-center gap-1"><FileCode size={13} /> Survey No: {caseDetails?.survey_number || "SV-9912"}</span>
            </p>
          </div>

          <div className="flex items-center gap-2">
            {/* Report Builder moved to the review workspace (ReviewPage.tsx)
             * — it belongs alongside document approval, not the upload step,
             * since building a report only makes sense once there's
             * something reviewed to cite. */}
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

        {/* Document Ingestion */}
        <Card>
          <CardHeader className="border-b">
            <CardTitle className="text-lg flex items-center gap-2">
              <UploadCloud size={20} className="text-primary" />
              Case Document Ingestion
            </CardTitle>
            <CardDescription>
              Upload up to 20 legal deeds, title insurance policies, tax filings, or survey maps at once (PDF/PNG/JPG, under 10MB each).
            </CardDescription>
          </CardHeader>

          <CardContent className="pt-6">
            <BatchUploadPanel caseId={caseId} onUploaded={() => setDocumentListKey((k) => k + 1)} />
          </CardContent>
        </Card>

        {/* Documents */}
        <Card className="mt-6">
          <CardHeader className="border-b">
            <CardTitle className="text-lg">Documents</CardTitle>
            <CardDescription>Every document uploaded to this case and its processing status.</CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            <DocumentList caseId={caseId} refreshKey={documentListKey} />
          </CardContent>
        </Card>

        {/* Search */}
        <Card className="mt-6">
          <CardHeader className="border-b">
            <CardTitle className="text-lg flex items-center gap-2">
              <SearchIcon size={20} className="text-primary" />
              Search Case Documents
            </CardTitle>
            <CardDescription>
              Exact keyword search across every document&apos;s original-language and English text.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            <CaseSearchPanel caseId={caseId} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
