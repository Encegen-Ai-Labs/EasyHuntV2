"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { apiClient } from "@/services/api/client";

export const dashboardCasesQuery = {
  key: ["dashboard", "cases"],
};

export function useDashboardCases() {
  return useQuery({
    queryKey: dashboardCasesQuery.key,
    queryFn: apiClient.dashboard.getCases,
    staleTime: 30_000,
  });
}

export function useCaseById(caseId: string) {
  return useQuery({
    queryKey: ["cases", caseId],
    queryFn: () => apiClient.cases.getById(caseId),
    enabled: Boolean(caseId),
    staleTime: 60_000,
  });
}

export function useExtractedFields() {
  return useQuery({
    queryKey: ["cases", "extracted-fields"],
    queryFn: apiClient.cases.getExtractedFields,
    staleTime: 60_000,
  });
}

export function useLoginMutation() {
  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      apiClient.auth.login(email, password),
  });
}

export function useSignupMutation() {
  return useMutation({
    mutationFn: (payload: Parameters<typeof apiClient.auth.signup>[0]) =>
      apiClient.auth.signup(payload),
  });
}
