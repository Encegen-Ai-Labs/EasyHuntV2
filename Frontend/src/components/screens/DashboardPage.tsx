"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Activity,
  CheckCircle2,
  FileSearch,
  ArrowRight,
  Search,
  Download,
} from "lucide-react";
import { useDashboardCases } from "@/services/api/hooks";
import { Button } from "@/components/ui/button";
import { KeyboardInput } from "@/components/keyboard/KeyboardField";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import type { CaseRecord } from "@/services/api/client";

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

function toCsv(cases: CaseRecord[]): string {
  const header = ["Case ID", "Title", "Place", "Status", "Created"];
  const rows = cases.map((c) => [
    c.id,
    c.title,
    c.address === "Address N/A" ? "" : c.address,
    statusLabel(c.status),
    c.createdAt,
  ]);
  return [header, ...rows]
    .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(","))
    .join("\n");
}

export function DashboardPage() {
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

  const kpis = useMemo(() => {
    const total = dashboardCases.length;
    const pendingExtractions = dashboardCases.filter((c) => c.status === "Processing" || c.status === "Draft").length;
    const completedReviews = dashboardCases.filter((c) => c.status === "Completed").length;
    return { total, pendingExtractions, completedReviews };
  }, [dashboardCases]);

  function handleExport() {
    const csv = toCsv(filteredCases.length ? filteredCases : dashboardCases);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `easyhuntv2-cases-${new Date().toISOString().split("T")[0]}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  function openCase(caseId: string) {
    router.push(`/cases/${caseId}`);
  }

  return (
    <div className="min-h-screen bg-background">
      <main className="mx-auto max-w-7xl px-4 py-8 md:px-6">
        {/* Page header */}
        <section className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight md:text-4xl">Overview</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Where all your cases stand. Open a case to continue working on it.
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={handleExport} disabled={dashboardCases.length === 0}>
              <Download data-icon="inline-start" />
              Export
            </Button>
            <Button size="sm" nativeButton={false} render={<Link href="/cases/new" />}>
              New case
            </Button>
          </div>
        </section>

        {/* KPI cards */}
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <KpiCard title="All cases" value={String(kpis.total)} icon={<FileSearch size={18} />} />
          <KpiCard title="Being read" value={String(kpis.pendingExtractions)} icon={<Activity size={18} />} />
          <KpiCard title="Finished cases" value={String(kpis.completedReviews)} icon={<CheckCircle2 size={18} />} />
        </section>

        {/* Cases table */}
        <Card className="mt-8">
          <CardHeader className="border-b">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="flex flex-wrap items-center gap-2">
                <div className="relative">
                  <KeyboardInput
                    leadingIcon={<Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />}
                    wrapperClassName="w-[240px]"
                    className="h-9 pl-8 text-sm"
                    placeholder="Search by property name or place…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
                <select
                  className="h-9 min-w-[150px] rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition-colors focus:border-ring"
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
                  className="h-9 min-w-[150px] rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition-colors focus:border-ring"
                  value={dateFilter}
                  onChange={(e) => setDateFilter(e.target.value)}
                >
                  <option>Date range</option>
                  <option>This month</option>
                  <option>Last 30 days</option>
                </select>
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
              <p className="p-6 text-sm font-medium text-destructive">Unable to load cases.</p>
            )}
            {!isLoading && !isError && dashboardCases.length === 0 && (
              <p className="p-6 text-sm text-muted-foreground">
                No cases yet. Press <span className="font-medium text-foreground">New case</span> to start one.
              </p>
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
      </main>
    </div>
  );
}

function KpiCard({
  title,
  value,
  icon,
}: {
  title: string;
  value: string;
  icon: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <CardTitle className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            {title}
          </CardTitle>
          <span className="flex size-8 items-center justify-center rounded-md bg-secondary text-secondary-foreground">
            {icon}
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-bold tracking-tight">{value}</div>
      </CardContent>
    </Card>
  );
}
