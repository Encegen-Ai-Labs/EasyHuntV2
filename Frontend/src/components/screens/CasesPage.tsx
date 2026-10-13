"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, FolderOpen, Plus, Search } from "lucide-react";
import { useDashboardCases } from "@/services/api/hooks";
import { Button } from "@/components/ui/button";
import { KeyboardInput } from "@/components/keyboard/KeyboardField";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";


/** What a case's status means, in words a first-time user understands. */
const STATUS_LABEL: Record<string, string> = {
  Draft: "Not started",
  Processing: "Reading documents",
  "Needs Review": "Ready to review",
  Flagged: "Needs attention",
  Completed: "Finished",
};
const statusLabel = (status: string) => STATUS_LABEL[status] ?? status;

function isWithinDays(dateStr: string, days: number): boolean {
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return true;
  const diffMs = Date.now() - date.getTime();
  return diffMs >= 0 && diffMs <= days * 24 * 60 * 60 * 1000;
}

function isThisCalendarMonth(dateStr: string): boolean {
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return true;
  const now = new Date();
  return date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth();
}

export function CasesPage() {
  const router = useRouter();
  const { data, isLoading, isError } = useDashboardCases();
  const dashboardCases = useMemo(() => data?.data ?? [], [data]);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("All status");
  const [dateFilter, setDateFilter] = useState("Date range");

  const filteredCases = useMemo(() => {
    return dashboardCases.filter((c) => {
      const q = search.trim().toLowerCase();
      const matchesSearch =
        !q || c.title.toLowerCase().includes(q) || c.address.toLowerCase().includes(q) || c.id.toLowerCase().includes(q);
      const matchesStatus = statusFilter === "All status" || c.status === statusFilter;
      const matchesDate =
        dateFilter === "Date range" ||
        (dateFilter === "This month" && isThisCalendarMonth(c.createdAt)) ||
        (dateFilter === "Last 30 days" && isWithinDays(c.createdAt, 30));
      return matchesSearch && matchesStatus && matchesDate;
    });
  }, [dashboardCases, search, statusFilter, dateFilter]);

  function openCase(caseId: string) {
    router.push(`/cases/${caseId}`);
  }

  return (
    <div className="min-h-screen bg-background px-4 py-8">
      <div className="mx-auto max-w-7xl">
        {/* Page header */}
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Your cases</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              One case is one property. Open a case to add its documents, check them and make the report.
            </p>
          </div>
          <Button size="sm" nativeButton={false} render={<Link href="/cases/new" />}>
            <Plus data-icon="inline-start" />
            Create Case
          </Button>
        </div>

        <Card>
          <CardHeader className="border-b">
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative min-w-[220px] flex-1">
                <KeyboardInput
                  leadingIcon={<Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />}
                  className="h-9 pl-8 text-sm"
                  placeholder="Search by property name or place…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <select
                className="h-9 min-w-[160px] rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition-colors focus:border-ring"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="All status">All statuses</option>
                <option value="Draft">{statusLabel("Draft")}</option>
                <option value="Processing">{statusLabel("Processing")}</option>
                <option value="Needs Review">{statusLabel("Needs Review")}</option>
                <option value="Flagged">{statusLabel("Flagged")}</option>
                <option value="Completed">{statusLabel("Completed")}</option>
              </select>
              <select
                className="h-9 min-w-[160px] rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition-colors focus:border-ring"
                value={dateFilter}
                onChange={(e) => setDateFilter(e.target.value)}
              >
                <option>Date range</option>
                <option>This month</option>
                <option>Last 30 days</option>
              </select>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {isLoading && (
              <div className="flex flex-col gap-3 p-6">
                {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
              </div>
            )}
            {isError && (
              <p className="p-6 text-sm font-medium text-destructive">Unable to load cases.</p>
            )}
            {!isLoading && !isError && dashboardCases.length === 0 && (
              <div className="flex flex-col items-center gap-3 px-6 py-14 text-center">
                <FolderOpen size={28} className="text-muted-foreground" />
                <p className="text-lg font-semibold">You have no cases yet</p>
                <p className="max-w-sm text-sm text-muted-foreground">
                  Start by creating a case for a property. Then you can upload its documents.
                </p>
                <Button nativeButton={false} render={<Link href="/cases/new" />}>
                  <Plus size={15} data-icon="inline-start" />
                  Create your first case
                </Button>
              </div>
            )}
            {!isLoading && !isError && dashboardCases.length > 0 && filteredCases.length === 0 && (
              <p className="p-6 text-sm text-muted-foreground">No cases match what you typed or chose. Clear the search or the filters to see all cases.</p>
            )}
            {!isLoading && !isError && filteredCases.length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Case</TableHead>
                    <TableHead>Where it is</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="text-right"><span className="sr-only">Open</span></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredCases.map((caseItem) => (
                    <TableRow
                      key={caseItem.id}
                      className="cursor-pointer"
                      onClick={() => openCase(caseItem.id)}
                    >
                      <TableCell>
                        <div className="font-medium">{caseItem.title}</div>
                        <div className="text-xs text-muted-foreground">{caseItem.address === "Address N/A" ? "No location added" : caseItem.address}</div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary">{statusLabel(caseItem.status)}</Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">{caseItem.createdAt}</TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            openCase(caseItem.id);
                          }}
                        >
                          Open
                          <ArrowRight size={14} data-icon="inline-end" />
                        </Button>
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
