"use client";

import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { CaseSearchPage } from "@/components/screens/CaseSearchPage";

export default function CaseSearchRoutePage() {
  return (
    <ProtectedRoute allowedRoles={["Reviewer", "Admin"]}>
      <CaseSearchPage />
    </ProtectedRoute>
  );
}
