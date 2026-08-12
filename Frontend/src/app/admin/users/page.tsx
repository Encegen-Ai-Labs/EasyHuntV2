"use client";

import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { UserManagementPage } from "@/components/screens/UserManagementPage";

export default function AdminUsersPage() {
  return (
    <ProtectedRoute allowedRoles={["Admin"]}>
      <UserManagementPage />
    </ProtectedRoute>
  );
}
