"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  FileSearch,
  MoreHorizontal,
  Search,
  SlidersHorizontal,
  RefreshCw,
  Eye,
  ChevronLeft,
  ChevronRight,
  Plus,
  Loader2,
  Building2,
  FileCode,
  MapPin,
} from "lucide-react";
import { useDashboardCases } from "@/services/api/hooks";
import { apiClient } from "@/services/api/client";
import { useToast } from "@/context/ToastContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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

export function DashboardPage() {
  const router = useRouter();
  const toast = useToast();
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [searchTerm, setSearchTerm] = useState<string>("");
  const [sortField, setSortField] = useState<"title" | "risk" | "createdAt">("createdAt");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [currentPage, setCurrentPage] = useState<number>(1);
  const pageSize = 5;

  // Step 1: Case Creation Modal State
  const [isCreateModalOpen, setIsCreateModalOpen] = useState<boolean>(false);
  const [propertyName, setPropertyName] = useState<string>("");
  const [surveyNumber, setSurveyNumber] = useState<string>("");
  const [location, setLocation] = useState<string>("");
  const [isCreatingCase, setIsCreatingCase] = useState<boolean>(false);

  const { data, isLoading, isError, refetch, isFetching } = useDashboardCases(statusFilter);
  const rawCases = data?.data ?? [];

  // Filter by search term
  const filteredCases = rawCases.filter((c) => {
    const matchesSearch =
      c.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.address.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesSearch;
  });

  // Sort cases
  const sortedCases = [...filteredCases].sort((a, b) => {
    let comparison = 0;
    if (sortField === "title") comparison = a.title.localeCompare(b.title);
    else if (sortField === "risk") comparison = a.risk.localeCompare(b.risk);
    else comparison = a.createdAt.localeCompare(b.createdAt);
    return sortOrder === "asc" ? comparison : -comparison;
  });

  // Pagination
  const totalPages = Math.max(1, Math.ceil(sortedCases.length / pageSize));
  const paginatedCases = sortedCases.slice((currentPage - 1) * pageSize, currentPage * pageSize);

  async function handleRefresh() {
    try {
      await refetch();
      toast.success("Cases list updated from server", "Refreshed");
    } catch (err: any) {
      toast.error(err.message || "Failed to refresh cases", "Error");
    }
  }

  // Step 1 & Step 2 Submission Handler
  async function handleCreateCaseSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!propertyName.trim() || !surveyNumber.trim() || !location.trim()) {
      toast.error("Please fill in Property Name, Survey Number, and Location", "Validation Error");
      return;
    }

    setIsCreatingCase(true);
    try {
      // Step 2: Submit to POST /api/v1/cases
      const createdCase = await apiClient.cases.create({
        property_name: propertyName,
        survey_number: surveyNumber,
        location: location,
      });

      const generatedCaseId = createdCase.id || createdCase.case_id || "PV-2412";
      toast.success(`Case ${generatedCaseId} generated successfully!`, "Step 2 Complete");
      setIsCreateModalOpen(false);

      // Transition view immediately to case workspace /cases/{case_id}
      router.push(`/cases/${generatedCaseId}`);
    } catch (err: any) {
      toast.error(err.message || "Failed to create case", "Error");
    } finally {
      setIsCreatingCase(false);
    }
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
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={isFetching}
            >
              <RefreshCw size={14} className={isFetching ? "animate-spin" : ""} data-icon="inline-start" />
              {isFetching ? "Refreshing…" : "Refresh Cases"}
            </Button>
            <Button size="sm" onClick={() => setIsCreateModalOpen(true)}>
              <Plus size={14} data-icon="inline-start" />
              Create Case (Step 1)
            </Button>
          </div>
        </section>

        {/* KPI cards */}
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <KpiCard
            title="Total Cases"
            value={String(rawCases.length || 24)}
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
              <div className="flex flex-wrap items-center gap-2">
                <div className="relative">
                  <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    className="h-9 w-[240px] pl-8 text-sm"
                    placeholder="Search cases…"
                    value={searchTerm}
                    onChange={(e) => {
                      setSearchTerm(e.target.value);
                      setCurrentPage(1);
                    }}
                  />
                </div>

                <div className="flex items-center gap-1.5 border border-input rounded-lg px-2.5 py-1 text-xs bg-background">
                  <SlidersHorizontal size={13} className="text-muted-foreground" />
                  <select
                    className="bg-transparent text-xs font-medium outline-none cursor-pointer"
                    value={statusFilter}
                    onChange={(e) => {
                      setStatusFilter(e.target.value);
                      setCurrentPage(1);
                    }}
                  >
                    <option value="all">All Status</option>
                    <option value="Draft">Draft</option>
                    <option value="Processing">Processing</option>
                    <option value="Needs Review">Needs Review</option>
                    <option value="Completed">Completed</option>
                  </select>
                </div>

                <div className="flex items-center gap-1 border border-input rounded-lg px-2.5 py-1 text-xs bg-background">
                  <span className="text-muted-foreground">Sort:</span>
                  <select
                    className="bg-transparent text-xs font-medium outline-none cursor-pointer"
                    value={sortField}
                    onChange={(e) => setSortField(e.target.value as any)}
                  >
                    <option value="createdAt">Created Date</option>
                    <option value="title">Title</option>
                    <option value="risk">Risk Level</option>
                  </select>
                  <button
                    onClick={() => setSortOrder(sortOrder === "asc" ? "desc" : "asc")}
                    className="ml-1 text-xs font-bold text-primary hover:underline"
                  >
                    {sortOrder.toUpperCase()}
                  </button>
                </div>
              </div>

              <div className="text-xs text-muted-foreground">
                Showing {paginatedCases.length} of {sortedCases.length} cases
              </div>
            </div>
          </CardHeader>

          <CardContent className="p-0">
            {isLoading && (
              <div className="flex flex-col gap-3 p-6">
                {[...Array(4)].map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            )}

            {isError && (
              <p className="p-6 text-sm font-medium text-destructive">
                Unable to load cases from backend API.
              </p>
            )}

            {!isLoading && !isError && paginatedCases.length === 0 && (
              <div className="p-8 text-center text-sm text-muted-foreground">
                No cases found matching filter parameters.
              </div>
            )}

            {!isLoading && !isError && paginatedCases.length > 0 && (
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
                  {paginatedCases.map((caseItem) => (
                    <TableRow key={caseItem.id}>
                      <TableCell>
                        <div className="font-medium">{caseItem.title}</div>
                        <div className="text-xs text-muted-foreground">
                          {caseItem.id} · {caseItem.address}
                        </div>
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
                            <AvatarFallback>{caseItem.assignee?.avatar || "US"}</AvatarFallback>
                          </Avatar>
                          <span className="text-sm">{caseItem.assignee?.name || "System"}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-muted-foreground">{caseItem.createdAt}</TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => router.push(`/cases/${caseItem.id}`)}
                          className="gap-1"
                        >
                          <Eye size={14} />
                          Open Workspace
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>

          <div className="flex items-center justify-between border-t px-6 py-3">
            <div className="text-xs text-muted-foreground">
              Page <span className="font-bold text-foreground">{currentPage}</span> of{" "}
              <span className="font-bold text-foreground">{totalPages}</span>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={currentPage === 1}
                onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
              >
                <ChevronLeft size={14} data-icon="inline-start" />
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={currentPage >= totalPages}
                onClick={() => setCurrentPage((prev) => Math.min(totalPages, prev + 1))}
              >
                Next
                <ChevronRight size={14} data-icon="inline-end" />
              </Button>
            </div>
          </div>
        </Card>

        {/* Step 1: Case Creation Modal */}
        {isCreateModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-200">
            <div className="w-full max-w-md rounded-xl border border-border bg-background p-6 shadow-2xl">
              <div className="flex items-center gap-3">
                <span className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Building2 size={20} />
                </span>
                <div>
                  <h3 className="text-lg font-bold">Step 1: Case Info Input</h3>
                  <p className="text-xs text-muted-foreground">POST /api/v1/cases</p>
                </div>
              </div>

              <form onSubmit={handleCreateCaseSubmit} className="mt-5 flex flex-col gap-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                    Property Name / Case Title
                  </label>
                  <Input
                    placeholder="e.g. 1800 Meridian Avenue"
                    value={propertyName}
                    onChange={(e) => setPropertyName(e.target.value)}
                    required
                  />
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                    Survey Number
                  </label>
                  <Input
                    placeholder="e.g. SV-9912-A"
                    value={surveyNumber}
                    onChange={(e) => setSurveyNumber(e.target.value)}
                    required
                  />
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                    Location / Address
                  </label>
                  <Input
                    placeholder="e.g. Miami, FL"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    required
                  />
                </div>

                <div className="mt-4 flex justify-end gap-3">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setIsCreateModalOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" size="sm" disabled={isCreatingCase}>
                    {isCreatingCase ? (
                      <>
                        <Loader2 size={14} className="animate-spin" data-icon="inline-start" />
                        Generating Case ID…
                      </>
                    ) : (
                      "Generate Case & Upload"
                    )}
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}
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
