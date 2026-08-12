"use client";

import { ProtectedRoute } from "@/components/auth/ProtectedRoute";
import { ReviewPage } from "@/components/screens/ReviewPage";

export default function ReviewCaseIdPage() {
  return (
    <ProtectedRoute allowedRoles={["Reviewer", "Admin"]}>
      <ReviewPage />
    </ProtectedRoute>
  );
}
