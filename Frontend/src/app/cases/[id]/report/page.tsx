"use client";

import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { ReportPage } from "@/components/screens/ReportPage";

export default function CaseReportRoutePage() {
  return (
    <ProtectedRoute allowedRoles={["Reviewer", "Admin"]}>
      <ReportPage />
    </ProtectedRoute>
  );
}
