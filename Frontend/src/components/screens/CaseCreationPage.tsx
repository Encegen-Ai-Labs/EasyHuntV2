import { Building2, ChevronLeft, ChevronRight, FileUp, MapPin, UploadCloud } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardFooter, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";

export function CaseCreationPage() {
  return (
    <div className="min-h-screen bg-background px-4 py-10">
      <div className="mx-auto max-w-4xl">
        {/* Page header */}
        <div className="mb-7 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">PropVerify AI</p>
            <h1 className="mt-1 text-3xl font-bold tracking-tight">Create Case</h1>
          </div>
          <Badge variant="secondary">Case Wizard</Badge>
        </div>

        <Card>
          <CardHeader className="border-b">
            {/* Step indicator */}
            <div className="grid grid-cols-3 gap-3">
              <StepPill label="Case Details" active />
              <StepPill label="Documents" />
              <StepPill label="Confirmation" />
            </div>
          </CardHeader>

          <CardContent className="pt-6">
            <div className="grid gap-8 md:grid-cols-[1fr_300px]">
              {/* Left form */}
              <div>
                <div className="mb-5">
                  <h2 className="text-xl font-semibold tracking-tight">Case details</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Capture the primary property context and diligence workflow.
                  </p>
                </div>

                <div className="flex flex-col gap-4">
                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="case-title" className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                      Case title
                    </label>
                    <Input id="case-title" defaultValue="1800 Meridian Avenue" readOnly />
                  </div>
                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="case-address" className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                      Property address
                    </label>
                    <Input id="case-address" defaultValue="1800 Meridian Ave, Miami FL" readOnly />
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="flex flex-col gap-1.5">
                      <label htmlFor="case-type" className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                        Property type
                      </label>
                      <select id="case-type" className="h-9 rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition-colors focus:border-ring">
                        <option>Residential</option>
                        <option>Retail</option>
                        <option>Industrial</option>
                      </select>
                    </div>
                    <div className="flex flex-col gap-1.5">
                      <label htmlFor="case-priority" className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                        Priority tag
                      </label>
                      <select id="case-priority" className="h-9 rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition-colors focus:border-ring">
                        <option>High</option>
                        <option>Normal</option>
                        <option>Critical</option>
                      </select>
                    </div>
                  </div>
                </div>

                {/* Upload zone */}
                <div className="mt-6 rounded-xl border border-dashed border-border bg-muted/30 p-5">
                  <div className="flex items-center gap-3">
                    <span className="flex size-10 items-center justify-center rounded-lg bg-secondary text-secondary-foreground">
                      <UploadCloud size={20} />
                    </span>
                    <div>
                      <div className="text-sm font-medium">Upload documents</div>
                      <div className="text-xs text-muted-foreground">PDF, JPG, PNG, TIFF</div>
                    </div>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {["Deed.pdf", "property-tax.pdf", "photo-04.png"].map((file) => (
                      <Badge key={file} variant="secondary">{file}</Badge>
                    ))}
                  </div>
                </div>
              </div>

              {/* Sidebar summary */}
              <Card size="sm">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle>Case Snapshot</CardTitle>
                    <Badge variant="secondary">Ready</Badge>
                  </div>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  <SummaryRow icon={<Building2 size={14} />} label="Property type" value="Residential" />
                  <SummaryRow icon={<MapPin size={14} />} label="Location" value="Miami, FL" />
                  <SummaryRow icon={<FileUp size={14} />} label="Documents" value="03 files" />
                </CardContent>
                <CardFooter>
                  <Button className="w-full" size="sm">Process Case</Button>
                </CardFooter>
              </Card>
            </div>
          </CardContent>

          <CardFooter className="flex items-center justify-between">
            <Button variant="outline" size="sm">
              <ChevronLeft data-icon="inline-start" />
              Back
            </Button>
            <Button size="sm">
              Next
              <ChevronRight data-icon="inline-end" />
            </Button>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
}

function StepPill({ label, active = false }: { label: string; active?: boolean }) {
  return (
    <div
      className={cn(
        "rounded-full border px-4 py-2 text-center text-xs font-semibold uppercase tracking-widest",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-muted text-muted-foreground"
      )}
    >
      {label}
    </div>
  );
}

function SummaryRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-border bg-background px-3 py-2">
      <div className="flex items-center gap-2 text-muted-foreground">
        {icon}
        <span className="text-xs font-semibold uppercase tracking-widest">{label}</span>
      </div>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}
