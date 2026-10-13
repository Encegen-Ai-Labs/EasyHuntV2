"use client";

import React from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowRight, UploadCloud } from "lucide-react";
import { useCaseById, useCaseProgress } from "@/services/api/hooks";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { BatchUploadPanel } from "@/components/upload/BatchUploadPanel";
import { DocumentList } from "@/components/case/DocumentList";
import { RiskFlagsPanel } from "@/components/case/RiskFlagsPanel";
import { CaseStepper } from "@/components/case/CaseStepper";
import { PageHeader } from "@/components/case/PageHeader";
import { StepGuide } from "@/components/case/StepGuide";

export function CaseWorkspacePage() {
  const params = useParams();
  const caseId = (params?.id as string) || "";
  const queryClient = useQueryClient();

  const { data: caseData } = useCaseById(caseId);
  const caseDetails = caseData?.data;
  const { total, processing, readyToReview, approved } = useCaseProgress(caseId);

  const readyCount = total - processing;

  return (
    <div className="min-h-screen bg-background px-4 py-8 md:px-6">
      <div className="mx-auto max-w-5xl">
        <PageHeader
          title={caseDetails?.title || caseDetails?.property_name || "Case Workspace"}
          subtitle={caseDetails?.address && caseDetails.address !== "Address N/A" ? caseDetails.address : caseDetails?.location || "No location added"}
        />

        <CaseStepper caseId={caseId} current="upload" />

        <StepGuide
          id="upload"
          title="Step 1 of 4: add the property documents"
          steps={[
            "Drag the files into the box below, or click it to choose them. PDFs and photos of pages both work.",
            "Press Upload. Each document is read automatically, which takes a few minutes. You can leave this page and come back.",
            "When a document says “Ready to review”, open it from the list and check what was read (the next step).",
          ]}
          note="You can add more documents at any time, up to 20 at once."
        />

        <Card>
          <CardHeader className="border-b">
            <CardTitle className="flex items-center gap-2 text-lg">
              <UploadCloud size={20} className="text-primary" />
              Upload documents
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-6">
            <BatchUploadPanel
              caseId={caseId}
              onUploaded={() => queryClient.invalidateQueries({ queryKey: ["documents", caseId, "list"] })}
            />
          </CardContent>
        </Card>

        <Card className="mt-6">
          <CardHeader className="border-b">
            <CardTitle className="text-lg">Documents</CardTitle>
          </CardHeader>
          <CardContent className="pt-6">
            <DocumentList caseId={caseId} />
          </CardContent>
        </Card>

        {total > 0 && (
          <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-5">
            <p className="text-sm text-muted-foreground">
              {readyCount} of {total} read{approved > 0 ? ` · ${approved} approved` : ""}
              {readyToReview > 0 && approved > 0 ? ` · ${readyToReview} to review` : ""}
            </p>
            <Button nativeButton={false} render={<Link href={`/cases/${caseId}/review`} />} disabled={readyCount === 0}>
              Review documents
              <ArrowRight size={15} data-icon="inline-end" />
            </Button>
          </div>
        )}

        <div className="mt-6">
          <RiskFlagsPanel caseId={caseId} />
        </div>
      </div>
    </div>
  );
}
