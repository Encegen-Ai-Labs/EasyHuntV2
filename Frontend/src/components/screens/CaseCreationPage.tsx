"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Building2, Loader2, MapPin } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardFooter, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useCreateCaseMutation } from "@/services/api/hooks";
import { useToast } from "@/context/ToastContext";

export function CaseCreationPage() {
  const router = useRouter();
  const toast = useToast();
  const createCase = useCreateCaseMutation();

  const [propertyName, setPropertyName] = useState("");
  const [surveyNumber, setSurveyNumber] = useState("");
  const [location, setLocation] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!propertyName.trim() || !surveyNumber.trim()) {
      toast.error("Property name and survey number are required", "Missing Fields");
      return;
    }

    const result = await createCase.mutateAsync({
      property_name: propertyName.trim(),
      survey_number: surveyNumber.trim(),
      location: location.trim() || undefined,
    });

    if (result.success && result.data) {
      toast.success("Case created. You can upload documents now.", "Case Created");
      router.push(`/cases/${result.data.id}`);
    } else {
      toast.error(result.error || "Failed to create case", "Error");
    }
  }

  return (
    <div className="min-h-screen bg-background px-4 py-10">
      <div className="mx-auto max-w-2xl">
        <div className="mb-7">
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">PropVerify AI</p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight">Create Case</h1>
        </div>

        <form onSubmit={handleSubmit}>
          <Card>
            <CardHeader className="border-b">
              <CardTitle>Case details</CardTitle>
              <CardDescription>
                Capture the property context. You&apos;ll upload documents on the next screen.
              </CardDescription>
            </CardHeader>

            <CardContent className="pt-6 flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="property-name" className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  Property name
                </label>
                <Input
                  id="property-name"
                  placeholder="1800 Meridian Avenue"
                  value={propertyName}
                  onChange={(e) => setPropertyName(e.target.value)}
                  required
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="survey-number" className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  Survey number
                </label>
                <Input
                  id="survey-number"
                  placeholder="SY-1234"
                  value={surveyNumber}
                  onChange={(e) => setSurveyNumber(e.target.value)}
                  required
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="location" className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                  Location (optional)
                </label>
                <Input
                  id="location"
                  placeholder="Miami, FL"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                />
              </div>

              <div className="mt-2 flex flex-col gap-2 rounded-xl border border-border bg-muted/20 p-3 text-xs text-muted-foreground">
                <div className="flex items-center gap-2">
                  <Building2 size={14} />
                  <span>{propertyName || "Property name will appear here"}</span>
                </div>
                <div className="flex items-center gap-2">
                  <MapPin size={14} />
                  <span>{location || "No location set"}</span>
                </div>
              </div>
            </CardContent>

            <CardFooter className="flex items-center justify-between border-t">
              <Badge variant="secondary">Case Wizard</Badge>
              <Button type="submit" size="sm" disabled={createCase.isPending} className="gap-2">
                {createCase.isPending ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    Creating…
                  </>
                ) : (
                  "Create Case"
                )}
              </Button>
            </CardFooter>
          </Card>
        </form>
      </div>
    </div>
  );
}
