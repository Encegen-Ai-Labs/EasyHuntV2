"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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

export function useCreateCaseMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: { property_name: string; survey_number: string; location?: string }) =>
      apiClient.cases.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: dashboardCasesQuery.key });
    },
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

export function useUploadDocumentMutation() {
  return useMutation({
    mutationFn: ({ caseId, file }: { caseId: string; file: File }) =>
      apiClient.documents.upload(caseId, file),
  });
}

export function useProcessDocumentMutation() {
  return useMutation({
    mutationFn: (docId: string) => apiClient.documents.process(docId),
  });
}

export function useGenerateReportMutation() {
  return useMutation({
    mutationFn: (caseId: string) => apiClient.reports.generate(caseId),
  });
}

export function useDownloadReportQuery(caseId: string) {
  return useQuery({
    queryKey: ["reports", "download", caseId],
    queryFn: () => apiClient.reports.download(caseId),
    enabled: Boolean(caseId),
  });
}

export function useFlagsQuery(caseId?: string) {
  return useQuery({
    queryKey: ["flags", caseId || "all"],
    queryFn: () => apiClient.flags.list(caseId),
  });
}

export function useResolveFlagMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ flagId, notes, status }: { flagId: string; notes: string; status?: string }) =>
      apiClient.flags.resolve(flagId, notes, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["flags"] });
    },
  });
}
