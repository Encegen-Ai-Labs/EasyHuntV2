"use client";

import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { UsagePage } from "@/components/screens/UsagePage";

export default function AdminUsageRoutePage() {
  return (
    <ProtectedRoute allowedRoles={["Admin"]}>
      <UsagePage />
    </ProtectedRoute>
  );
}
