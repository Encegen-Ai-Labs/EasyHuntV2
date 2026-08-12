"use client";

import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { CaseWorkspacePage } from "@/components/screens/CaseWorkspacePage";

export default function CaseWorkspaceRoutePage() {
  return (
    <ProtectedRoute allowedRoles={["Vendor", "Reviewer", "Admin"]}>
      <CaseWorkspacePage />
    </ProtectedRoute>
  );
}
