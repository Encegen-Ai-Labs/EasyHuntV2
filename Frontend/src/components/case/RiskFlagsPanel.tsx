"use client";

import React, { useState } from "react";
import { AlertTriangle, BrainCircuit, Ruler } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useFlagsQuery, useResolveFlagMutation } from "@/services/api/hooks";
import { useToast } from "@/context/ToastContext";
import type { FlagRecord, FlagSeverity } from "@/services/api/client";

type BadgeVariant = "outline" | "secondary" | "destructive" | "default";

const SEVERITY_VARIANT: Record<FlagSeverity, BadgeVariant> = {
  critical: "destructive",
  high: "destructive",
  medium: "outline",
  low: "secondary",
};

interface RiskFlagsPanelProps {
  caseId: string;
}

export function RiskFlagsPanel({ caseId }: RiskFlagsPanelProps) {
  const { data, isLoading } = useFlagsQuery(caseId);
  const resolveMutation = useResolveFlagMutation();
  const toast = useToast();
  const [notesByFlag, setNotesByFlag] = useState<Record<string, string>>({});

  const flags: FlagRecord[] = data?.success && data.data ? data.data : [];
  const activeFlags = flags.filter((f) => f.status === "raised");
  const resolvedFlags = flags.filter((f) => f.status !== "raised");

  const handleResolve = async (flagId: string, status: "resolved" | "ignored") => {
    const notes = notesByFlag[flagId] || (status === "ignored" ? "Dismissed by reviewer." : "Resolved by reviewer.");
    const result = await resolveMutation.mutateAsync({ flagId, notes, status });
    if (result.success) {
      toast.success(status === "ignored" ? "Flag dismissed." : "Flag marked resolved.", "Updated");
      setNotesByFlag((prev) => ({ ...prev, [flagId]: "" }));
    } else {
      toast.error(result.error || "Failed to update flag", "Error");
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-xs text-muted-foreground">
          Loading risk flags…
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={activeFlags.length > 0 ? "border-destructive/30" : undefined}>
      <CardHeader className={activeFlags.length > 0 ? "border-b border-destructive/20 bg-destructive/5" : "border-b border-border"}>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Risk Flags</p>
            <CardTitle className="mt-1 text-xl">Title Scrutiny Flags</CardTitle>
          </div>
          <Badge variant={activeFlags.length > 0 ? "destructive" : "secondary"}>
            {String(activeFlags.length).padStart(2, "0")}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="pt-6">
        {flags.length === 0 ? (
          <p className="py-8 text-center text-xs text-muted-foreground">
            No risk flags raised for this case yet.
          </p>
        ) : (
          <div className="flex flex-col gap-4">
            {activeFlags.map((flag) => (
              <div key={flag.id} className="flex flex-col gap-3 rounded-xl border border-border bg-muted/20 p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex gap-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-destructive/10 text-destructive">
                      <AlertTriangle size={18} />
                    </span>
                    <div>
                      <div className="font-semibold">{flag.flag_type}</div>
                      <div className="mt-0.5 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                        {flag.source === "llm" ? <BrainCircuit size={11} /> : <Ruler size={11} />}
                        {flag.source === "llm" ? "Read from document text" : "Structural chain check"}
                      </div>
                    </div>
                  </div>
                  <Badge variant={SEVERITY_VARIANT[flag.severity] || "outline"}>{flag.severity}</Badge>
                </div>
                <p className="text-sm leading-relaxed text-muted-foreground">{flag.description}</p>
                <div className="flex flex-wrap items-center gap-2">
                  <Input
                    placeholder="Resolution note (optional)"
                    value={notesByFlag[flag.id] || ""}
                    onChange={(e) => setNotesByFlag((prev) => ({ ...prev, [flag.id]: e.target.value }))}
                    className="max-w-xs"
                  />
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={resolveMutation.isPending}
                    onClick={() => handleResolve(flag.id, "resolved")}
                  >
                    Resolve
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={resolveMutation.isPending}
                    onClick={() => handleResolve(flag.id, "ignored")}
                  >
                    Dismiss
                  </Button>
                </div>
              </div>
            ))}

            {resolvedFlags.length > 0 && (
              <div className="flex flex-col gap-2 border-t border-border pt-4">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                  Resolved / dismissed
                </p>
                {resolvedFlags.map((flag) => (
                  <div
                    key={flag.id}
                    className="flex items-center justify-between gap-2 rounded-lg border border-border/60 bg-background px-3 py-2 text-xs text-muted-foreground"
                  >
                    <span className="truncate">{flag.flag_type} — {flag.description}</span>
                    <Badge variant="secondary" className="shrink-0 text-[10px] uppercase">
                      {flag.status}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
