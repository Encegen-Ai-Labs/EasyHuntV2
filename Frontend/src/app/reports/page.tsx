"use client";

import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { ReportPage } from "@/components/screens/ReportPage";

export default function ReportsRoutePage() {
  return (
    <ProtectedRoute allowedRoles={["Admin", "Reviewer"]}>
      <ReportPage />
    </ProtectedRoute>
  );
}
