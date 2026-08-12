"use client";

import { MoreHorizontal, Plus, Search } from "lucide-react";
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
  if (risk === "High") return "outline";
  return "secondary";
}

export function CasesPage() {
  const { data, isLoading, isError } = useDashboardCases();
  const dashboardCases = data?.data ?? [];

  return (
    <div className="min-h-screen bg-background px-4 py-8">
      <div className="mx-auto max-w-7xl">
        {/* Page header */}
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Case Operations</p>
            <h1 className="mt-1 text-3xl font-bold tracking-tight">All Cases</h1>
          </div>
          <Button size="sm">
            <Plus data-icon="inline-start" />
            Create Case
          </Button>
        </div>

        <Card>
          <CardHeader className="border-b">
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative min-w-[220px] flex-1">
                <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input className="h-9 pl-8 text-sm" placeholder="Search by title or address…" readOnly />
              </div>
              <select className="h-9 min-w-[160px] rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition-colors focus:border-ring">
                <option>All status</option>
                <option>Draft</option>
                <option>Processing</option>
                <option>Needs Review</option>
                <option>Flagged</option>
                <option>Completed</option>
              </select>
              <select className="h-9 min-w-[160px] rounded-lg border border-input bg-background px-3 text-sm text-foreground outline-none transition-colors focus:border-ring">
                <option>Date range</option>
                <option>This month</option>
                <option>Last 30 days</option>
              </select>
              <Button variant="outline" size="sm">Filters</Button>
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
            {!isLoading && !isError && (
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
                  {dashboardCases.map((caseItem) => (
                    <TableRow key={caseItem.id}>
                      <TableCell>
                        <div className="font-medium">{caseItem.title}</div>
                        <div className="text-xs text-muted-foreground">{caseItem.id}</div>
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
      </div>
    </div>
  );
}
