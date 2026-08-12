"use client";

import React, { useState, useEffect } from "react";
import {
  Users,
  UserPlus,
  Shield,
  Building,
  Mail,
  Key,
  CheckCircle2,
  Loader2,
  RefreshCw,
  Search,
  UserCheck,
} from "lucide-react";
import { apiClient, UserRecord, CaseRecord } from "@/services/api/client";
import { useToast } from "@/context/ToastContext";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

export function UserManagementPage() {
  const toast = useToast();

  const [users, setUsers] = useState<UserRecord[]>([]);
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [isLoadingUsers, setIsLoadingUsers] = useState<boolean>(true);

  // Modal State for Adding Reviewer
  const [isAddModalOpen, setIsAddModalOpen] = useState<boolean>(false);
  const [newEmail, setNewEmail] = useState<string>("");
  const [newPassword, setNewPassword] = useState<string>("");
  const [newOrg, setNewOrg] = useState<string>("");
  const [isSubmittingReviewer, setIsSubmittingReviewer] = useState<boolean>(false);

  // Assign Reviewer Loading map
  const [assigningCaseId, setAssigningCaseId] = useState<string | null>(null);

  // Search filter
  const [searchTerm, setSearchTerm] = useState<string>("");

  async function loadData() {
    setIsLoadingUsers(true);
    try {
      const [usersData, casesRes] = await Promise.all([
        apiClient.admin.getUsers(),
        apiClient.cases.list(),
      ]);
      setUsers(usersData || []);
      setCases(casesRes.data || []);
    } catch (err: any) {
      toast.error(err.message || "Failed to load directory data", "Error");
    } fontId: {
      setIsLoadingUsers(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  // Submit Add Reviewer Form
  async function handleAddReviewer(e: React.FormEvent) {
    e.preventDefault();
    if (!newEmail || !newPassword || !newOrg) {
      toast.error("Please fill in all fields", "Validation Error");
      return;
    }

    setIsSubmittingReviewer(true);
    try {
      const res = await apiClient.admin.createReviewer({
        email: newEmail,
        password: newPassword,
        organisation_name: newOrg,
      });

      toast.success(`Reviewer account created for ${res.email}`, "Reviewer Created");
      setIsAddModalOpen(false);
      setNewEmail("");
      setNewPassword("");
      setNewOrg("");
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Failed to create reviewer account", "Error");
    } finally {
      setIsSubmittingReviewer(false);
    }
  }

  // Handle Case Assign Reviewer Action
  async function handleAssignReviewer(caseId: string, reviewerId: string) {
    if (!reviewerId) return;
    setAssigningCaseId(caseId);
    try {
      await apiClient.admin.assignReviewer(caseId, reviewerId);
      toast.success(`Reassigned case ${caseId} to reviewer`, "Reviewer Assigned");
      loadData();
    } catch (err: any) {
      toast.error(err.message || "Failed to assign reviewer", "Assignment Error");
    } finally {
      setAssigningCaseId(null);
    }
  }

  const reviewers = users.filter((u) => u.role.toLowerCase() === "reviewer" || u.role.toLowerCase() === "admin");

  const filteredUsers = users.filter(
    (u) =>
      u.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (u.organisation_name && u.organisation_name.toLowerCase().includes(searchTerm.toLowerCase())) ||
      u.role.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-background px-4 py-8 md:px-6">
      <div className="mx-auto max-w-7xl">
        {/* Header */}
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              Admin Console
            </p>
            <h1 className="mt-1 text-3xl font-bold tracking-tight">User Directory & Case Assignments</h1>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={loadData} disabled={isLoadingUsers}>
              <RefreshCw size={14} className={isLoadingUsers ? "animate-spin" : ""} data-icon="inline-start" />
              Refresh Directory
            </Button>
            <Button size="sm" onClick={() => setIsAddModalOpen(true)} className="gap-1.5">
              <UserPlus size={16} />
              Add Reviewer
            </Button>
          </div>
        </div>

        {/* User Directory Table Card */}
        <Card className="mb-8">
          <CardHeader className="border-b">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <CardTitle className="text-lg">User Directory</CardTitle>
                <CardDescription>System accounts across Vendor, Reviewer, and Admin roles.</CardDescription>
              </div>
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  className="h-9 w-[240px] pl-8 text-sm"
                  placeholder="Search users..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {isLoadingUsers ? (
              <div className="p-8 text-center text-sm text-muted-foreground">
                <Loader2 size={24} className="animate-spin mx-auto mb-2 text-primary" />
                Loading user directory…
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>User</TableHead>
                    <TableHead>Role</TableHead>
                    <TableHead>Organisation</TableHead>
                    <TableHead>Created Date</TableHead>
                    <TableHead className="text-right">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredUsers.map((u) => (
                    <TableRow key={u.id}>
                      <TableCell>
                        <div className="flex items-center gap-2.5">
                          <Avatar size="sm">
                            <AvatarFallback>{u.email.substring(0, 2).toUpperCase()}</AvatarFallback>
                          </Avatar>
                          <div>
                            <div className="font-semibold text-foreground">{u.email}</div>
                            <div className="text-xs text-muted-foreground font-mono">ID: {u.id}</div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            u.role.toLowerCase() === "admin"
                              ? "destructive"
                              : u.role.toLowerCase() === "reviewer"
                              ? "default"
                              : "secondary"
                          }
                          className="text-[10px] font-bold uppercase"
                        >
                          {u.role}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm font-medium">
                        {u.organisation_name || "N/A"}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {u.created_at ? u.created_at.split("T")[0] : "Active"}
                      </TableCell>
                      <TableCell className="text-right">
                        <Badge variant="outline" className="border-emerald-500/30 text-emerald-500">
                          Active
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Case Assignment Dropdown Table */}
        <Card>
          <CardHeader className="border-b">
            <CardTitle className="text-lg">Case Reviewer Assignments</CardTitle>
            <CardDescription>Directly assign property cases to qualified reviewers.</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Case Title & ID</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Current Assignee</TableHead>
                  <TableHead>Assign Reviewer</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {cases.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell>
                      <div className="font-semibold">{c.title}</div>
                      <div className="text-xs text-muted-foreground">{c.id} · {c.address}</div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{c.status}</Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2 text-sm">
                        <UserCheck size={14} className="text-primary" />
                        <span>{c.assignee?.name || "Unassigned"}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <select
                          className="h-8 rounded-lg border border-input bg-background px-3 text-xs text-foreground outline-none focus:border-ring cursor-pointer"
                          defaultValue={c.reviewer_id || ""}
                          onChange={(e) => handleAssignReviewer(c.id, e.target.value)}
                          disabled={assigningCaseId === c.id}
                        >
                          <option value="" disabled>Select Reviewer…</option>
                          {reviewers.map((r) => (
                            <option key={r.id} value={r.id}>
                              {r.email} ({r.organisation_name || r.role})
                            </option>
                          ))}
                        </select>
                        {assigningCaseId === c.id && (
                          <Loader2 size={14} className="animate-spin text-primary" />
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Add Reviewer Modal */}
        {isAddModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-200">
            <div className="w-full max-w-md rounded-xl border border-border bg-background p-6 shadow-2xl">
              <div className="flex items-center gap-3">
                <span className="flex size-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <UserPlus size={20} />
                </span>
                <div>
                  <h3 className="text-lg font-bold">Add Reviewer Account</h3>
                  <p className="text-xs text-muted-foreground">POST /api/v1/admin/reviewers</p>
                </div>
              </div>

              <form onSubmit={handleAddReviewer} className="mt-5 flex flex-col gap-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                    Reviewer Email
                  </label>
                  <Input
                    type="email"
                    placeholder="reviewer@auditfirm.com"
                    value={newEmail}
                    onChange={(e) => setNewEmail(e.target.value)}
                    required
                  />
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                    Initial Password
                  </label>
                  <Input
                    type="password"
                    placeholder="••••••••"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                  />
                </div>

                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                    Organisation Name
                  </label>
                  <Input
                    type="text"
                    placeholder="Legal Audit Partners LLC"
                    value={newOrg}
                    onChange={(e) => setNewOrg(e.target.value)}
                    required
                  />
                </div>

                <div className="mt-4 flex justify-end gap-3">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setIsAddModalOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button type="submit" size="sm" disabled={isSubmittingReviewer}>
                    {isSubmittingReviewer ? (
                      <>
                        <Loader2 size={14} className="animate-spin" data-icon="inline-start" />
                        Creating Account…
                      </>
                    ) : (
                      "Create Reviewer"
                    )}
                  </Button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
