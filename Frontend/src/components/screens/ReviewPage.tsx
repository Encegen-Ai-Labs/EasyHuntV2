"use client";

import { Eye, FileSearch, Minimize2, Minus, Plus, ZoomIn } from "lucide-react";
import { useExtractedFields } from "@/services/api/hooks";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";

export function ReviewPage() {
  const { data, isLoading, isError } = useExtractedFields();
  const extraction = data?.data;
  const groups = extraction?.fields ?? [
    {
      title: "Ownership & Title",
      fields: [
        { key: "Owner", value: "Meridian Holdings LLC", confidence: 98, edited: false },
        { key: "Title Status", value: "Clear", confidence: 92, edited: false },
        { key: "Deed Type", value: "Warranty Deed", confidence: 88, edited: true },
      ],
    },
    {
      title: "Financials",
      fields: [
        { key: "Fair Market Value", value: "$845,000", confidence: 91, edited: false },
        { key: "Tax Assessment", value: "$736,180", confidence: 83, edited: false },
        { key: "Mortgage Balance", value: "$417,500", confidence: 74, edited: false },
      ],
    },
    {
      title: "Encumbrances",
      fields: [
        { key: "Tax Lien", value: "None", confidence: 95, edited: false },
        { key: "Open Judgment", value: "Monroe County", confidence: 68, edited: true },
      ],
    },
  ];

  return (
    <div className="min-h-screen bg-background px-4 py-6">
      <div className="mx-auto max-w-[1800px]">
        {/* Page header */}
        <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Extraction Review</p>
            <h1 className="mt-1 text-2xl font-bold tracking-tight">PV-2408 // 1800 Meridian Avenue</h1>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm">Export</Button>
            <Button size="sm">Save Review</Button>
          </div>
        </header>

        {/* Split layout */}
        <div className="grid gap-4 lg:grid-cols-[1fr_420px]">
          {/* Document pane */}
          <Card className="overflow-hidden">
            <CardHeader className="border-b py-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1">
                  <Button variant="ghost" size="sm"><Minus size={13} /></Button>
                  <Button variant="ghost" size="sm"><Plus size={13} /></Button>
                  <Button variant="ghost" size="sm"><Minimize2 size={13} /></Button>
                </div>
                <div className="flex items-center gap-1">
                  <Button variant="ghost" size="sm"><Eye size={13} /></Button>
                  <Button variant="ghost" size="sm"><FileSearch size={13} /></Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="min-h-[600px] bg-muted/20 p-6">
              {/* Simulated PDF canvas */}
              <div className="flex min-h-[560px] items-center justify-center">
                <div className="relative w-full max-w-lg overflow-hidden rounded-xl border border-border bg-background shadow-lg" style={{ minHeight: 520 }}>
                  {/* Lined paper effect via repeating gradient */}
                  <div
                    className="absolute inset-0 opacity-30"
                    style={{ backgroundImage: "repeating-linear-gradient(180deg, transparent 0px, transparent 24px, hsl(var(--border)) 25px)" }}
                  />
                  <div className="relative p-8">
                    <h3 className="text-2xl font-bold">Meridian Avenue / Property Profile</h3>
                    {/* Highlight boxes */}
                    <div className="mt-6 h-10 rounded-md border-2 border-ring/50 bg-ring/10" />
                    <div className="mt-32 h-16 rounded-md border-2 border-muted-foreground/30 bg-muted/30" />
                    <div className="mt-8 flex flex-col gap-3">
                      {["Owner", "Property Type", "Tax Assessment"].map((item) => (
                        <div key={item} className="border-b border-border pb-2 text-sm font-medium text-muted-foreground">
                          {item}
                        </div>
                      ))}
                    </div>
                  </div>
                  {/* Page banner */}
                  <div className="absolute bottom-4 right-4 flex items-center gap-2 rounded-full border border-border bg-background px-3 py-1.5 text-xs font-medium shadow-sm">
                    <span>Page 01 / 04</span>
                    <div className="flex gap-1">
                      <button className="size-6 rounded-full bg-secondary text-secondary-foreground text-xs">‹</button>
                      <button className="size-6 rounded-full bg-secondary text-secondary-foreground text-xs">›</button>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Fields pane */}
          <Card>
            <CardHeader className="border-b">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Extracted Fields</p>
                  <CardTitle className="mt-1">Diligence Data</CardTitle>
                </div>
                <Button variant="outline" size="sm">Auto Sync</Button>
              </div>
            </CardHeader>
            <CardContent className="pt-4">
              {isLoading && (
                <p className="text-sm text-muted-foreground">Loading extraction fields…</p>
              )}
              {isError && (
                <p className="text-sm font-medium text-destructive">Unable to load extraction fields.</p>
              )}
              {!isLoading && !isError && (
                <Accordion multiple>
                  {groups.map((group) => (
                    <AccordionItem key={group.title} value={group.title}>
                      <AccordionTrigger className="text-sm font-semibold">
                        <span>{group.title}</span>
                        <span className="ml-auto mr-2 text-xs text-muted-foreground">{group.fields.length} fields</span>
                      </AccordionTrigger>
                      <AccordionContent>
                        <div className="flex flex-col gap-3 pt-2">
                          {group.fields.map((field) => (
                            <div key={field.key} className="rounded-lg border border-border p-3">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-semibold">{field.key}</span>
                                <Badge variant="secondary" className="text-[10px]">
                                  {field.confidence}%
                                </Badge>
                                {field.edited && (
                                  <span className="size-1.5 rounded-full bg-ring" />
                                )}
                              </div>
                              <div className="mt-2 flex items-center gap-2">
                                <Input className="h-8 text-sm" defaultValue={field.value} readOnly />
                                <Button variant="outline" size="sm">Edit</Button>
                              </div>
                            </div>
                          ))}
                        </div>
                      </AccordionContent>
                    </AccordionItem>
                  ))}
                </Accordion>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
