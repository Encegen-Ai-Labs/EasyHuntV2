"use client";

import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { ReportBuilderPage } from "@/components/screens/ReportBuilderPage";

export default function ReportBuilderRoute() {
  return (
    <ProtectedRoute allowedRoles={["Reviewer", "Admin"]}>
      <ReportBuilderPage />
    </ProtectedRoute>
  );
}
