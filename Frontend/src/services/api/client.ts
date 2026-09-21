export type CaseStatus = "Draft" | "Processing" | "Needs Review" | "Flagged" | "Completed";

export interface CaseRecord {
  id: string;
  title: string;
  address: string;
  propertyType: string;
  createdAt: string;
  priority: "Low" | "Normal" | "High" | "Critical";
  status: CaseStatus;
  assignee: {
    name: string;
    avatar: string;
  };
  risk: "Low" | "Medium" | "High" | "Critical";
  confidence: number;
  reviewer_id?: string;
  // Raw backend case fields (app/schemas/cases.py CaseResponse) — normalizeCase()
  // below maps these into title/address above, but screens sometimes read the
  // backend field names directly (e.g. CaseWorkspacePage.tsx's header).
  property_name?: string;
  location?: string;
  survey_number?: string;
}

export interface UserRecord {
  id: string;
  email: string;
  role: string;
  organisation_name?: string;
  created_at?: string;
}

export interface DocumentRecord {
  id: string;
  case_id: string;
  file_name: string;
  file_path: string;
  file_size: number;
  mime_type: string;
  status: string;
  created_at: string;
  uploaded_by?: string;
}

export interface DocumentUploadResult {
  file_name: string;
  success: boolean;
  document?: DocumentRecord;
  error?: string;
}

export interface BatchUploadResponse {
  results: DocumentUploadResult[];
}

export interface DocumentPageRecord {
  page_number: number;
  original_text?: string;
  english_text?: string;
}

export interface DocumentPagesResponse {
  document_id: string;
  pages: DocumentPageRecord[];
}

export type SearchMode = "exact" | "semantic";

export interface SearchResult {
  document_id: string;
  document_name?: string;
  page_number: number;
  matched_in: "original" | "english" | "semantic";
  snippet: string;
  // Only set for semantic-mode results (0..1, higher = more relevant) —
  // exact mode has no ranking score, a substring either matched or it didn't.
  similarity?: number;
}

export interface SearchResponse {
  query: string;
  mode: SearchMode;
  results: SearchResult[];
}

export interface ReportExcerpt {
  id: string;
  document_id: string;
  document_name?: string;
  page_number: number;
  excerpt_text: string;
  sequence_order: number;
  note?: string;
  created_at: string;
}

export interface ReportBuilderState {
  report_id: string;
  case_id: string;
  status: string;
  excerpts: ReportExcerpt[];
}

export interface ReportExportResult {
  file_path: string;
  download_url: string;
}

// Shape of app/services/pipeline_service.py's "extractions" table rows — the
// real Gemini extraction output. validated_json_output holds the actual fields
// (backend/app/services/llm_extractor.py's EXTRACTION_PROMPT: owner_name,
// survey_number, transaction_date, etc., each with a matching "<field>_confidence"
// key of "high"/"medium"/"low" — not a fixed schema, so the frontend renders
// whatever keys are present rather than assuming a specific field list.
export interface ExtractionRecord {
  id: string;
  document_id: string;
  raw_ocr_text?: string | null;
  raw_json_output?: Record<string, any> | null;
  validated_json_output?: Record<string, any> | null;
  human_correction?: Record<string, any> | null;
  model_used?: string;
  confidence?: string;
  validation_errors?: any[] | null;
  needs_review?: boolean;
  has_handwritten_content?: boolean;
  handwriting_flagged?: boolean;
  status?: string;
  review_notes?: string | null;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  created_at?: string;
}

export interface ReviewDocumentEntry {
  document: DocumentRecord;
  file_url: string;
  extraction: ExtractionRecord | null;
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  process.env.BACKEND_URL ||
  "http://localhost:8000/api/v1";

function getAuthHeaders(extraHeaders: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = { ...extraHeaders };
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("propverify_token");
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }
  return headers;
}

function normalizeCase(item: any): CaseRecord {
  const statusMap: Record<string, CaseRecord["status"]> = {
    open: "Processing",
    processing: "Processing",
    review: "Needs Review",
    completed: "Completed",
    flagged: "Flagged",
    draft: "Draft",
  };

  return {
    id: String(item.id || item.case_id || "PV-0000"),
    title: item.title || item.property_name || "Untitled Property",
    address: item.address || item.location || "Address N/A",
    propertyType: item.propertyType || item.property_type || "Residential",
    createdAt: item.createdAt || item.created_at?.split("T")[0] || new Date().toISOString().split("T")[0],
    priority: item.priority || "High",
    status: statusMap[item.status?.toLowerCase()] || item.status || "Needs Review",
    assignee: item.assignee || { name: "System Reviewer", avatar: "SR" },
    risk: item.risk || "Medium",
    confidence: item.confidence ?? 85,
    reviewer_id: item.reviewer_id,
    property_name: item.property_name,
    location: item.location,
    survey_number: item.survey_number,
  };
}

export const apiClient = {
  baseUrl: API_BASE_URL,

  dashboard: {
    getCases: async (): Promise<{ data: CaseRecord[] }> => {
      const res = await fetch(`${API_BASE_URL}/cases`, {
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
      });
      if (!res.ok) throw new Error(`Failed to load cases (HTTP ${res.status})`);
      const data = await res.json();
      const cases = Array.isArray(data) ? data.map(normalizeCase) : [];
      return { data: cases };
    },
  },

  cases: {
    getById: async (id: string): Promise<{ data: CaseRecord }> => {
      const res = await fetch(`${API_BASE_URL}/cases/${id}`, {
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
      });
      if (!res.ok) throw new Error(`Failed to load case (HTTP ${res.status})`);
      const item = await res.json();
      return { data: normalizeCase(item) };
    },

    create: async (payload: { property_name: string; survey_number: string; location?: string }) => {
      try {
        const res = await fetch(`${API_BASE_URL}/cases`, {
          method: "POST",
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Failed with status ${res.status}`);
        }
        const data = await res.json();
        return { success: true, data: normalizeCase(data) };
      } catch (err: any) {
        console.warn("Error creating case via backend API:", err);
        return { success: false, error: err.message };
      }
    },
  },

  auth: {
    login: async (email: string, password: string) => {
      try {
        const res = await fetch(`${API_BASE_URL}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          return {
            success: false,
            error: errData.detail || "Invalid login credentials",
          };
        }

        const data = await res.json();
        if (data.access_token && typeof window !== "undefined") {
          localStorage.setItem("propverify_token", data.access_token);
          if (data.user_id) localStorage.setItem("propverify_user_id", data.user_id);
          if (data.role) localStorage.setItem("propverify_role", data.role);
        }

        return {
          success: true,
          token: data.access_token,
          user: {
            id: data.user_id || "1",
            email: data.email || email,
            role: data.role || "Reviewer",
          },
        };
      } catch (err: any) {
        return { success: false, error: err.message || "Network error while logging in" };
      }
    },

    logout: async () => {
      // No server-side session to invalidate today; kept as a hook for a future
      // token-revocation endpoint. AuthContext.logout() clears local state regardless.
    },
  },

  documents: {
    // Uploads a batch of up to 20 files in one multipart request. Uses XHR
    // instead of fetch because fetch cannot report upload progress; onProgress
    // reports the whole batch's transfer progress, not per-file (a single
    // multipart POST can't distinguish which file is "at" a given percent).
    upload: (
      caseId: string,
      files: File[],
      options?: { signal?: AbortSignal; onProgress?: (percent: number) => void }
    ): Promise<{ success: boolean; data?: BatchUploadResponse; error?: string }> => {
      return new Promise((resolve) => {
        const formData = new FormData();
        formData.append("case_id", caseId);
        files.forEach((file) => formData.append("files", file));

        const xhr = new XMLHttpRequest();
        xhr.open("POST", `${API_BASE_URL}/documents/upload`);
        for (const [key, value] of Object.entries(getAuthHeaders())) {
          xhr.setRequestHeader(key, value);
        }

        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable && options?.onProgress) {
            options.onProgress(Math.round((e.loaded / e.total) * 100));
          }
        };

        xhr.onload = () => {
          let parsed: any = null;
          try {
            parsed = JSON.parse(xhr.responseText);
          } catch {
            // fall through to status-based handling below
          }
          if (xhr.status >= 200 && xhr.status < 300 && parsed) {
            resolve({ success: true, data: parsed as BatchUploadResponse });
          } else {
            resolve({ success: false, error: parsed?.detail || `Upload failed with status ${xhr.status}` });
          }
        };

        xhr.onerror = () => resolve({ success: false, error: "Network error during upload" });
        xhr.onabort = () => resolve({ success: false, error: "Upload canceled" });

        if (options?.signal) {
          if (options.signal.aborted) {
            xhr.abort();
          } else {
            options.signal.addEventListener("abort", () => xhr.abort());
          }
        }

        xhr.send(formData);
      });
    },

    getStatus: async (docId: string) => {
      try {
        const res = await fetch(`${API_BASE_URL}/documents/${docId}`, {
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return { success: true, data: await res.json() };
      } catch (err: any) {
        return { success: false, error: err.message };
      }
    },

    // Deletes a document immediately, including while it's still
    // uploading/processing in the background — see
    // backend/app/services/doc_service.py::DocumentService.delete_document
    // for exactly what "delete while processing" means (soft-discard: the
    // row and file are gone right away; any in-flight background pipeline
    // work for it just finishes with nowhere left to write its result, it
    // isn't actually interrupted mid-call).
    delete: async (docId: string): Promise<{ success: boolean; error?: string }> => {
      try {
        const res = await fetch(`${API_BASE_URL}/documents/${docId}`, {
          method: "DELETE",
          headers: getAuthHeaders(),
        });
        if (!res.ok && res.status !== 204) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Failed to delete document (status ${res.status})`);
        }
        return { success: true };
      } catch (err: any) {
        return { success: false, error: err.message };
      }
    },

    listByCase: async (caseId: string): Promise<{ success: boolean; data?: DocumentRecord[]; error?: string }> => {
      try {
        const url = new URL(`${API_BASE_URL}/documents`);
        url.searchParams.set("case_id", caseId);
        const res = await fetch(url.toString(), {
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return { success: true, data: await res.json() };
      } catch (err: any) {
        return { success: false, error: err.message };
      }
    },

    getPages: async (docId: string): Promise<{ success: boolean; data?: DocumentPagesResponse; error?: string }> => {
      try {
        const res = await fetch(`${API_BASE_URL}/documents/${docId}/pages`, {
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return { success: true, data: await res.json() };
      } catch (err: any) {
        return { success: false, error: err.message };
      }
    },

    // Lets a reviewer correct a page's transcribed text (original-language
    // and/or English). Writes straight to document_pages, the same columns
    // search/translation/report excerpts read from, so a fix here propagates
    // everywhere else that page's text is used — see
    // backend/app/api/v1/documents.py::update_document_page.
    updatePageText: async (
      docId: string,
      pageNumber: number,
      updates: { original_text?: string; english_text?: string }
    ): Promise<{ success: boolean; data?: DocumentPageRecord; error?: string }> => {
      try {
        const res = await fetch(`${API_BASE_URL}/documents/${docId}/pages/${pageNumber}`, {
          method: "PATCH",
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify(updates),
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Failed to save page edit (status ${res.status})`);
        }
        return { success: true, data: await res.json() };
      } catch (err: any) {
        return { success: false, error: err.message };
      }
    },

    // Admin-only: a short-lived signed URL to a page's post-OpenCV-enhanced
    // image (the exact bytes OCR/Gemini actually read) — see
    // backend/app/api/v1/documents.py::get_enhanced_page_image.
    getEnhancedImageUrl: async (
      docId: string,
      pageNumber: number
    ): Promise<{ success: boolean; data?: { url: string }; error?: string }> => {
      try {
        const res = await fetch(`${API_BASE_URL}/documents/${docId}/pages/${pageNumber}/enhanced-image`, {
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Failed to load enhanced image (status ${res.status})`);
        }
        return { success: true, data: await res.json() };
      } catch (err: any) {
        return { success: false, error: err.message };
      }
    },

    process: async (docId: string) => {
      try {
        const res = await fetch(`${API_BASE_URL}/documents/${docId}/process`, {
          method: "POST",
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Processing failed with status ${res.status}`);
        }
        return { success: true, data: await res.json() };
      } catch (err: any) {
        return { success: false, error: err.message };
      }
    },

    // On-demand — translation no longer runs automatically during upload
    // (backend/app/services/pipeline_service.py). Runs synchronously server-side
    // (fast enough not to need polling like /process does), so this resolves
    // with the translated pages directly.
    translate: async (docId: string): Promise<{ success: boolean; data?: DocumentPagesResponse; error?: string }> => {
      try {
        const res = await fetch(`${API_BASE_URL}/documents/${docId}/translate`, {
          method: "POST",
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Translation failed with status ${res.status}`);
        }
        return { success: true, data: await res.json() };
      } catch (err: any) {
        return { success: false, error: err.message };
      }
    },
  },

  reports: {
    generate: async (caseId: string) => {
      try {
        const res = await fetch(`${API_BASE_URL}/reports/generate/${caseId}`, {
          method: "POST",
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Report generation failed`);
        }
        return { success: true, data: await res.json() };
      } catch (err: any) {
        return { success: false, error: err.message };
      }
    },

    download: async (caseId: string) => {
      try {
        const res = await fetch(`${API_BASE_URL}/reports/download/${caseId}`, {
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Download failed`);
        }
        return { success: true, data: await res.json() };
      } catch (err: any) {
        return { success: false, error: err.message };
      }
    },
  },

  flags: {
    list: async (caseId?: string) => {
      try {
        const url = new URL(`${API_BASE_URL}/flags`);
        if (caseId) url.searchParams.append("case_id", caseId);

        const res = await fetch(url.toString(), {
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return { success: true, data: await res.json() };
      } catch (err: any) {
        return { success: false, error: err.message };
      }
    },

    resolve: async (flagId: string, resolutionNotes: string, status = "resolved") => {
      try {
        const res = await fetch(`${API_BASE_URL}/flags/${flagId}/resolve`, {
          method: "PUT",
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({ resolution_notes: resolutionNotes, status }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return { success: true, data: await res.json() };
      } catch (err: any) {
        return { success: false, error: err.message };
      }
    },
  },

  // Real per-document extraction results for the review workspace (backend:
  // app/api/v1/review.py). Distinct from documents.listByCase — this returns the
  // actual Gemini output (extraction.validated_json_output) plus a signed file_url
  // for the source document, not just upload/status metadata.
  review: {
    getCaseDocuments: async (caseId: string): Promise<{ success: boolean; data?: ReviewDocumentEntry[]; error?: string }> => {
      try {
        const res = await fetch(`${API_BASE_URL}/review/${caseId}/documents`, {
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Failed to load review documents (${res.status})`);
        }
        return { success: true, data: await res.json() };
      } catch (err: any) {
        return { success: false, error: err.message };
      }
    },

    submitDocumentReview: async (
      documentId: string,
      // decision omitted (undefined) saves the reviewer's field edits without
      // finalizing approve/reject — see backend/app/services/review_service.py.
      payload: { validated_output: Record<string, any>; review_notes?: string; decision?: "approved" | "rejected" }
    ): Promise<{ success: boolean; data?: any; error?: string }> => {
      try {
        const res = await fetch(`${API_BASE_URL}/review/documents/${documentId}`, {
          method: "PATCH",
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Failed to submit review (${res.status})`);
        }
        return { success: true, data: await res.json() };
      } catch (err: any) {
        return { success: false, error: err.message };
      }
    },
  },

  // Admin-only reviewer account management (backend: app/api/v1/admin.py).
  // Unlike the namespaces above, these throw on failure rather than returning
  // { success: false }, since UserManagementPage.tsx calls them from a try/catch.
  admin: {
    getUsers: async (): Promise<UserRecord[]> => {
      const res = await fetch(`${API_BASE_URL}/admin/users`, {
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Failed to load users (${res.status})`);
      }
      return res.json();
    },

    createReviewer: async (payload: { email: string; password: string; organisation_name: string }) => {
      const res = await fetch(`${API_BASE_URL}/admin/reviewers`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Failed to create reviewer (${res.status})`);
      }
      return res.json();
    },

    assignReviewer: async (caseId: string, reviewerId: string) => {
      const url = new URL(`${API_BASE_URL}/admin/assign-reviewer`);
      url.searchParams.set("case_id", caseId);
      url.searchParams.set("reviewer_id", reviewerId);

      const res = await fetch(url.toString(), {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Failed to assign reviewer (${res.status})`);
      }
      return res.json();
    },
  },

  search: {
    searchCase: async (
      caseId: string,
      query: string,
      mode: SearchMode = "exact"
    ): Promise<{ success: boolean; data?: SearchResponse; error?: string }> => {
      try {
        const url = new URL(`${API_BASE_URL}/cases/${caseId}/search`);
        url.searchParams.set("q", query);
        url.searchParams.set("mode", mode);
        const res = await fetch(url.toString(), {
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Search failed with status ${res.status}`);
        }
        return { success: true, data: await res.json() };
      } catch (err: any) {
        return { success: false, error: err.message };
      }
    },
  },

  reportBuilder: {
    get: async (caseId: string): Promise<{ success: boolean; data?: ReportBuilderState; error?: string }> => {
      try {
        const res = await fetch(`${API_BASE_URL}/cases/${caseId}/report-builder`, {
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return { success: true, data: await res.json() };
      } catch (err: any) {
        return { success: false, error: err.message };
      }
    },

    addExcerpt: async (
      caseId: string,
      payload: { document_id: string; page_number: number; excerpt_text: string; note?: string }
    ): Promise<{ success: boolean; data?: ReportExcerpt; error?: string }> => {
      try {
        const res = await fetch(`${API_BASE_URL}/cases/${caseId}/report-builder/excerpts`, {
          method: "POST",
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Failed to add excerpt (${res.status})`);
        }
        return { success: true, data: await res.json() };
      } catch (err: any) {
        return { success: false, error: err.message };
      }
    },

    updateExcerptNote: async (
      caseId: string,
      excerptId: string,
      note: string,
      excerptText?: string
    ): Promise<{ success: boolean; data?: ReportExcerpt; error?: string }> => {
      try {
        const res = await fetch(`${API_BASE_URL}/cases/${caseId}/report-builder/excerpts/${excerptId}`, {
          method: "PATCH",
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify(excerptText !== undefined ? { note, excerpt_text: excerptText } : { note }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return { success: true, data: await res.json() };
      } catch (err: any) {
        return { success: false, error: err.message };
      }
    },

    removeExcerpt: async (caseId: string, excerptId: string): Promise<{ success: boolean; error?: string }> => {
      try {
        const res = await fetch(`${API_BASE_URL}/cases/${caseId}/report-builder/excerpts/${excerptId}`, {
          method: "DELETE",
          headers: getAuthHeaders(),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return { success: true };
      } catch (err: any) {
        return { success: false, error: err.message };
      }
    },

    reorder: async (
      caseId: string,
      excerptIds: string[]
    ): Promise<{ success: boolean; data?: ReportExcerpt[]; error?: string }> => {
      try {
        const res = await fetch(`${API_BASE_URL}/cases/${caseId}/report-builder/excerpts/reorder`, {
          method: "PUT",
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({ excerpt_ids: excerptIds }),
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Failed to reorder excerpts (${res.status})`);
        }
        return { success: true, data: await res.json() };
      } catch (err: any) {
        return { success: false, error: err.message };
      }
    },

    exportPdf: async (caseId: string): Promise<{ success: boolean; data?: ReportExportResult; error?: string }> => {
      try {
        const res = await fetch(`${API_BASE_URL}/cases/${caseId}/report-builder/export`, {
          method: "POST",
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Export failed with status ${res.status}`);
        }
        return { success: true, data: await res.json() };
      } catch (err: any) {
        return { success: false, error: err.message };
      }
    },
  },
};
