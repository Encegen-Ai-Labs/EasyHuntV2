export interface UserRecord {
  id: string;
  email: string;
  role: string;
  organisation_name?: string;
  created_at?: string;
}

export interface CaseRecord {
  id: string;
  title: string;
  property_name?: string;
  survey_number?: string;
  location?: string;
  address: string;
  propertyType: string;
  createdAt: string;
  priority: string;
  status: string;
  assignee: {
    name: string;
    avatar: string;
    id?: string;
  };
  reviewer_id?: string;
  risk: string;
  confidence: number;
}

export interface FlagItem {
  id: string;
  case_id: string;
  flag_type: string;
  severity: "low" | "medium" | "high" | "critical";
  description: string;
  status: "raised" | "resolved" | "pending";
  resolution_notes?: string;
  created_at?: string;
}

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
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

async function handleFetchResponse(res: Response) {
  if (res.status === 401) {
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("auth:unauthorized"));
    }
    throw new Error("Unauthorized (401). Redirecting to login.");
  }
  if (res.status === 403) {
    let errMessage = "Access Denied (403). Insufficient permissions.";
    try {
      const data = await res.json();
      if (data.detail) errMessage = data.detail;
    } catch {}
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("auth:forbidden", { detail: { message: errMessage } }));
    }
    throw new Error(errMessage);
  }

  if (!res.ok) {
    let errorDetail = `HTTP Error ${res.status}`;
    try {
      const errData = await res.json();
      errorDetail = errData.detail || errData.message || errorDetail;
    } catch {}
    throw new Error(errorDetail);
  }

  return res.json();
}

export const apiClient = {
  baseUrl: API_BASE_URL,

  auth: {
    login: async (email: string, password: string) => {
      try {
        const res = await fetch(`${API_BASE_URL}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        const data = await handleFetchResponse(res);
        return {
          success: true,
          token: data.access_token || data.token,
          user: {
            id: data.user_id || "1",
            email: data.email || email,
            role: data.role || "Vendor",
          },
        };
      } catch (err: any) {
        return { success: false, error: err.message || "Invalid credentials" };
      }
    },

    signup: async (payload: { email: string; password: string; name?: string }) => {
      try {
        const res = await fetch(`${API_BASE_URL}/auth/signup`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: payload.email,
            password: payload.password,
            organisation_name: payload.name || "Default Org",
            role: "Vendor",
          }),
        });
        const data = await handleFetchResponse(res);
        return {
          success: true,
          token: data.token || data.access_token,
          user: {
            id: data.user_id || "2",
            email: data.email || payload.email,
            name: payload.name,
            role: data.role || "Vendor",
          },
        };
      } catch (err: any) {
        return { success: false, error: err.message || "Failed to create account" };
      }
    },

    logout: async () => {
      try {
        await fetch(`${API_BASE_URL}/auth/logout`, {
          method: "POST",
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
        });
      } catch {}
    },
  },

  admin: {
    getUsers: async (): Promise<UserRecord[]> => {
      const res = await fetch(`${API_BASE_URL}/admin/users`, {
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
      });
      return handleFetchResponse(res);
    },

    createReviewer: async (payload: { email: string; password: string; organisation_name: string }) => {
      const res = await fetch(`${API_BASE_URL}/admin/reviewers`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(payload),
      });
      return handleFetchResponse(res);
    },

    assignReviewer: async (caseId: string, reviewerId: string) => {
      const res = await fetch(
        `${API_BASE_URL}/admin/assign-reviewer?case_id=${encodeURIComponent(caseId)}&reviewer_id=${encodeURIComponent(reviewerId)}`,
        {
          method: "POST",
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
        }
      );
      return handleFetchResponse(res);
    },
  },

  cases: {
    list: async (statusFilter?: string): Promise<{ data: CaseRecord[] }> => {
      try {
        const url = new URL(`${API_BASE_URL}/cases`);
        if (statusFilter && statusFilter !== "all") {
          url.searchParams.append("status", statusFilter);
        }
        const res = await fetch(url.toString(), {
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
        });
        const data = await handleFetchResponse(res);
        const casesList = Array.isArray(data) ? data : [];
        return { data: casesList };
      } catch (err: any) {
        console.warn("Failed to fetch cases from API:", err.message);
        return { data: [] };
      }
    },

    getById: async (id: string): Promise<CaseRecord> => {
      const res = await fetch(`${API_BASE_URL}/cases/${id}`, {
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
      });
      return handleFetchResponse(res);
    },

    create: async (payload: { property_name: string; survey_number: string; location: string }) => {
      const res = await fetch(`${API_BASE_URL}/cases`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(payload),
      });
      return handleFetchResponse(res);
    },

    finalize: async (caseId: string) => {
      const res = await fetch(`${API_BASE_URL}/cases/${caseId}/finalize`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
      });
      return handleFetchResponse(res);
    },
  },

  documents: {
    upload: (
      caseId: string,
      file: File,
      options?: {
        onProgress?: (progress: number) => void;
        signal?: AbortSignal;
      }
    ): Promise<{ success: boolean; data?: any; error?: string }> => {
      return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", `${API_BASE_URL}/documents/upload`);

        const token = typeof window !== "undefined" ? localStorage.getItem("propverify_token") : null;
        if (token) {
          xhr.setRequestHeader("Authorization", `Bearer ${token}`);
        }

        if (options?.signal) {
          options.signal.addEventListener("abort", () => {
            xhr.abort();
            reject(new DOMException("Upload canceled by user", "AbortError"));
          });
        }

        if (xhr.upload && options?.onProgress) {
          xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
              const percentComplete = Math.round((e.loaded / e.total) * 100);
              options.onProgress!(percentComplete);
            }
          };
        }

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              const resData = JSON.parse(xhr.responseText);
              resolve({ success: true, data: resData });
            } catch {
              resolve({ success: true, data: { id: "doc-uploaded" } });
            }
          } else if (xhr.status === 401) {
            if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent("auth:unauthorized"));
            reject(new Error("Unauthorized (401)"));
          } else if (xhr.status === 403) {
            if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent("auth:forbidden"));
            reject(new Error("Forbidden (403)"));
          } else {
            reject(new Error(`Upload failed with status ${xhr.status}`));
          }
        };

        xhr.onerror = () => reject(new Error("Network error during document upload"));
        xhr.onabort = () => reject(new DOMException("Upload canceled by user", "AbortError"));

        const formData = new FormData();
        formData.append("case_id", caseId);
        formData.append("file", file);

        xhr.send(formData);
      });
    },

    process: async (docId: string) => {
      const res = await fetch(`${API_BASE_URL}/documents/${docId}/process`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
      });
      return handleFetchResponse(res);
    },

    getStatus: async (documentId: string) => {
      const res = await fetch(`${API_BASE_URL}/documents/${documentId}/status`, {
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
      });
      return handleFetchResponse(res);
    },
  },

  review: {
    getPending: async (): Promise<CaseRecord[]> => {
      const res = await fetch(`${API_BASE_URL}/review/pending`, {
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
      });
      return handleFetchResponse(res);
    },

    submitDocumentDecision: async (
      documentId: string,
      payload: {
        validated_output: Record<string, any>;
        review_notes?: string;
        decision: "approved" | "rejected";
      }
    ) => {
      const res = await fetch(`${API_BASE_URL}/review/documents/${documentId}`, {
        method: "PATCH",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(payload),
      });
      return handleFetchResponse(res);
    },

    finalizeCaseDecision: async (caseId: string, decision: "approve" | "reject") => {
      const res = await fetch(
        `${API_BASE_URL}/review/${encodeURIComponent(caseId)}/decision?decision=${encodeURIComponent(decision)}`,
        {
          method: "POST",
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
        }
      );
      return handleFetchResponse(res);
    },
  },

  flags: {
    list: async (caseId?: string): Promise<FlagItem[]> => {
      const url = new URL(`${API_BASE_URL}/flags`);
      if (caseId) url.searchParams.append("case_id", caseId);
      const res = await fetch(url.toString(), {
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
      });
      return handleFetchResponse(res);
    },

    raise: async (caseId: string, payload: { flag_type: string; severity: "low" | "medium" | "high" | "critical"; description: string }) => {
      const res = await fetch(`${API_BASE_URL}/flags/${encodeURIComponent(caseId)}`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(payload),
      });
      return handleFetchResponse(res);
    },

    resolve: async (flagId: string, resolutionNotes: string, status = "resolved") => {
      const res = await fetch(`${API_BASE_URL}/review/flag/${encodeURIComponent(flagId)}/resolve`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ resolution_notes: resolutionNotes, status }),
      });
      return handleFetchResponse(res);
    },
  },

  reports: {
    generate: async (caseId: string) => {
      const res = await fetch(`${API_BASE_URL}/reports/generate/${encodeURIComponent(caseId)}`, {
        method: "POST",
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
      });
      return handleFetchResponse(res);
    },

    getDownloadUrl: async (caseId: string): Promise<{ download_url: string }> => {
      const res = await fetch(`${API_BASE_URL}/reports/download/${encodeURIComponent(caseId)}`, {
        headers: getAuthHeaders({ "Content-Type": "application/json" }),
      });
      return handleFetchResponse(res);
    },
  },
};
