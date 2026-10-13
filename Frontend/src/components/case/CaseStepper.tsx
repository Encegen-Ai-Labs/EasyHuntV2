"use client";

import Link from "next/link";
import { useCaseProgress } from "@/services/api/hooks";
import { cn } from "@/lib/utils";

export type CaseStep = "upload" | "review" | "search" | "report";

const STEPS: { id: CaseStep; label: string; hint: string; path: (caseId: string) => string }[] = [
  { id: "upload", label: "Upload", hint: "Add the papers", path: (id) => `/cases/${id}` },
  { id: "review", label: "Review", hint: "Check and approve", path: (id) => `/cases/${id}/review` },
  { id: "search", label: "Search", hint: "Find and select text", path: (id) => `/cases/${id}/search` },
  { id: "report", label: "Report", hint: "Make and download", path: (id) => `/cases/${id}/report` },
];

/** Where the lawyer is in a case. Search and Report stay locked until at least
 * one document is approved. */
export function CaseStepper({ caseId, current }: { caseId: string; current: CaseStep }) {
  const { total, approved, isLoading } = useCaseProgress(caseId);

  function lockReason(step: CaseStep): string | null {
    if (isLoading) return null;
    if (step === "review" && total === 0) return "Upload a document first";
    if ((step === "search" || step === "report") && approved === 0) return "Approve a document first";
    return null;
  }

  return (
    <nav aria-label="Case progress" className="mb-8 border-b border-border">
      <ol className="flex gap-7 overflow-x-auto">
        {STEPS.map((step, index) => {
          const locked = lockReason(step.id);
          const isCurrent = step.id === current;
          const className = cn(
            "-mb-px flex items-start gap-2 whitespace-nowrap border-b-2 pb-2.5 text-sm transition-colors",
            isCurrent ? "border-primary font-semibold text-foreground" : "border-transparent",
            !isCurrent && !locked && "text-muted-foreground hover:text-foreground",
            locked && "cursor-not-allowed text-muted-foreground/60"
          );
          const body = (
            <>
              <span className={cn("text-xs tabular-nums", isCurrent ? "text-primary" : "text-muted-foreground/70")}>{index + 1}</span>
              <span className="flex flex-col leading-tight">
                <span>{step.label}</span>
                <span className="text-[11px] font-normal text-muted-foreground/80">{locked ?? step.hint}</span>
              </span>
              {step.id === "review" && total > 0 && !locked && (
                <span className="text-xs font-normal text-muted-foreground">{approved}/{total}</span>
              )}
            </>
          );
          return (
            <li key={step.id}>
              {locked ? (
                <span className={className} aria-disabled="true" title={locked}>{body}</span>
              ) : (
                <Link href={step.path(caseId)} className={className} aria-current={isCurrent ? "step" : undefined}>
                  {body}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
