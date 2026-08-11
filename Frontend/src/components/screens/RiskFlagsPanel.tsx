import { AlertTriangle, MessageSquare } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function RiskFlagsPanel() {
  const flags = [
    { title: "Open Judgment", severity: "Critical", source: "County docket // 2026-08-02", detail: "Monroe County civil judgment references property owner." },
    { title: "Tax Lien Hold", severity: "Warning", source: "Tax records // line 07", detail: "Outstanding district lien transfer pending confirmation." },
    { title: "Ownership Name Variant", severity: "Info", source: "Deed / title page", detail: "Entity identifier differs from owner submitted." },
  ];

  return (
    <Card className="border-destructive/30">
      <CardHeader className="border-b border-destructive/20 bg-destructive/5">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-destructive">Risk Flags</p>
            <CardTitle className="mt-1 text-xl">Flag Review</CardTitle>
          </div>
          <Badge variant="destructive">03</Badge>
        </div>
      </CardHeader>
      <CardContent className="pt-6">
        <div className="flex flex-col gap-4">
          {flags.map((flag) => (
            <div key={flag.title} className="flex flex-col gap-4 rounded-xl border border-border bg-muted/20 p-4">
              <div className="flex items-start justify-between">
                <div className="flex gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-destructive/10 text-destructive">
                    <AlertTriangle size={18} />
                  </span>
                  <div>
                    <div className="font-semibold">{flag.title}</div>
                    <div className="mt-0.5 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">{flag.source}</div>
                  </div>
                </div>
                <Badge variant={flag.severity === "Critical" ? "destructive" : flag.severity === "Warning" ? "outline" : "secondary"}>
                  {flag.severity}
                </Badge>
              </div>
              <p className="text-sm leading-relaxed text-muted-foreground">{flag.detail}</p>
              <div className="flex flex-wrap items-center gap-2">
                <Button variant="outline" size="sm">Resolve</Button>
                <Button variant="outline" size="sm">Dismiss</Button>
                <Button variant="outline" size="sm">
                  <MessageSquare data-icon="inline-start" />
                  Note
                </Button>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
