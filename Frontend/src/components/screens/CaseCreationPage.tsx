"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Building2, ChevronRight, MapPin, FileCode, Loader2, ArrowRight } from "lucide-react";
import { apiClient } from "@/services/api/client";
import { useToast } from "@/context/ToastContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardFooter, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/Input";

export function CaseCreationPage() {
  const router = useRouter();
  const toast = useToast();

  const [propertyName, setPropertyName] = useState<string>("");
  const [surveyNumber, setSurveyNumber] = useState<string>("");
  const [location, setLocation] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!propertyName || !surveyNumber || !location) {
      toast.error("Please fill in all case details", "Validation Error");
      return;
    }

    setIsSubmitting(true);
    try {
      // Step 2: Post to API and extract generated case_id from API response
      const res = await apiClient.cases.create({
        property_name: propertyName,
        survey_number: surveyNumber,
        location: location,
      });

      const generatedCaseId = res.id || res.case_id || (res as any).data?.id || "PV-2412";
      toast.success(`Case created! Generated Case ID: ${generatedCaseId}`, "Step 2 Complete");

      // Immediately transition view to case workspace (/cases/{case_id}) to reveal Document Upload UI (Step 3)
      router.push(`/cases/${generatedCaseId}`);
    } catch (err: any) {
      toast.error(err.message || "Failed to create case", "Error");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-background px-4 py-10">
      <div className="mx-auto max-w-3xl">
        {/* Page header */}
        <div className="mb-7 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">EasyHuntV2 Case Flow</p>
            <h1 className="mt-1 text-3xl font-bold tracking-tight">Step 1: Case Info Input</h1>
          </div>
          <Badge variant="secondary">Sequential Case Wizard</Badge>
        </div>

        <Card>
          <CardHeader className="border-b">
            <CardTitle>Enter Case Specifications</CardTitle>
            <CardDescription>
              Input case details to trigger server-side Case ID generation (`POST /api/v1/cases`) and reveal Document Upload UI.
            </CardDescription>
          </CardHeader>

          <form onSubmit={handleSubmit}>
            <CardContent className="pt-6 flex flex-col gap-5">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
                  <Building2 size={14} className="text-primary" />
                  Property Name / Case Title
                </label>
                <Input
                  placeholder="e.g. 1800 Meridian Avenue"
                  value={propertyName}
                  onChange={(e) => setPropertyName(e.target.value)}
                  required
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
                  <FileCode size={14} className="text-primary" />
                  Survey Number
                </label>
                <Input
                  placeholder="e.g. SV-9912-A"
                  value={surveyNumber}
                  onChange={(e) => setSurveyNumber(e.target.value)}
                  required
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
                  <MapPin size={14} className="text-primary" />
                  Location / Address
                </label>
                <Input
                  placeholder="e.g. Miami, FL"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  required
                />
              </div>
            </CardContent>

            <CardFooter className="border-t flex justify-between pt-4">
              <Button type="button" variant="outline" size="sm" onClick={() => router.back()}>
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={isSubmitting} className="gap-2 font-semibold">
                {isSubmitting ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    Generating Case ID…
                  </>
                ) : (
                  <>
                    Generate Case & Transition
                    <ArrowRight size={14} />
                  </>
                )}
              </Button>
            </CardFooter>
          </form>
        </Card>
      </div>
    </div>
  );
}
