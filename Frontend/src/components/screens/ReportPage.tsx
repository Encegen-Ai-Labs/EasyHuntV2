import { Calendar, CheckCircle2, Clock, Download, FileText, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

export function ReportPage() {
  return (
    <div className="min-h-screen bg-background px-4 py-10">
      <div className="mx-auto max-w-6xl">
        {/* Header */}
        <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Executive Report</p>
            <h1 className="mt-1 text-3xl font-bold tracking-tight">PV-2408 / Meridian Avenue</h1>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm">
              <Download data-icon="inline-start" />
              Export PDF
            </Button>
            <Button size="sm">Generate Summary</Button>
          </div>
        </header>

        {/* Stats */}
        <section className="grid gap-4 md:grid-cols-4">
          {[
            { title: "Property Specs", value: "Residential", detail: "2,140 SF", icon: <FileText size={16} /> },
            { title: "Cleared Items", value: "07", detail: "No open issues", icon: <CheckCircle2 size={16} /> },
            { title: "Resolved Risks", value: "02", detail: "Low confidence fields", icon: <ShieldCheck size={16} /> },
            { title: "Audit Trail", value: "14", detail: "Events logged", icon: <Clock size={16} /> },
          ].map(({ title, value, detail, icon }) => (
            <Card key={title} size="sm">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <span className="flex size-8 items-center justify-center rounded-md bg-secondary text-secondary-foreground">
                    {icon}
                  </span>
                  <Badge variant="secondary" className="text-[10px]">Live</Badge>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">{title}</p>
                <div className="mt-1 text-2xl font-bold tracking-tight">{value}</div>
                <div className="text-xs text-muted-foreground">{detail}</div>
              </CardContent>
            </Card>
          ))}
        </section>

        {/* Detail cards */}
        <section className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <Card>
            <CardHeader className="border-b">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Executive Summary</p>
                  <CardTitle className="mt-1">Property Risk Assessment</CardTitle>
                </div>
                <Badge variant="secondary">Cleared</Badge>
              </div>
            </CardHeader>
            <CardContent className="flex flex-col gap-3 pt-4">
              <RiskLine label="Title Ownership" value="Clear" warning={false} />
              <RiskLine label="Financial Exposure" value="Low" warning={false} />
              <RiskLine label="Open Encumbrances" value="01 warning" warning />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="border-b">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Audit Trail</p>
                  <CardTitle className="mt-1">Reviewer Activity</CardTitle>
                </div>
                <Button variant="secondary" size="sm">Today</Button>
              </div>
            </CardHeader>
            <CardContent className="flex flex-col gap-4 pt-4">
              <AuditRow time="08:14 AM" action="OCR extraction completed" user="AI Pipeline" />
              <AuditRow time="09:02 AM" action="Title fields reviewed" user="Avery Johnson" />
              <AuditRow time="09:46 AM" action="Risk flag resolved" user="Mia Rivera" />
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
}

function RiskLine({ label, value, warning }: { label: string; value: string; warning: boolean }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-border px-4 py-3">
      <div>
        <div className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">{label}</div>
        <div className="mt-1 text-sm font-medium">{value}</div>
      </div>
      <Badge variant={warning ? "outline" : "secondary"}>{warning ? "Warning" : "Clear"}</Badge>
    </div>
  );
}

function AuditRow({ time, action, user }: { time: string; action: string; user: string }) {
  return (
    <div className="flex items-start gap-3">
      <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-secondary text-secondary-foreground">
        <Calendar size={13} />
      </span>
      <div>
        <div className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">{time}</div>
        <div className="mt-0.5 text-sm font-medium">{action}</div>
        <div className="text-xs text-muted-foreground">{user}</div>
      </div>
    </div>
  );
}
