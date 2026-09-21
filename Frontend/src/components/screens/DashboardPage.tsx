"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  FileSearch,
  MoreHorizontal,
  Search,
  Download,
} from "lucide-react";
import { useDashboardCases } from "@/services/api/hooks";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
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
import type { CaseRecord } from "@/services/api/client";

function riskVariant(risk: string): "default" | "secondary" | "destructive" | "outline" {
  if (risk === "Critical") return "destructive";
  if (risk === "High") return "outline";
  return "secondary";
}

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
  const header = ["Case ID", "Title", "Status", "Priority", "Risk", "Owner", "Created"];
  const rows = cases.map((c) => [
    c.id,
    c.title,
    c.status,
    c.priority,
    c.risk,
    c.assignee.name,
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
    const criticalRiskFlags = dashboardCases.filter((c) => c.risk === "Critical").length;
    const completedReviews = dashboardCases.filter((c) => c.status === "Completed").length;
    return { total, pendingExtractions, criticalRiskFlags, completedReviews };
  }, [dashboardCases]);

  function handleExport() {
    const csv = toCsv(filteredCases.length ? filteredCases : dashboardCases);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `propverify-cases-${new Date().toISOString().split("T")[0]}.csv`;
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
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              Operating Dashboard
            </p>
            <h1 className="mt-1 text-3xl font-bold tracking-tight md:text-4xl">
              Property Intelligence
            </h1>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={handleExport} disabled={dashboardCases.length === 0}>
              <Download data-icon="inline-start" />
              Export
            </Button>
            <Button size="sm" nativeButton={false} render={<Link href="/cases/new" />}>
              Create Case
            </Button>
          </div>
        </section>

        {/* KPI cards */}
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <KpiCard title="Total Cases" value={String(kpis.total)} icon={<FileSearch size={18} />} />
          <KpiCard title="Pending Extractions" value={String(kpis.pendingExtractions)} icon={<Activity size={18} />} />
          <KpiCard title="Critical Risk Flags" value={String(kpis.criticalRiskFlags)} icon={<AlertTriangle size={18} />} />
          <KpiCard title="Completed Reviews" value={String(kpis.completedReviews)} icon={<CheckCircle2 size={18} />} />
        </section>

        {/* Cases table */}
        <Card className="mt-8">
          <CardHeader className="border-b">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="flex flex-wrap items-center gap-2">
                <div className="relative">
                  <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    className="h-9 w-[240px] pl-8 text-sm"
                    placeholder="Search cases…"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
                <select
                  className="h-9 min-w-[150px] rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition-colors focus:border-ring"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                >
                  <option>All status</option>
                  <option>Draft</option>
                  <option>Processing</option>
                  <option>Needs Review</option>
                  <option>Flagged</option>
                  <option>Completed</option>
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
            {!isLoading && !isError && filteredCases.length === 0 && (
              <p className="p-6 text-sm text-muted-foreground">No cases match your filters.</p>
            )}
            {!isLoading && !isError && filteredCases.length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Case</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Priority</TableHead>
                    <TableHead>Risk</TableHead>
                    <TableHead>Owner</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
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
                        <div className="text-xs text-muted-foreground">{caseItem.address}</div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="secondary">{caseItem.status}</Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{caseItem.priority}</Badge>
                      </TableCell>
                      <TableCell>
                        <Badge variant={riskVariant(caseItem.risk)}>{caseItem.risk}</Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Avatar size="sm">
                            <AvatarFallback>{caseItem.assignee.avatar}</AvatarFallback>
                          </Avatar>
                          <span className="text-sm">{caseItem.assignee.name}</span>
                        </div>
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
                          <MoreHorizontal size={14} />
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
