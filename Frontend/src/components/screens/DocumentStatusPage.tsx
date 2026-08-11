import { CheckCircle2, Clock3, FileSearch, Loader2, ShieldAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

const steps = [
  { label: "Uploaded", state: "done", detail: "3/3 files", progress: 100 },
  { label: "OCR Processing", state: "live", detail: "Live", progress: 75 },
  { label: "AI Extraction", state: "done", detail: "18/20 fields", progress: 100 },
  { label: "Risk Audit", state: "flagged", detail: "2 alerts", progress: 50 },
  { label: "Ready for Review", state: "pending", detail: "Not started", progress: 10 },
];

function stepIcon(state: string) {
  if (state === "done") return <CheckCircle2 size={16} />;
  if (state === "live") return <Loader2 className="animate-spin" size={16} />;
  if (state === "flagged") return <ShieldAlert size={16} />;
  return <Clock3 size={16} />;
}

export function DocumentStatusPage() {
  return (
    <div className="min-h-screen bg-background px-4 py-10">
      <div className="mx-auto max-w-6xl">
        <Card>
          <CardHeader className="border-b">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Document Status</p>
                <CardTitle className="mt-1 text-2xl">PV-2408 // Meridian Avenue</CardTitle>
              </div>
              <Badge variant="outline">Needs review</Badge>
            </div>
          </CardHeader>

          <CardContent className="pt-6">
            {/* Pipeline steps */}
            <div className="grid gap-3 md:grid-cols-5">
              {steps.map((step) => (
                <div key={step.label} className="rounded-lg border border-border bg-card p-4">
                  <div className="flex items-center justify-between">
                    <span className="flex size-8 items-center justify-center rounded-md bg-secondary text-secondary-foreground">
                      {stepIcon(step.state)}
                    </span>
                  </div>
                  <div className="mt-3 text-sm font-semibold">{step.label}</div>
                  <div className="mt-0.5 text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                    {step.detail}
                  </div>
                  <Progress value={step.progress} className="mt-3 h-1.5" />
                </div>
              ))}
            </div>

            {/* Processing stream */}
            <Card size="sm" className="mt-6">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Processing stream</p>
                    <div className="mt-1 text-xl font-bold tracking-tight">OCR + Extraction</div>
                  </div>
                  <Badge variant="secondary">Running</Badge>
                </div>
              </CardHeader>
            </Card>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
