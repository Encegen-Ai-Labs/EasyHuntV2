"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { MoreHorizontal, Plus, Search } from "lucide-react";
import { useDashboardCases } from "@/services/api/hooks";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
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
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Case Operations</p>
            <h1 className="mt-1 text-3xl font-bold tracking-tight">All Cases</h1>
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
                <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  className="h-9 pl-8 text-sm"
                  placeholder="Search by title or address…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <select
                className="h-9 min-w-[160px] rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition-colors focus:border-ring"
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
            {!isLoading && !isError && filteredCases.length === 0 && (
              <p className="p-6 text-sm text-muted-foreground">No cases match your filters.</p>
            )}
            {!isLoading && !isError && filteredCases.length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Case</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Owner</TableHead>
                    <TableHead>Risk</TableHead>
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
                      <TableCell className="text-sm text-muted-foreground">{caseItem.propertyType}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Avatar size="sm">
                            <AvatarFallback>{caseItem.assignee.avatar}</AvatarFallback>
                          </Avatar>
                          <span className="text-sm">{caseItem.assignee.name}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={riskVariant(caseItem.risk)}>{caseItem.risk}</Badge>
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
      </div>
    </div>
  );
}
