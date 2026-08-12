"use client";

import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { UploadPage } from "@/components/screens/UploadPage";

export default function CasesUploadPage() {
  return (
    <ProtectedRoute allowedRoles={["Vendor", "Admin"]}>
      <UploadPage />
    </ProtectedRoute>
  );
}
