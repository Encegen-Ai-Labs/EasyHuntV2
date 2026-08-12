"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient, ExtractedGroup } from "@/services/api/client";

export const dashboardCasesQuery = {
  key: ["dashboard", "cases"],
};

export function useDashboardCases(statusFilter?: string) {
  return useQuery({
    queryKey: ["dashboard", "cases", statusFilter || "all"],
    queryFn: () => apiClient.cases.list(statusFilter),
    staleTime: 10_000,
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
    mutationFn: (payload: { property_name: string; survey_number?: string; location?: string }) =>
      apiClient.cases.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: dashboardCasesQuery.key });
    },
  });
}

export function useReviewQueue() {
  return useQuery({
    queryKey: ["review", "queue"],
    queryFn: () => apiClient.review.getQueue(),
    staleTime: 10_000,
  });
}

export function useDocumentExtraction(documentId: string) {
  return useQuery({
    queryKey: ["documents", documentId, "extraction"],
    queryFn: () => apiClient.documents.getExtraction(documentId),
    enabled: Boolean(documentId),
  });
}

export function useSaveExtractionMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ documentId, fields }: { documentId: string; fields: ExtractedGroup[] }) =>
      apiClient.documents.saveExtraction(documentId, fields),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["documents", variables.documentId, "extraction"] });
    },
  });
}

export function useApproveDocumentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: string) => apiClient.documents.approve(documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["review", "queue"] });
      queryClient.invalidateQueries({ queryKey: dashboardCasesQuery.key });
    },
  });
}

export function useRejectDocumentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ documentId, reason }: { documentId: string; reason: string }) =>
      apiClient.documents.reject(documentId, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["review", "queue"] });
      queryClient.invalidateQueries({ queryKey: dashboardCasesQuery.key });
    },
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
