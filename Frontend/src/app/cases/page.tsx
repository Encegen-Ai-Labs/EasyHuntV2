"use client";

import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { DashboardPage } from "@/components/screens/DashboardPage";

export default function CasesRoute() {
  return (
    <ProtectedRoute allowedRoles={["Vendor", "Reviewer", "Admin"]}>
      <DashboardPage />
    </ProtectedRoute>
  );
}
