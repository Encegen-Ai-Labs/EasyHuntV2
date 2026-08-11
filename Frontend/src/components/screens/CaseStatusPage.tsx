import { CheckCheck, FileSearch, Loader2, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const pipeline = [
  { label: "Uploaded", done: true },
  { label: "OCR Processing", done: true },
  { label: "AI Extraction", done: true },
  { label: "Risk Audit", done: false, live: true },
  { label: "Ready for Review", done: false },
];

export function CaseStatusPage() {
  return (
    <div className="min-h-screen bg-background px-4 py-10">
      <div className="mx-auto max-w-5xl">
        <Card>
          <CardHeader className="border-b">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Case Pipeline</p>
                <CardTitle className="mt-1 text-2xl">PV-2408 // Meridian Avenue</CardTitle>
              </div>
              <Badge variant="outline">Processing</Badge>
            </div>
          </CardHeader>

          <CardContent className="pt-6">
            {/* Pipeline steps */}
            <div className="grid gap-3 md:grid-cols-5">
              {pipeline.map((step, index) => (
                <div
                  key={step.label}
                  className={cn(
                    "rounded-lg border p-3",
                    step.done
                      ? "border-border bg-secondary/50"
                      : step.live
                      ? "border-border bg-muted"
                      : "border-dashed border-border bg-background"
                  )}
                >
                  <div className="flex items-center gap-2">
                    {step.done ? (
                      <CheckCheck size={16} className="text-foreground" />
                    ) : step.live ? (
                      <Loader2 className="animate-spin" size={16} />
                    ) : (
                      <span className="size-2 rounded-full bg-muted-foreground/30" />
                    )}
                    <span className="text-xs font-semibold">{step.label}</span>
                  </div>
                  {index < pipeline.length - 1 && (
                    <div className="mt-3 h-px bg-border" />
                  )}
                </div>
              ))}
            </div>

            {/* Stats */}
            <div className="mt-6 grid gap-4 md:grid-cols-3">
              <StatCard label="OCR Confidence" value="93%" note="Document read" icon={<FileSearch size={16} />} />
              <StatCard label="Extraction Status" value="14/18" note="Fields mapped" icon={<ShieldCheck size={16} />} />
              <StatCard label="Risk Assessment" value="2 Alerts" note="Needs attention" icon={<Loader2 size={16} />} />
            </div>

            {/* Progress section */}
            <Card size="sm" className="mt-6">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Live extraction progress</p>
                    <div className="mt-1 text-2xl font-bold tracking-tight">68%</div>
                  </div>
                  <Button variant="outline" size="sm">Polling active</Button>
                </div>
              </CardHeader>
              <CardContent>
                <Progress value={68} className="h-2" />
              </CardContent>
            </Card>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  note,
  icon,
}: {
  label: string;
  value: string;
  note: string;
  icon: React.ReactNode;
}) {
  return (
    <Card size="sm">
      <CardHeader>
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">{label}</span>
          <span className="flex size-8 items-center justify-center rounded-md bg-secondary text-secondary-foreground">
            {icon}
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold tracking-tight">{value}</div>
        <div className="mt-0.5 text-xs text-muted-foreground">{note}</div>
      </CardContent>
    </Card>
  );
}
