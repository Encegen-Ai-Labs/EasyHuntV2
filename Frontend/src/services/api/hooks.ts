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

export function useReviewDocuments(caseId: string) {
  return useQuery({
    queryKey: ["review", caseId, "documents"],
    queryFn: () => apiClient.review.getCaseDocuments(caseId),
    enabled: Boolean(caseId),
    staleTime: 15_000,
  });
}

export function useSubmitDocumentReviewMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      documentId,
      caseId,
      payload,
    }: {
      documentId: string;
      caseId: string;
      payload: { validated_output: Record<string, any>; review_notes?: string; decision?: "approved" | "rejected" };
    }) => apiClient.review.submitDocumentReview(documentId, payload),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ["review", variables.caseId, "documents"] });
    },
  });
}

export function useUploadDocumentMutation() {
  return useMutation({
    mutationFn: ({ caseId, files }: { caseId: string; files: File[] }) =>
      apiClient.documents.upload(caseId, files),
  });
}

export function useDocumentPages(docId: string) {
  return useQuery({
    queryKey: ["documents", docId, "pages"],
    queryFn: () => apiClient.documents.getPages(docId),
    enabled: Boolean(docId),
    staleTime: 15_000,
  });
}

export function useTranslateDocumentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (docId: string) => apiClient.documents.translate(docId),
    onSuccess: (_data, docId) => {
      // Both the search page-viewer (getPages) and the review documents list
      // read english_text — invalidate whichever of these queries are mounted.
      queryClient.invalidateQueries({ queryKey: ["documents", docId, "pages"] });
      queryClient.invalidateQueries({ queryKey: ["review"] });
    },
  });
}

export function useUpdateDocumentPageMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      docId,
      pageNumber,
      updates,
    }: {
      docId: string;
      pageNumber: number;
      updates: { original_text?: string; english_text?: string };
    }) => apiClient.documents.updatePageText(docId, pageNumber, updates),
    onSuccess: (_data, { docId }) => {
      // Same invalidation set as translate — a page-text edit affects the
      // same two surfaces (this page-viewer, and the review documents list).
      queryClient.invalidateQueries({ queryKey: ["documents", docId, "pages"] });
      queryClient.invalidateQueries({ queryKey: ["review"] });
    },
  });
}

export function useEnhancedPageImageMutation() {
  return useMutation({
    mutationFn: ({ docId, pageNumber }: { docId: string; pageNumber: number }) =>
      apiClient.documents.getEnhancedImageUrl(docId, pageNumber),
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
