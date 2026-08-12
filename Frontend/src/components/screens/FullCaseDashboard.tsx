"use client";

import { AlertTriangle, ArrowUp, CheckCircle2, FileCheck2, FileSearch, Search } from "lucide-react";
import { PdfDownloadButton } from "@/components/ui/PdfDownloadButton";
import { useDashboardCases } from "@/services/api/hooks";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/Input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";

function riskVariant(risk: string): "default" | "secondary" | "destructive" | "outline" {
  if (risk === "Critical") return "destructive";
  return "outline";
}

export function FullCaseDashboard() {
  const { data, isLoading, isError } = useDashboardCases();
  const dashboardCases = data?.data ?? [];

  return (
    <div className="min-h-screen bg-background">
      <div className="mx-auto max-w-7xl px-4 py-10 md:px-6">
        {/* Header */}
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Operational Dashboard</p>
            <h1 className="mt-1 text-3xl font-bold tracking-tight md:text-4xl">Case Dashboard</h1>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm">Filter</Button>
            <PdfDownloadButton label="Export Summary" />
          </div>
        </div>

        {/* KPI strip */}
        <section className="grid gap-4 md:grid-cols-4">
          {[
            { title: "Total Cases", value: "24", detail: "+12%", icon: <FileSearch size={18} /> },
            { title: "In Processing", value: "06", detail: "Live OCR", icon: <FileCheck2 size={18} /> },
            { title: "Flagged", value: "03", detail: "Risk review", icon: <AlertTriangle size={18} /> },
            { title: "Completed", value: "11", detail: "Reviewed", icon: <CheckCircle2 size={18} /> },
          ].map(({ title, value, detail, icon }) => (
            <Card key={title}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">{title}</span>
                  <span className="flex size-8 items-center justify-center rounded-md bg-secondary text-secondary-foreground">{icon}</span>
                </div>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold tracking-tight">{value}</div>
                <div className="mt-1 text-xs text-muted-foreground">{detail}</div>
              </CardContent>
            </Card>
          ))}
        </section>

        {/* Table */}
        <Card className="mt-8">
          <CardHeader className="border-b">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
                  <Input className="h-9 w-[240px] pl-8 text-sm" placeholder="Search by case…" readOnly />
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className="text-xs">Table view</Badge>
                <Button variant="outline" size="sm">Grid</Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {isLoading && (
              <div className="flex flex-col gap-3 p-6">
                {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
              </div>
            )}
            {isError && (
              <p className="p-6 text-sm font-medium text-destructive">Unable to load dashboard rows.</p>
            )}
            {!isLoading && !isError && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Case</TableHead>
                    <TableHead>Document Status</TableHead>
                    <TableHead>Owner</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Risk</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {dashboardCases.map((c) => (
                    <TableRow key={c.id}>
                      <TableCell>
                        <div className="font-medium">{c.title}</div>
                        <div className="text-xs text-muted-foreground">{c.id} • {c.address}</div>
                      </TableCell>
                      <TableCell><Badge variant="secondary">Ready</Badge></TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Avatar size="sm">
                            <AvatarFallback>{c.assignee.avatar}</AvatarFallback>
                          </Avatar>
                          <span className="text-sm">{c.assignee.name}</span>
                        </div>
                      </TableCell>
                      <TableCell><Badge variant="outline">{c.status}</Badge></TableCell>
                      <TableCell><Badge variant={riskVariant(c.risk)}>{c.risk}</Badge></TableCell>
                      <TableCell className="text-muted-foreground">{c.createdAt}</TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="sm">•••</Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
