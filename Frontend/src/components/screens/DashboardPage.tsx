"use client";

import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  FileSearch,
  MoreHorizontal,
  Search,
  SlidersHorizontal,
  Calendar,
} from "lucide-react";
import { useDashboardCases } from "@/services/api/hooks";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
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

export function DashboardPage() {
  const { data, isLoading, isError } = useDashboardCases();
  const dashboardCases = data?.data ?? [];

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
            <Button variant="outline" size="sm">Export</Button>
            <Button size="sm">Create Case</Button>
          </div>
        </section>

        {/* KPI cards */}
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <KpiCard
            title="Total Cases"
            value="24"
            change="+12%"
            icon={<FileSearch size={18} />}
          />
          <KpiCard
            title="Pending Extractions"
            value="06"
            change="-2"
            icon={<Activity size={18} />}
          />
          <KpiCard
            title="Critical Risk Flags"
            value="03"
            change="+1"
            icon={<AlertTriangle size={18} />}
          />
          <KpiCard
            title="Completed Reviews"
            value="11"
            change="+18%"
            icon={<CheckCircle2 size={18} />}
          />
        </section>

        {/* Cases table */}
        <Card className="mt-8">
          <CardHeader className="border-b">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
                  <Input className="h-9 w-[240px] pl-8 text-sm" placeholder="Search cases…" readOnly />
                </div>
                <Button variant="outline" size="sm">
                  <SlidersHorizontal data-icon="inline-start" />
                  All Status
                </Button>
                <Button variant="outline" size="sm">
                  <Calendar data-icon="inline-start" />
                  This month
                </Button>
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
            {!isLoading && !isError && (
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
                  {dashboardCases.map((caseItem) => (
                    <TableRow key={caseItem.id}>
                      <TableCell>
                        <div className="font-medium">{caseItem.title}</div>
                        <div className="text-xs text-muted-foreground">{caseItem.id} · {caseItem.address}</div>
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
                        <Button variant="ghost" size="sm">
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
  change,
  icon,
}: {
  title: string;
  value: string;
  change: string;
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
        <div className="mt-2 flex items-center gap-1.5">
          <span className="flex items-center gap-0.5 text-sm font-semibold">
            <ArrowUpRight size={14} />
            {change}
          </span>
          <span className="text-xs text-muted-foreground">vs prior period</span>
        </div>
      </CardContent>
    </Card>
  );
}
