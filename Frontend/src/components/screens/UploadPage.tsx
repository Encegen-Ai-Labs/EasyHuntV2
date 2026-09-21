"use client";

import React, { useState } from "react";
import { ShieldCheck } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { BatchUploadPanel } from "@/components/upload/BatchUploadPanel";

export function UploadPage() {
  const [caseId, setCaseId] = useState<string>("PV-2408");
  const [propertyName, setPropertyName] = useState<string>("1800 Meridian Avenue");

  return (
    <div className="min-h-screen bg-background px-4 py-10">
      <div className="mx-auto max-w-4xl">
        {/* Page header */}
        <div className="mb-7 flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Document Infrastructure</p>
            <h1 className="mt-1 text-3xl font-bold tracking-tight">Upload Property Documents</h1>
          </div>
          <Badge variant="secondary" className="gap-1">
            <ShieldCheck size={14} />
            Document Intake Mode
          </Badge>
        </div>

        <Card>
          <CardHeader className="border-b">
            <CardTitle>Case & File Specifications</CardTitle>
            <CardDescription>
              Upload up to 20 deeds, title reports, tax disclosures, or mortgage filings at once for automated extraction.
            </CardDescription>
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

            <BatchUploadPanel caseId={caseId} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
