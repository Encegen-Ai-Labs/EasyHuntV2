"use client";

import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { CaseCreationPage } from "@/components/screens/CaseCreationPage";

export default function NewCaseRoutePage() {
  return (
    <ProtectedRoute allowedRoles={["Vendor", "Admin"]}>
      <CaseCreationPage />
    </ProtectedRoute>
  );
}
