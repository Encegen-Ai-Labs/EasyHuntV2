import {
  getCaseById as mockGetCaseById,
  getDashboardCases as mockGetDashboardCases,
  getExtractedFields as mockGetExtractedFields,
  login as mockLogin,
  signup as mockSignup,
  type CaseRecord,
  type SignupData,
} from "@/services/api/mockApi";

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
  };
}

export const apiClient = {
  baseUrl: API_BASE_URL,

  dashboard: {
    getCases: async (): Promise<{ data: CaseRecord[] }> => {
      try {
        const res = await fetch(`${API_BASE_URL}/cases`, {
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const cases = Array.isArray(data) ? data.map(normalizeCase) : [];
        return { data: cases };
      } catch (err) {
        console.warn("Backend API unavailable for dashboard cases, falling back to mock:", err);
        return mockGetDashboardCases();
      }
    },
  },

  cases: {
    getById: async (id: string): Promise<{ data: CaseRecord }> => {
      try {
        const res = await fetch(`${API_BASE_URL}/cases/${id}`, {
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const item = await res.json();
        return { data: normalizeCase(item) };
      } catch (err) {
        console.warn(`Backend API unavailable for case ${id}, falling back to mock:`, err);
        return mockGetCaseById(id);
      }
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

    getExtractedFields: async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/cases/extracted-fields`, {
          headers: getAuthHeaders({ "Content-Type": "application/json" }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        return { data };
      } catch (err) {
        console.warn("Backend API unavailable for extracted fields, falling back to mock:", err);
        return mockGetExtractedFields();
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
            role: data.role || "Vendor",
          },
        };
      } catch (err) {
        console.warn("Backend login failed, using mock auth fallback:", err);
        return mockLogin(email, password);
      }
    },

    signup: async (payload: SignupData) => {
      try {
        const res = await fetch(`${API_BASE_URL}/auth/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: payload.email,
            password: payload.password,
            organisation_name: payload.name || "Default Org",
            role: "Vendor",
          }),
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          return {
            success: false,
            error: errData.detail || "Failed to create account",
          };
        }

        const data = await res.json();
        if (data.token && typeof window !== "undefined") {
          localStorage.setItem("propverify_token", data.token);
          if (data.user_id) localStorage.setItem("propverify_user_id", data.user_id);
        }

        return {
          success: true,
          user: {
            id: data.user_id || "2",
            email: data.email || payload.email,
            name: payload.name,
          },
        };
      } catch (err) {
        console.warn("Backend signup failed, using mock auth fallback:", err);
        return mockSignup(payload);
      }
    },
  },

  documents: {
    upload: async (caseId: string, file: File) => {
      try {
        const formData = new FormData();
        formData.append("case_id", caseId);
        formData.append("file", file);

        const res = await fetch(`${API_BASE_URL}/documents/upload`, {
          method: "POST",
          headers: getAuthHeaders(),
          body: formData,
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Upload failed with status ${res.status}`);
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
};
