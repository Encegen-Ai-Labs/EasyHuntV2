"use client";

import React, { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { apiClient, type UsageSummary } from "@/services/api/client";
import { PageHeader } from "@/components/case/PageHeader";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const KIND_LABELS: Record<string, string> = {
  page_transcription: "Reading pages",
  page_transcription_and_fields: "Reading single pages",
  field_extraction_text: "Extracting fields",
  field_extraction_image: "Extracting fields (image)",
  embedding: "Search index",
  translation: "Translation (Gemini)",
  translate_google: "Translation (Google)",
  report_autofill: "Filling bank reports",
  report_draft: "Report drafts",
};

const money = (value: number) => `$${value.toFixed(value >= 10 ? 2 : 3)}`;
const count = (value: number) => value.toLocaleString();

function Tile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 font-heading text-2xl font-medium tabular-nums">{value}</p>
      {note && <p className="mt-0.5 text-xs text-muted-foreground">{note}</p>}
    </div>
  );
}

export function UsagePage() {
  const [days, setDays] = useState(7);
  const [data, setData] = useState<UsageSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void apiClient.admin.getUsage(days).then((result) => {
      if (cancelled) return;
      if (result.success && result.data) setData(result.data);
      else setError(result.error || "Could not load usage.");
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [days]);

  const peak = Math.max(0.0001, ...(data?.by_day.map((d) => d.cost_usd) ?? [0]));
  const failures = data ? data.errors + data.rate_limited : 0;

  return (
    <div className="min-h-screen bg-background px-4 py-8 md:px-6">
      <div className="mx-auto max-w-5xl">
        <PageHeader
          title="Usage and cost"
          subtitle="Estimated from the prices in settings. Compare with the Google Cloud billing page."
          actions={
            <div className="flex gap-1">
              {[7, 30].map((option) => (
                <Button key={option} size="sm" variant={days === option ? "secondary" : "ghost"} onClick={() => setDays(option)}>
                  {option} days
                </Button>
              ))}
            </div>
          }
        />

        {loading && (
          <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground">
            <Loader2 size={15} className="animate-spin" /> Loading…
          </p>
        )}
        {error && <p className="rounded-lg bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p>}

        {data && !loading && (
          <div className="flex flex-col gap-8">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Tile
                label="Today"
                value={money(data.today_cost_usd)}
                note={data.daily_budget_usd > 0 ? `limit ${money(data.daily_budget_usd)} a day` : "no daily limit set"}
              />
              <Tile label={`Last ${data.days} days`} value={money(data.total_cost_usd)} />
              <Tile label="Model calls" value={count(data.total_calls)} note={`${count(data.tokens_in + data.tokens_out)} tokens`} />
              <Tile
                label="Failed calls"
                value={count(failures)}
                note={data.rate_limited > 0 ? `${count(data.rate_limited)} rate-limited by Google` : undefined}
              />
            </div>

            <section>
              <h2 className="mb-3 font-heading text-xl font-medium">By day</h2>
              <div className="flex h-32 items-end gap-1.5 border-b border-border">
                {data.by_day.map((day) => (
                  <div key={day.date} className="flex h-full flex-1 flex-col justify-end" title={`${day.date}: ${money(day.cost_usd)}, ${day.calls} calls`}>
                    <div className={cn("w-full rounded-t-sm", day.cost_usd > 0 ? "bg-primary" : "bg-border")} style={{ height: `${Math.max(2, (day.cost_usd / peak) * 100)}%` }} />
                  </div>
                ))}
              </div>
              <div className="mt-1 flex gap-1.5 text-[10px] text-muted-foreground">
                {data.by_day.map((day) => (
                  <span key={day.date} className="flex-1 text-center tabular-nums">{day.date.slice(8)}</span>
                ))}
              </div>
            </section>

            <section>
              <h2 className="mb-3 font-heading text-xl font-medium">What it was spent on</h2>
              {data.by_kind.length === 0 ? (
                <p className="text-sm text-muted-foreground">No model calls in this period.</p>
              ) : (
                <div className="overflow-x-auto rounded-lg border border-border">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50 text-left text-xs text-muted-foreground">
                      <tr>
                        <th className="px-3 py-2 font-medium">Task</th>
                        <th className="px-3 py-2 text-right font-medium">Calls</th>
                        <th className="px-3 py-2 text-right font-medium">Tokens in / out</th>
                        <th className="px-3 py-2 text-right font-medium">Failed</th>
                        <th className="px-3 py-2 text-right font-medium">Cost</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.by_kind.map((row) => (
                        <tr key={row.kind} className="border-t border-border">
                          <td className="px-3 py-2">{KIND_LABELS[row.kind] ?? row.kind}</td>
                          <td className="px-3 py-2 text-right tabular-nums">{count(row.calls)}</td>
                          <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{count(row.tokens_in)} / {count(row.tokens_out)}</td>
                          <td className="px-3 py-2 text-right tabular-nums">{row.errors || "–"}</td>
                          <td className="px-3 py-2 text-right tabular-nums">{money(row.cost_usd)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <div className="grid gap-8 md:grid-cols-2">
              <section>
                <h2 className="mb-3 font-heading text-xl font-medium">Most expensive cases</h2>
                {data.top_cases.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Nothing yet.</p>
                ) : (
                  <ul className="divide-y divide-border rounded-lg border border-border text-sm">
                    {data.top_cases.map((item) => (
                      <li key={item.case_id} className="flex items-center justify-between gap-3 px-3 py-2">
                        <span className="truncate">{item.name || item.case_id}</span>
                        <span className="tabular-nums">{money(item.cost_usd)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section>
                <h2 className="mb-3 font-heading text-xl font-medium">Recent failures</h2>
                {data.recent_failures.length === 0 ? (
                  <p className="text-sm text-muted-foreground">None in this period.</p>
                ) : (
                  <ul className="divide-y divide-border rounded-lg border border-border text-sm">
                    {data.recent_failures.map((item, index) => (
                      <li key={index} className="px-3 py-2">
                        <p className="flex justify-between gap-3">
                          <span>{KIND_LABELS[item.kind] ?? item.kind}</span>
                          <span className="text-xs text-muted-foreground">
                            {item.status === "rate_limited" ? "rate-limited" : "error"} · {new Date(item.created_at).toLocaleString()}
                          </span>
                        </p>
                        {item.error && <p className="mt-0.5 truncate text-xs text-muted-foreground">{item.error}</p>}
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
